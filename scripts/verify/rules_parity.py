"""Task P2.3a: the rules engine against the generator's rule mirror on the model v1 dataset.

The rule flags the model saw are frozen for model v1 (PROGRESS_LOG.md section 2), so for every
train, validation and test record the engine must give what the generator stored with the record:
the claim outcome, the claim flags (OON, from R08) and each line's outcome, reason codes in order
and flags (NCCI_BYPASS; R11 to R13 line denials). The RULES_RESULT block of the record's prompt
must also be exactly what the engine's outcome renders to.

The engine's part is R08's flag (check_group_b) and Group C (check_line_edits). Groups A and B are
not compared (P2.3a decision 2): many dataset claims reference authorizations that are not in the
reference data. The full engine is still run on every record to report where it would stop, by
rule and by what is missing.

Rules v2 (P2.3b, R14 to R20) change some lines by design: the engine must give the stored outcome
plus exactly the reason codes and flags listed in tests/golden/rules/v2_dataset_changes.csv (a line
with an added reason is denied; a claim whose every line is denied is DENY), so any unplanned
change still shows. For a record the list does not touch, the prompt's RULES_RESULT block must
still be exactly the engine's. The list is written from the engine (--write-v2-changes) and must
equal the independent checks of scripts/verify/rules_v2_impact.py.

Report only: the generator and the dataset are not changed.

    uv run python -m scripts.verify.rules_parity
    uv run python -m scripts.verify.rules_parity --write-v2-changes   # rewrite the change list
"""

import argparse
import csv
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from app.db.curated import CuratedData, load_curated, rule_codes
from app.db.rules_reference import build_reference, load_code_tables, reference_for_claim
from app.domain.contracts import IntakeClaim, RuleOutcomeValue, RuleResult, RulesOutcome
from app.ml.prompt import _rule_line
from app.rules.engine import evaluate
from app.rules.lcd_edits import REASON_RULES
from app.rules.line_edits import check_line_edits
from app.rules.reference import RulesReference
from app.rules.requirements import check_group_b

ROOT = Path(__file__).resolve().parents[2]
DECISION_DIR = ROOT / "data" / "generated" / "decision"
REFERENCE_DIR = ROOT / "data" / "generated" / "reference"
EXTRA_AUTHORIZATIONS = ROOT / "data" / "generated" / "claims" / "authorizations_extra.jsonl"
SPLITS = ("train", "validation", "test")
CONFIDENCE_MIN = 0.85  # dataset claims are JSON: no field confidences
EXAMPLES = 3
V2_CHANGES = ROOT / "tests" / "golden" / "rules" / "v2_dataset_changes.csv"
CHANGE_FIELDS = ("record_id", "line_no", "rule_id", "kind", "code")
FLAG_RULES = {"NCS_WITHOUT_EMG": "R17", "FACET_TWO_REGIONS": "R19", "EXTENDED_TESTING": "R20"}
V2_RULES = {**REASON_RULES, **FLAG_RULES}  # code -> rule


@dataclass(frozen=True)
class Change:
    """One reason code (kind REASON: the line is denied) or flag that rules v2 add to a line."""

    record_id: str
    line_no: int
    rule_id: str
    kind: str  # REASON | FLAG
    code: str


def read_changes(path: Path = V2_CHANGES) -> dict[str, list[Change]]:
    out: dict[str, list[Change]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["record_id"]].append(
                Change(
                    row["record_id"], int(row["line_no"]), row["rule_id"], row["kind"], row["code"]
                )
            )
    return dict(out)


def write_changes(changes: Sequence[Change], path: Path = V2_CHANGES) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(CHANGE_FIELDS)
        writer.writerows((c.record_id, c.line_no, c.rule_id, c.kind, c.code) for c in changes)


@cache
def listed_changes() -> dict[str, list[Change]]:
    return read_changes()


def with_changes(stored: RulesOutcome, changes: Sequence[Change]) -> RulesOutcome:
    """The stored v1 outcome with the listed v2 reasons and flags added, in order."""
    lines = []
    for line in stored.line_outcomes:
        mine = [c for c in changes if c.line_no == line.line_no]
        reasons = [*line.reason_codes, *(c.code for c in mine if c.kind == "REASON")]
        flags = [*line.flags, *(c.code for c in mine if c.kind == "FLAG")]
        lines.append(
            line.model_copy(
                update={
                    "outcome": "DENY" if reasons else "PASS",
                    "reason_codes": reasons,
                    "flags": flags,
                }
            )
        )
    denied = bool(lines) and all(line.outcome == "DENY" for line in lines)
    return stored.model_copy(
        update={
            "line_outcomes": lines,
            "claim_outcome": RuleOutcomeValue.DENY if denied else stored.claim_outcome,
        }
    )


