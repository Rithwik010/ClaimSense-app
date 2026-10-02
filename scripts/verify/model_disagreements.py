"""Task V1c: where the fine-tuned model disagrees with the gold labels on the test split.

Report only: no data, label, policy or generator is changed. Reads the saved evaluation of
claimsense-decision:v1 (data/generated/eval/finetuned-v1.jsonl, written by
training/evaluate/model.py) and the test split it was scored on, and lists every criterion status
and line decision where the model differs from gold. The pairing is the evaluator's: statuses are
compared on valid answers only (an invalid answer is PEND on every model line, as in the
pipeline), and rule-decided lines are not scored.

Disagreements in a group with an already-known label problem are marked, counted and kept out of
the review sample (a record with any such line stays out entirely):
- diagnosis mismatch: V1a check 1's rule (the line's diagnoses do not satisfy its billing
  article's covered ICD-10-CM groups); office visits have no article and are not checked;
- two_policy records with contradictory notes (D-ESI-5), with the V1a follow-up 2 patterns;
- ESI lines (62321, 62323, 64483; D-ESI-1 to D-ESI-7);
- POL-REHAB-001 evaluation lines (97161, 97162; V1b finding POL-REHAB-001.F1).

    uv run python -m scripts.verify.model_disagreements
"""

import csv
import json
import random
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "data" / "generated" / "decision"
EVAL_FILE = ROOT / "data" / "generated" / "eval" / "finetuned-v1.jsonl"
EVAL_SUMMARY = ROOT / "data" / "generated" / "eval" / "finetuned-v1.json"
OUT_DIR = ROOT / "data" / "generated" / "verification"
A_IMPACT = OUT_DIR / "A_impact.md"  # V1a follow-up 2 report: lists the D-ESI-5 records
PROMPT = ROOT / "app" / "ml" / "prompts" / "decision_v2.txt"
SPLITS = ("train", "validation", "test")
SEED = 42
MINUTES_PER_ROW = 3
NOT_LISTED = "(not listed)"
INSTRUCTION = (
    "Read the criterion and notes and decide the status yourself BEFORE looking at the gold and "
    "model columns. Then write LABEL RIGHT, MODEL RIGHT, BOTH WRONG or UNSURE."
)

STATUS = "criterion status"
DECISION = "line decision"

DX = "diagnosis mismatch"
CONTRADICTION = "two_policy contradictory notes"
ESI = "ESI line"
REHAB_EVAL = "POL-REHAB-001 evaluation line"
GROUPS = (DX, CONTRADICTION, ESI, REHAB_EVAL)
GROUP_SOURCE = {
    DX: "V1a check 1: diagnoses do not satisfy the billing article (R15 in v2, D-DX-1)",
    CONTRADICTION: "D-ESI-5: radicular statement and 'no pain down the limbs' in one record",
    ESI: "62321, 62323, 64483: ESI labels conflict with LCD L33906 (D-ESI-1 to D-ESI-7)",
    REHAB_EVAL: "97161, 97162: plan-of-care criterion on evaluations (V1b, POL-REHAB-001.F1)",
}
ESI_CODES = frozenset({"62321", "62323", "64483"})
REHAB_EVALUATION_CODES = frozenset({"97161", "97162"})

# The V1a follow-up 2 patterns (A_impact.md section 2), applied to the whole notes, any case.
RADICULAR = re.compile(
    r"\btravels down the (?:left|right) (?:leg|arm)\b"
    r"|\bradiating to (?:left|right) (?:leg|arm)\b"
    r"|\bshoots down the (?:left|right) leg\b"
    r"|\bradicular pain to\b"
    r"|\b(?:pressing on|pressure on|compressing)\s+(?:the\s+)?(?:(?:left|right)\s+)?[CLST]\d\s+"
    r"(?:nerve\s+)?root\b"
    r"|\bfor (?:leg|arm) pain\b",
    re.IGNORECASE,
)
NO_LIMB_PAIN = re.compile(
    r"\bno pain or numbness down the limbs\b|\bno radicular sx\b", re.IGNORECASE
)

BOUNDARY = "NOT_APPLICABLE / NOT_DOCUMENTED boundary"
SAMPLE_QUOTA: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("MET -> NOT_DOCUMENTED", ("MET -> NOT_DOCUMENTED",), 3),
    ("NOT_MET -> NOT_DOCUMENTED", ("NOT_MET -> NOT_DOCUMENTED",), 3),
    (BOUNDARY, ("NOT_APPLICABLE -> NOT_DOCUMENTED", "NOT_DOCUMENTED -> NOT_APPLICABLE"), 2),
)


@dataclass(frozen=True)
class Line:
    line_no: int
    code: str
    diagnoses: tuple[str, ...] = ()


@dataclass(frozen=True)
class Pair:
    line_no: int
    criterion_id: str
    gold: str
    gold_evidence: str
    model: str | None  # None when the answer was invalid


@dataclass(frozen=True)
class Disagreement:
    record_id: str
    line_no: int
    code: str
    kind: str  # STATUS or DECISION
    gold: str
    model: str
    criterion_id: str = ""
    gold_evidence: str = ""
    model_evidence: str = ""
    valid: bool = True
    groups: tuple[str, ...] = ()  # known problems of this line (or of its whole record)
    record_groups: tuple[str, ...] = ()  # known problems anywhere in the record
    scenario: str = ""
    note_style: str = ""
    policies: str = ""

    @property
    def error_type(self) -> str:
        return f"{self.gold} -> {self.model}"

    @property
    def key(self) -> tuple[str, int, str, str]:
        """Unique: one status disagreement per criterion and line, one decision per line."""
        return self.record_id, self.line_no, self.kind, self.criterion_id


# --- grouping ---------------------------------------------------------------------------------


def contradictory_notes(notes: str) -> bool:
    """D-ESI-5: a radicular statement and 'no pain down the limbs' in the same notes."""
    return bool(RADICULAR.search(notes) and NO_LIMB_PAIN.search(notes))


def line_groups(
    scenario: str,
    notes: str,
    lines: Iterable[Line],
    dx_supported: Callable[[Line], bool | None],
) -> dict[int, tuple[str, ...]]:
    """The known label-problem groups of each scored line. `dx_supported` returns None when the
    line's code has no billing article (not checkable)."""
    contradiction = scenario == "two_policy" and contradictory_notes(notes)
    out = {}
    for line in lines:
        found = set()
        if dx_supported(line) is False:
            found.add(DX)
        if contradiction:
            found.add(CONTRADICTION)
        if line.code in ESI_CODES:
            found.add(ESI)
        if line.code in REHAB_EVALUATION_CODES:
            found.add(REHAB_EVAL)
        out[line.line_no] = tuple(g for g in GROUPS if g in found)
    return out


# --- pairing ----------------------------------------------------------------------------------


def pair_criteria(
    target_lines: Sequence[Mapping[str, Any]], saved: Sequence[Mapping[str, Any]]
) -> list[Pair]:
    """Give the evaluator's saved (gold, predicted) pairs their line and criterion ID. The
    evaluator wrote them in gold order (target lines, then each line's criteria); any other
    order, or a gold status that differs from the target, stops the run."""
    gold = [(line["line_no"], c) for line in target_lines for c in line["criteria"]]
    if len(gold) != len(saved):
        raise ValueError(f"{len(saved)} saved pairs for {len(gold)} gold criteria")
    pairs = []
    for (line_no, criterion), pair in zip(gold, saved, strict=True):
        if criterion["status"] != pair["gold"]:
            raise ValueError(
                f"line {line_no} {criterion['criterion_id']}: saved gold {pair['gold']} is not "
                f"the target's {criterion['status']}"
            )
        pairs.append(
            Pair(
                line_no,
                criterion["criterion_id"],
                criterion["status"],
                criterion.get("evidence", ""),
                pair["predicted"],
            )
        )
    return pairs