def engine_changes(record_id: str, view: RulesOutcome) -> list[Change]:
    """The rules v2 reason codes and flags on the engine's lines (what the change list holds)."""
    return [
        Change(record_id, line.line_no, V2_RULES[code], kind, code)
        for line in view.line_outcomes
        for kind, codes in (("REASON", line.reason_codes), ("FLAG", line.flags))
        for code in codes
        if code in V2_RULES
    ]


@dataclass(frozen=True)
class Record:
    split: str
    record_id: str
    claim: Mapping[str, Any]
    rules_outcome: Mapping[str, Any]
    network: str  # metadata: IN_NETWORK | OUT_OF_NETWORK
    user_message: str


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_records(decision_dir: Path = DECISION_DIR) -> list[Record]:
    """Every record, pairing `<split>_inputs.jsonl` (claim, stored rules outcome) with
    `<split>.jsonl` (the chat the model was trained on) by record ID."""
    records = []
    for split in SPLITS:
        chats = {
            row["metadata"]["record_id"]: row for row in _jsonl(decision_dir / f"{split}.jsonl")
        }
        for row in _jsonl(decision_dir / f"{split}_inputs.jsonl"):
            chat = chats[row["record_id"]]
            records.append(
                Record(
                    split=split,
                    record_id=row["record_id"],
                    claim=row["claim"],
                    rules_outcome=row["rules_outcome"],
                    network=chat["metadata"]["network"],
                    user_message=next(
                        m["content"] for m in chat["messages"] if m["role"] == "user"
                    ),
                )
            )
    return records


def dataset_reference(reference_dir: Path = REFERENCE_DIR) -> RulesReference:
    """The generated reference data, with no claims on file (dataset records are independent)."""
    curated = load_curated()
    return build_reference(
        curated,
        load_code_tables(rule_codes(curated)),  # the dataset bills in-scope codes only
        _jsonl(reference_dir / "members.jsonl"),
        _jsonl(reference_dir / "providers.jsonl"),
        _jsonl(reference_dir / "provider_networks.jsonl"),
        _jsonl(reference_dir / "authorizations.jsonl") + _jsonl(EXTRA_AUTHORIZATIONS),
    )


def engine_view(claim: IntakeClaim, reference: RulesReference) -> RulesOutcome:
    """The part of the engine the prompt shows: R08's claim flag and Group C's line outcomes, with
    the claim outcome Group C gives (every line denied -> DENY)."""
    member = reference.members[claim.member_id]
    _, flags = check_group_b(claim, member, reference)
    _, lines = check_line_edits(claim, reference.plans[member.plan_id], reference)
    denied = all(line.outcome == "DENY" for line in lines)
    return RulesOutcome(
        claim_outcome=RuleOutcomeValue.DENY if denied else RuleOutcomeValue.PASS,
        rule_results=[],
        line_outcomes=lines,
        flags=flags,
    )


def rules_block(outcome: RulesOutcome) -> str:
    """The RULES_RESULT block as app/ml/prompt.py renders it."""
    flags = f" (claim flags: {', '.join(outcome.flags)})" if outcome.flags else ""
    lines = [_rule_line(line) for line in outcome.line_outcomes]
    return "\n".join(
        ["RULES_RESULT", f"Claim outcome: {outcome.claim_outcome.value}{flags}", *lines]
    )


def prompt_block(user_message: str) -> str:
    start = user_message.index("RULES_RESULT\n")
    return user_message[start : user_message.index("\n\n", start)]


def differences(record: Record, reference: RulesReference) -> list[str]:
    claim = IntakeClaim.model_validate(record.claim)
    view = engine_view(claim, reference)
    changes = listed_changes().get(record.record_id, [])
    stored = with_changes(RulesOutcome.model_validate(record.rules_outcome), changes)
    found = []
    if view.claim_outcome is not stored.claim_outcome:
        found.append(f"claim outcome {view.claim_outcome.value} != {stored.claim_outcome.value}")
    if view.flags != stored.flags:
        found.append(f"claim flags {view.flags} != {stored.flags}")
    in_network = reference.in_network(claim.billing_npi, reference.members[claim.member_id].plan_id)
    if ("IN_NETWORK" if in_network else "OUT_OF_NETWORK") != record.network:
        found.append(f"network: engine in_network={in_network}, record {record.network}")
    engine_lines = [line.model_dump() for line in view.line_outcomes]
    stored_lines = [line.model_dump() for line in stored.line_outcomes]
    if engine_lines != stored_lines:
        found += [
            f"line {mine['line_no']}: {mine} != {theirs}"
            for mine, theirs in zip(engine_lines, stored_lines, strict=False)
            if mine != theirs
        ]
        if len(engine_lines) != len(stored_lines):
            found.append(f"{len(engine_lines)} line outcomes != {len(stored_lines)}")
    if not changes and rules_block(view) != prompt_block(record.user_message):
        found.append("the prompt's RULES_RESULT block differs from the engine's")
    return found


# --- The database-backed reference (P2.1) -------------------------------------------------------