def record_disagreements(
    record_id: str,
    lines: Mapping[int, Line],
    pairs: Sequence[Pair],
    saved_lines: Sequence[Mapping[str, Any]],
    valid: bool,
    model_evidence: Mapping[tuple[int, str], str],
    groups: Mapping[int, tuple[str, ...]],
    scenario: str = "",
    note_style: str = "",
    policies: str = "",
) -> list[Disagreement]:
    """Status disagreements (valid answers only), then line-decision disagreements."""
    record_groups = tuple(g for g in GROUPS if any(g in found for found in groups.values()))

    def row(line_no: int, kind: str, gold: str, model: str, **more: str) -> Disagreement:
        return Disagreement(
            record_id,
            line_no,
            lines[line_no].code,
            kind,
            gold,
            model,
            valid=valid,
            groups=groups.get(line_no, ()),
            record_groups=record_groups,
            scenario=scenario,
            note_style=note_style,
            policies=policies,
            **more,
        )

    rows = []
    if valid:
        for p in pairs:
            model = p.model or NOT_LISTED
            if model != p.gold:
                rows.append(
                    row(
                        p.line_no,
                        STATUS,
                        p.gold,
                        model,
                        criterion_id=p.criterion_id,
                        gold_evidence=p.gold_evidence,
                        model_evidence=model_evidence.get((p.line_no, p.criterion_id), ""),
                    )
                )
    for line in saved_lines:
        if line["gold"] != line["predicted"]:
            rows.append(row(line["line_no"], DECISION, line["gold"], line["predicted"]))
    return rows


# --- sample -----------------------------------------------------------------------------------


def select_sample(
    rows: Iterable[Disagreement],
    seed: int = SEED,
    quota: Sequence[tuple[str, tuple[str, ...], int]] = SAMPLE_QUOTA,
) -> tuple[list[Disagreement], dict[str, int]]:
    """Status disagreements on valid answers in records with no known problem: the quota's
    number from each pool (pools sorted, then drawn with one seeded generator in quota order),
    then shuffled so the row order does not reveal the error type. A short pool is taken whole
    and its shortfall reported; nothing is substituted."""
    rng = random.Random(seed)
    candidates = [r for r in rows if r.kind == STATUS and r.valid and not r.record_groups]
    sample: list[Disagreement] = []
    short: dict[str, int] = {}
    for name, types, wanted in quota:
        pool = sorted(
            (r for r in candidates if r.error_type in types),
            key=lambda r: (r.record_id, r.line_no, r.criterion_id),
        )
        picks = rng.sample(pool, min(wanted, len(pool)))
        if len(picks) < wanted:
            short[name] = wanted - len(picks)
        sample += picks
    rng.shuffle(sample)
    return sample, short


# --- inputs and self-checks -------------------------------------------------------------------


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dx_checker() -> Callable[[Line], bool | None]:
    """V1a check 1's rule: the line's diagnoses satisfy one of its code's billing-article group
    combinations (data/curated/diagnosis_support.csv, current article version in data/raw/)."""
    from app.db import raw
    from app.db.curated import load_curated
    from scripts.verify.label_checks import Support, supported

    support = {
        code: Support(s.billing_article, s.alternatives)
        for code, s in load_curated().diagnosis_support.items()
    }
    articles = raw.read_article_diagnoses({s.article for s in support.values()})
    covered = {a: dict(d.covered) for a, d in articles.items()}

    def check(line: Line) -> bool | None:
        rule = support.get(line.code)
        return None if rule is None else supported(line.diagnoses, rule, covered)

    return check


def scored_lines(record: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[int, Line]:
    """The record's model-decided lines (the target's lines), with code and line diagnoses."""
    claim = inputs["claim"]
    letters = {chr(ord("A") + k): d for k, d in enumerate(claim["diagnoses"])}
    service = {s["line_no"]: s for s in claim["service_lines"]}
    target = json.loads(record["messages"][-1]["content"])
    return {
        t["line_no"]: Line(
            t["line_no"],
            service[t["line_no"]]["procedure_code"],
            tuple(letters[p] for p in service[t["line_no"]]["diagnosis_pointers"] if p in letters),
        )
        for t in target["lines"]
    }


def model_evidence(result: Mapping[str, Any], pairs: Sequence[Pair]) -> dict[tuple[int, str], str]:
    """The model's evidence per (line, criterion) from its saved answer; its statuses must equal
    the evaluator's saved ones."""
    answer = json.loads(result["output"])
    found = {
        (line["line_no"], c["criterion_id"]): c
        for line in answer["lines"]
        for c in line.get("criteria", [])
    }
    for p in pairs:
        status = found.get((p.line_no, p.criterion_id), {}).get("status")
        if status != p.model:
            raise ValueError(
                f"{result['record_id']} line {p.line_no} {p.criterion_id}: answer says {status}, "
                f"the evaluator saved {p.model}"
            )
    return {key: c.get("evidence", "") for key, c in found.items()}


def documented_contradictions(path: Path = A_IMPACT) -> set[str] | None:
    """The records A_impact.md lists under D-ESI-5, or None when the report is not here."""
    if not path.exists():
        return None
    ids: set[str] = set()
    in_section = False
    for text in path.read_text(encoding="utf-8").splitlines():
        if text.startswith("### "):
            in_section = text.startswith("### D-ESI-5")
        elif in_section:
            found = re.match(r"^\|\s*(DEC-[A-Z]{2}-\d{5})\s*\|", text)
            if found:
                ids.add(found.group(1))
    return ids


def check_contradictions() -> str:
    """The re-implemented D-ESI-5 pattern must find exactly the records V1a listed."""
    found = {
        r["record_id"]
        for split in SPLITS
        for r in _jsonl(DATASET_DIR / f"{split}_inputs.jsonl")
        if contradictory_notes(r["claim"]["clinical_notes"])
    }
    listed = documented_contradictions()
    if listed is None:
        return f"D-ESI-5 pattern: {len(found)} records on all splits (A_impact.md not here)"
    if found != listed:
        raise ValueError(f"D-ESI-5 pattern differs from A_impact.md: {sorted(found ^ listed)}")
    return f"D-ESI-5 pattern: the same {len(found)} records A_impact.md lists (all splits)"


def check_dx_on_all_splits(check: Callable[[Line], bool | None]) -> str:
    """Check 1's rule on every split's model-decided lines (V1a follow-up 2 reported 391
    mismatch lines, all gold DENY)."""
    mismatched, decisions = 0, Counter()
    for split in SPLITS:
        inputs = {r["record_id"]: r for r in _jsonl(DATASET_DIR / f"{split}_inputs.jsonl")}
        for record in _jsonl(DATASET_DIR / f"{split}.jsonl"):
            labels = {x["line_no"]: x["decision"] for x in record["metadata"]["line_labels"]}
            lines = scored_lines(record, inputs[record["metadata"]["record_id"]])
            for line in lines.values():
                if check(line) is False:
                    mismatched += 1
                    decisions[labels[line.line_no]] += 1
    return (
        f"check 1 rule on all splits: {mismatched} mismatch lines (V1a follow-up 2: 391), gold "
        + ", ".join(f"{k} {v}" for k, v in sorted(decisions.items()))
    )


def check_against_summary(rows: Sequence[Disagreement], compared: int, agreed: int) -> str:
    """The recomputed status confusion and accuracy must equal the evaluator's saved summary."""
    metrics = json.loads(EVAL_SUMMARY.read_text(encoding="utf-8"))["metrics"]
    mine = Counter(r.error_type.replace(" -> ", "->") for r in rows if r.kind == STATUS)
    for error_type, count in metrics["criterion_status_confusion"]:
        if mine[error_type] != count:
            raise ValueError(f"{error_type}: {mine[error_type]} here, {count} in the summary")
    if round(agreed / compared, 4) != metrics["criterion_status_accuracy"]:
        raise ValueError(f"status accuracy {agreed}/{compared} differs from the summary")
    return (
        f"matches the evaluator's summary ({len(metrics['criterion_status_confusion'])} top "
        f"error types, status accuracy {metrics['criterion_status_accuracy']})"
    )


def status_definitions(path: Path = PROMPT) -> list[str]:
    """The four status definitions of prompt decision_v2, word for word."""
    wanted = ("- NOT_APPLICABLE:", "- MET:", "- NOT_MET:", "- NOT_DOCUMENTED:")
    found = [
        text.strip()
        for text in path.read_text(encoding="utf-8").splitlines()
        if text.strip().startswith(wanted)
    ]
    if len(found) != len(wanted):
        raise ValueError(f"expected {len(wanted)} status definitions in {path}, found {found}")
    return found


# --- outputs ----------------------------------------------------------------------------------

CSV_FIELDS = (
    "record_id",
    "scenario",
    "note_style",
    "policies",
    "line_no",
    "procedure_code",
    "kind",
    "error_type",
    "criterion_id",
    "criterion_text",
    "gold",
    "model",
    "answer_valid",
    "gold_evidence",
    "model_evidence",
    "known_problem",
    "record_known_problems",
    "review_row",
    "clinical_notes",
)


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def build(out_dir: Path = OUT_DIR) -> None:
    from app.db.curated import load_curated
    from scripts.verify.policy_sources import cpt_descriptors, redact

    curated = load_curated()
    criterion_text = {cid: c.text for cid, c in curated.criteria().items()}
    descriptors = cpt_descriptors(set(curated.scope))
    redacted = 0

    def clean(text: str) -> str:
        nonlocal redacted
        out, n = redact(text or "", descriptors)
        redacted += n
        return out

    records = {r["metadata"]["record_id"]: r for r in _jsonl(DATASET_DIR / "test.jsonl")}
    inputs = {r["record_id"]: r for r in _jsonl(DATASET_DIR / "test_inputs.jsonl")}
    results = _jsonl(EVAL_FILE)
    check = dx_checker()

    rows: list[Disagreement] = []
    notes: dict[str, str] = {}
    group_records: dict[str, set[str]] = {g: set() for g in GROUPS}
    group_lines: Counter[str] = Counter()
    compared = agreed = scored = lines_in_any_group = 0
    for result in results:
        record_id = result["record_id"]
        record, claim_inputs = records[record_id], inputs[record_id]
        meta = record["metadata"]
        target = json.loads(record["messages"][-1]["content"])
        lines = scored_lines(record, claim_inputs)
        notes[record_id] = claim_inputs["claim"]["clinical_notes"]
        groups = line_groups(meta["scenario_type"], notes[record_id], lines.values(), check)
        for found in groups.values():
            lines_in_any_group += bool(found)
            for g in found:
                group_lines[g] += 1
                group_records[g].add(record_id)
        pairs = pair_criteria(target["lines"], result["criteria"])
        evidence = model_evidence(result, pairs) if result["valid"] else {}
        if result["valid"]:
            compared += len(pairs)
            agreed += sum(p.gold == p.model for p in pairs)
        scored += len(result["lines"])
        rows += record_disagreements(
            record_id,
            lines,
            pairs,
            result["lines"],
            result["valid"],
            evidence,
            groups,
            scenario=meta["scenario_type"],
            note_style=meta.get("template_id", ""),
            policies=", ".join(meta.get("policy_ids", [])),
        )

    checks = [
        check_against_summary(rows, compared, agreed),
        check_contradictions(),
        check_dx_on_all_splits(check),
    ]
    sample, short = select_sample(rows)
    review_row = {r.key: n for n, r in enumerate(sample, start=1)}

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "C_disagreements_full.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "record_id": r.record_id,
                    "scenario": r.scenario,
                    "note_style": r.note_style,
                    "policies": r.policies,
                    "line_no": r.line_no,
                    "procedure_code": r.code,
                    "kind": r.kind,
                    "error_type": r.error_type,
                    "criterion_id": r.criterion_id,
                    "criterion_text": clean(criterion_text.get(r.criterion_id, "")),
                    "gold": r.gold,
                    "model": r.model,
                    "answer_valid": "yes" if r.valid else "no",
                    "gold_evidence": clean(r.gold_evidence),
                    "model_evidence": clean(r.model_evidence),
                    "known_problem": "; ".join(r.groups),
                    "record_known_problems": "; ".join(r.record_groups),
                    "review_row": review_row.get(r.key, ""),
                    "clinical_notes": clean(notes[r.record_id]),
                }
            )

    # review sheet
    valid = sum(r["valid"] for r in results)
    statuses = [r for r in rows if r.kind == STATUS]
    decisions = [r for r in rows if r.kind == DECISION]
    lines_md = [
        "# Model disagreements (Task V1c): review sheet",
        "",
        INSTRUCTION,
        "",
        f"Estimated review time: {MINUTES_PER_ROW * len(sample)} minutes ({len(sample)} rows, "
        f"{MINUTES_PER_ROW} minutes per row).",
        "",
        f"Source: claimsense-decision:v1 on the {len(results)} test records "
        f"(`data/generated/eval/finetuned-v1.jsonl`): {valid} valid answers; {compared:,} "
        f"criterion statuses and {scored} line decisions compared, as the evaluator does "
        f"(statuses on valid answers only; an invalid answer is PEND). {len(rows)} "
        f"disagreements ({len(statuses)} statuses, {len(decisions)} line decisions), all in "
        "`C_disagreements_full.csv`.",
        "",
        "## Disagreements per error type (gold -> model)",
        "",
        "| Kind | Gold -> model | All | In a known-problem group | Not explained | From "
        "invalid answers |",
        "|---|---|---|---|---|---|",
    ]
    for kind, items in ((STATUS, statuses), (DECISION, decisions)):
        for error_type, count in Counter(r.error_type for r in items).most_common():
            same = [r for r in items if r.error_type == error_type]
            explained = sum(bool(r.groups) for r in same)
            invalid = sum(not r.valid for r in same)
            lines_md.append(
                f"| {kind} | {error_type} | {count} | {explained} | {count - explained} | "
                f"{invalid if kind == DECISION else '-'} |"
            )
    in_group = [r for r in rows if r.groups]
    outside = [r for r in rows if not r.groups]
    lines_md += [
        "",
        "## Known-problem groups (already explained)",
        "",
        "| Group | Why | Test records | Lines | Status disagreements | Decision disagreements |",
        "|---|---|---|---|---|---|",
    ]
    for g in GROUPS:
        held = [r for r in rows if g in r.groups]
        lines_md.append(
            f"| {g} | {GROUP_SOURCE[g]} | {len(group_records[g])} | {group_lines[g]} | "
            f"{sum(r.kind == STATUS for r in held)} | {sum(r.kind == DECISION for r in held)} |"
        )
    any_records = set().union(*group_records.values())
    lines_md += [
        f"| Any group | A line can be in more than one group | {len(any_records)} | "
        f"{lines_in_any_group} | {sum(r.kind == STATUS for r in in_group)} | "
        f"{sum(r.kind == DECISION for r in in_group)} |",
        f"| No group | Not explained | - | - | {sum(r.kind == STATUS for r in outside)} | "
        f"{sum(r.kind == DECISION for r in outside)} |",
        "",
        f"Of the {len(outside)} unexplained disagreements, "
        f"{sum(bool(r.record_groups) for r in outside)} sit in a record with a known problem on "
        "another line, so they are left out of the sample too.",
        "",
        "## Status definitions (prompt decision_v2, word for word)",
        "",
        *status_definitions(),
        "",
        f"## Sample: {len(sample)} disagreements (seed {SEED}, records in no known-problem group)",
        "",
        "Drawn: "
        + ", ".join(f"{wanted} from {name}" for name, _, wanted in SAMPLE_QUOTA)
        + "; the rows are shuffled, so their order says nothing about the error type."
        + (
            " Short pools: " + ", ".join(f"{name} {n} fewer" for name, n in short.items()) + "."
            if short
            else ""
        ),
        "",
        "| # | Record ID | Criterion ID | Criterion text | Full clinical notes | My status | "
        "Who is right? | Notes | Gold status | Model status |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for n, r in enumerate(sample, start=1):
        lines_md.append(
            f"| {n} | {r.record_id}, line {r.line_no} ({r.code}) | {r.criterion_id} | "
            f"{_cell(clean(criterion_text.get(r.criterion_id, '')))} | "
            f"{_cell(clean(notes[r.record_id]))} |  |  |  | {r.gold} | {r.model} |"
        )
    (out_dir / "C_disagreements_review.md").write_text("\n".join(lines_md) + "\n", encoding="utf-8")

    print(
        f"{len(results)} records ({valid} valid): {len(rows)} disagreements ({len(statuses)} "
        f"statuses, {len(decisions)} decisions); in a known-problem group {len(in_group)}; "
        f"sample {len(sample)}; CPT descriptor text replaced {redacted}"
    )
    for line in checks:
        print(line)


def main() -> None:
    build()


if __name__ == "__main__":
    main()