def db_differences(
    records: Iterable[Record],
    session: Any,
    file_reference: RulesReference,
    curated: CuratedData | None = None,
) -> dict[str, list[str]]:
    """For every record: the full engine with the database-backed reference
    (app.db.rules_reference.reference_for_claim) against the file-backed one (every rule result,
    reason, flag and line outcome), and the database-backed reference against the generator's
    rule mirror and the prompt's RULES_RESULT text (`differences`). `session` is on a database
    the seed loaded (rule tables from data/raw/, the generated reference, no claims on file)."""
    curated = curated or load_curated()
    found: dict[str, list[str]] = {}
    for record in records:
        db_reference = reference_for_claim(session, record.claim, curated)
        mine = evaluate(record.claim, {}, db_reference, confidence_min=CONFIDENCE_MIN)
        theirs = evaluate(record.claim, {}, file_reference, confidence_min=CONFIDENCE_MIN)
        diff = differences(record, db_reference)
        if mine != theirs:
            diff.insert(0, f"database {mine.model_dump()} != files {theirs.model_dump()}")
        if diff:
            found[record.record_id] = diff
    return found


# --- Where the full engine stops (report only) ---------------------------------------------------


def missing_what(result: RuleResult, claim: IntakeClaim, reference: RulesReference) -> str:
    """What the failing rule could not find, in the reference data or on the claim."""
    if result.rule_id == "R10":
        same_number = [
            auth for auth in reference.authorizations if auth.auth_number == claim.prior_auth_number
        ]
        if claim.prior_auth_number is None:
            return "no prior-authorization number on the claim"
        if not same_number:
            return "prior-authorization number not in the reference data"
        if all(auth.member_id != claim.member_id for auth in same_number):
            return (
                "prior-authorization number in the reference data for another member "
                "(number reused; this claim's authorization is not there)"
            )
        return "authorization on file does not match the provider, code or date"
    if result.rule_id == "R04":
        return "member not in the reference data"
    if result.rule_id == "R06":
        npis = [claim.billing_npi, *(line.rendering_npi for line in claim.service_lines)]
        if any(npi not in reference.providers for npi in npis):
            return "provider not in the reference data"
        return "provider enrollment pending"
    if result.rule_id == "R09":
        return "no referring provider on the claim"
    return result.detail


@dataclass(frozen=True)
class Stop:
    rule_id: str
    reason_code: str
    missing: str
    record_ids: tuple[str, ...]


def full_run_stops(records: Iterable[Record], reference: RulesReference) -> tuple[int, list[Stop]]:
    """Runs the full engine on every record. Returns how many stop in Group A or B and every
    failing rule there, grouped by rule, reason and what is missing."""
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    stopped = 0
    for record in records:
        outcome = evaluate(record.claim, {}, reference, confidence_min=CONFIDENCE_MIN)
        if outcome.line_outcomes:
            continue
        stopped += 1
        claim = IntakeClaim.model_validate(record.claim)
        for result in outcome.rule_results:
            if not result.passed:
                key = (
                    result.rule_id,
                    result.reason_code or "",
                    missing_what(result, claim, reference),
                )
                groups[key].append(record.record_id)
    stops = [
        Stop(rule, reason, missing, tuple(ids))
        for (rule, reason, missing), ids in sorted(groups.items())
    ]
    return stopped, stops


def render(total: int, diffs: Mapping[str, Sequence[str]], stopped: int, stops: list[Stop]) -> str:
    lines = [
        "# P2.3a rules parity (model v1 dataset)",
        "",
        f"Records: {total} (train, validation, test).",
        f"Records where the engine differs from the generator's rule mirror: {len(diffs)}.",
    ]
    for record_id, found in list(diffs.items())[:20]:
        lines.append(f"- {record_id}: {'; '.join(found)}")
    lines += [
        "",
        f"Full engine: {stopped} of {total} records stop in Group A or B.",
        "",
        "| Rule | Reason | What is missing | Records | Examples |",
        "|---|---|---|---|---|",
    ]
    for stop in stops:
        examples = ", ".join(stop.record_ids[:EXAMPLES])
        lines.append(
            f"| {stop.rule_id} | {stop.reason_code} | {stop.missing} | {len(stop.record_ids)} "
            f"| {examples} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write-v2-changes", action="store_true", help="rewrite the change list")
    records = load_records()
    reference = dataset_reference()
    if parser.parse_args().write_v2_changes:
        changes = [
            change
            for r in records
            for change in engine_changes(
                r.record_id, engine_view(IntakeClaim.model_validate(r.claim), reference)
            )
        ]
        write_changes(changes)
        print(f"wrote {V2_CHANGES.relative_to(ROOT)}: {len(changes)} changes")
        return
    diffs = {r.record_id: found for r in records if (found := differences(r, reference))}
    stopped, stops = full_run_stops(records, reference)
    print(render(len(records), diffs, stopped, stops), end="")


if __name__ == "__main__":
    main()
