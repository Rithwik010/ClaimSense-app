"""Task G1: automatic checks on the rules and calculator golden cases, and a blind spot-check
sheet for one reviewer. Report only: no golden case, rules code or calculator code is changed.

Checks on every case:
- calculator (52 cases), per line and in total: plan pays + member pays = max(0, allowed -
  primary paid); allowed <= billed; no negative amounts; integer cents only; deductible applied
  <= the remaining deductible and member pays <= the remaining out-of-pocket maximum (working
  totals, line by line); copay <= allowed; denied and pended lines pay 0; totals = sum of lines
  (A8); accumulators after = before + the claim's cost share (A5);
- rules (90 cases): one expected outcome, matching its status and its failures; targeted rules
  and failures as in INSTRUCTIONS.md section 8.3; group order (Group A stops; Group B REJECT >
  DENY > PEND, D8; Group C = R11-R13, D8); H5 with the FIELDS_USED mapping; conflicts with R14
  (D-ESI-3) and R15 (D-DX-1); cases a D-RULE-1 single-claim candidate may change (for review);
- coverage: rules, rule variants and cost-share situations without a golden case.

Outputs in data/generated/verification/: G_spotcheck_sheet.md (blind: inputs only),
G_spotcheck_answers.csv (expected values) and G_golden_checks.csv (check details, with expected
amounts). The sheet tells the reviewer to open the two CSVs only after every cell is filled.

    uv run python -m scripts.verify.golden_checks
"""

import csv
import json
import random
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden"
INSTRUCTIONS_MD = ROOT / "INSTRUCTIONS.md"
README_MD = GOLDEN / "README.md"
OUT_DIR = ROOT / "data" / "generated" / "verification"
SHEET_FILE = "G_spotcheck_sheet.md"
ANSWERS_FILE = "G_spotcheck_answers.csv"
CHECKS_FILE = "G_golden_checks.csv"
SEED = 42
SAMPLE_SIZE = 10
MINUTES_PER_RULES_CASE = 3
MINUTES_PER_CALCULATOR_CASE = 6
CONFIDENCE_MIN = 0.85  # EXTRACTION_CONFIDENCE_MIN (section 8.12); "below" = strictly less (A-R9)

STATUS = {
    "PASS": "RECEIVED",
    "REJECT": "REJECTED",
    "DENY": "DENIED_BY_RULE",
    "PEND": "PENDED_BY_RULE",
}
GROUP = {
    **dict.fromkeys(
        ("R01", "R02", "R03", "R04", "DUP"), "A"
    ),  # D8: Group A has the duplicate check
    **dict.fromkeys(("R05", "R06", "R07", "R08", "R09", "R10"), "B"),
    **dict.fromkeys(("R11", "R12", "R13"), "C"),  # D8; section 8.3 item 3 now says R11-R13 too
}
H5 = "H5"
H5_REASON = "RJ_LOW_CONFIDENCE_FIELD"
ALL_RULES = "R01-R13"  # the target of a clean-claim case

# H5: the claim fields each rule uses, read from its section 8.3 text (shown on the sheet for
# review). "*" is any service line; for a line rule in PER_LINE only the failing line counts.
FIELDS_USED: dict[str, tuple[str, ...]] = {
    "R01": (),  # the missing field itself, which the cases do not name: not checked
    "R02": (
        "diagnoses",
        "service_lines.*.procedure_code",
        "service_lines.*.place_of_service",
        "service_lines.*.modifiers",
        "service_lines.*.date_of_service",
    ),
    "R03": ("billing_npi", "service_lines.*.rendering_npi", "referring_npi"),
    "R04": ("member_id",),
    "DUP": (
        "member_id",
        "billing_npi",
        "service_lines.*.date_of_service",
        "service_lines.*.procedure_code",
    ),
    "R05": ("member_id", "service_lines.*.date_of_service"),
    "R06": ("billing_npi", "service_lines.*.rendering_npi"),
    "R07": ("received_date", "service_lines.*.date_of_service", "billing_npi"),
    "R08": ("billing_npi", "member_id"),
    "R09": ("referring_npi", "service_lines.*.rendering_npi"),
    "R10": (
        "member_id",
        "service_lines.*.procedure_code",
        "service_lines.*.rendering_npi",
        "service_lines.*.date_of_service",
    ),
    "R11": (
        "service_lines.*.procedure_code",
        "service_lines.*.modifiers",
        "service_lines.*.date_of_service",
    ),
    "R12": (
        "service_lines.*.units",
        "service_lines.*.procedure_code",
        "service_lines.*.date_of_service",
    ),
    "R13": ("service_lines.*.procedure_code", "member_id"),
}
PER_LINE = frozenset({"R12", "R13"})  # R11 pairs two lines, so any line counts

ESI_CODES = frozenset({"62321", "62323", "64483"})
# D-ESI-3 (R14): another block is an ESI or a facet joint injection or nerve block; 64635
# (radiofrequency destruction) is not a block; no sympathetic or trigger point code is in scope.
BLOCK_CODES = ESI_CODES | {"64490", "64493"}

# D-RULE-1's 9 single-claim candidates (V1b findings): the codes a claim needs, and how many such
# lines on one date of service, before the candidate could change the case. Their v2 outcomes are
# not defined yet, so a match is marked for review, not as a conflict.
CANDIDATE_TRIGGERS: dict[str, tuple[frozenset[str], int]] = {
    "POL-BH-001.F3": (frozenset({"96130", "96131", "96136"}), 1),
    "POL-DX-001.F7": (frozenset({"95806"}), 1),
    "POL-DX-002.F2": (frozenset({"95907", "95910"}), 1),
    "POL-DX-002.F3": (frozenset({"95907", "95910"}), 1),
    "POL-DX-002.F4": (frozenset({"95886"}), 1),
    "POL-IMG-001.F2": (frozenset({"70450", "70551", "70553", "72141"}), 2),
    "POL-PAIN-001.F6": (ESI_CODES, 1),
    "POL-PAIN-002.F9": (frozenset({"64490", "64493", "64635"}), 2),
    "POL-SURG-003.F4": (frozenset({"36475", "36478", "37765"}), 2),
}

SITUATIONS = (
    "copay only",
    "deductible not met",
    "deductible partly met",
    "deductible met",
    "coinsurance",
    "out-of-pocket maximum reached",
    "out-of-network PPO",
    "COB secondary",
    "denied line in a multi-line claim",
    "deductible spans lines",
)
EXTRA_SITUATIONS = (
    "copay capped by the allowed amount",
    "billed below the fee schedule",
    "units > 1",
    "pended line",
    "out-of-network copay category (A3)",
    "COB: primary paid >= allowed",
)
AMOUNT_FIELDS = (
    "billed_cents",
    "allowed_cents",
    "contractual_adjustment_cents",
    "deductible_cents",
    "copay_cents",
    "coinsurance_cents",
    "cob_primary_paid_cents",
    "plan_pays_cents",
    "member_pays_cents",
    "balance_bill_exposure_cents",
)
IDENTITY = "plan pays + member pays = max(0, allowed - primary paid)"
CALCULATOR_CHECKS = (
    IDENTITY,
    "allowed <= billed",
    "no negative amounts",
    "member pays <= remaining out-of-pocket maximum",
    "deductible applied <= remaining deductible",
    "copay <= allowed",
    "denied or pended lines pay 0",
    "integer cents only",
    "totals = sum of lines (A8)",
    "accumulators after = before + the claim's cost share (A5)",
)
RULES_CHECKS = (
    "exactly one expected outcome",
    "status matches the outcome",
    "targeted rule exists in section 8.3",
    "failure matches section 8.3",
    "line number matches the rule's group",
    "Group A stops the claim",
    "Group B stops the claim",
    "outcome follows the group order",
    "H5: a failure on a low-confidence field becomes REJECT",
    "H5 applied without a low-confidence field the rule uses",
    "R14 (D-ESI-3) would deny this ESI line",
    "R15 (D-DX-1) would deny this line",
)


@dataclass(frozen=True)
class Finding:
    kind: str  # violation | conflict | review
    check: str
    case_id: str
    line_no: int | None = None
    detail: str = ""  # may hold expected amounts: CSV only, never on the sheet


# --- INSTRUCTIONS.md and README ---------------------------------------------------------------


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    text: str  # the rule's words (table "Rule" column, or the duplicate bullet)
    outcomes: frozenset[str]
    reasons: frozenset[str]
    quote: str  # the full table row or bullet, word for word


@dataclass(frozen=True)
class Spec:
    rules: dict[str, RuleSpec]
    order: list[str]  # section 8.3 evaluation order, items 1-4
    h5: str
    table_head: tuple[str, str]
    calc_steps: dict[int, str]
    cost_share: dict[str, str]  # COPAY, DEDUCTIBLE_COINSURANCE, OUT_OF_NETWORK
    calc_notes: list[str]
    calc_intro: list[str]  # section 8.6 paragraphs before step 1 (inputs, rounding, order)


def _section(lines: Sequence[str], start: str, end: str) -> list[str]:
    first = next(k for k, line in enumerate(lines) if line.startswith(start))
    last = next(k for k in range(first + 1, len(lines)) if lines[k].startswith(end))
    return list(lines[first + 1 : last])


def parse_instructions(text: str) -> Spec:
    """Section 8.3 (rules) and 8.6 (calculator), word for word; wrapped lines are joined."""
    lines = text.splitlines()
    rules_part = _section(lines, "### 8.3", "### 8.4")
    order: list[str] = []
    rules: dict[str, RuleSpec] = {}
    table_head = ("", "")
    in_order, bullet = False, None
    for line in rules_part:
        if line.startswith("**Evaluation order**"):
            in_order = True
            continue
        if line.startswith("| ID |"):
            in_order, table_head = False, (line, "")
            continue
        if line.startswith("|---") and table_head[0] and not table_head[1]:
            table_head = (table_head[0], line)
            continue
        if in_order:
            item = re.match(r"^\d\. (.*)$", line)
            if item:
                order.append(item.group(1).strip())
            elif line.strip() and order:
                order[-1] += " " + line.strip()
            continue
        row = re.match(r"^\| (R\d{2}) \| (.*?) \| (.*?) \| (.*?) \|$", line)
        if row:
            rule_id, words, outcome, reason = row.groups()
            rules[rule_id] = RuleSpec(
                rule_id,
                words,
                frozenset(re.findall(r"REJECT|DENY|PEND", outcome)),
                frozenset(re.findall(r"`([A-Z_]+)`", reason)),
                line,
            )
            continue
        if line.startswith("- **Duplicate claims**"):
            bullet = line[2:].strip()
        elif bullet is not None and line.startswith("  ") and line.strip():
            bullet += " " + line.strip()
        elif bullet is not None:
            words = re.search(r"\((.*?)\)", bullet)
            rules["DUP"] = RuleSpec(
                "DUP",
                words.group(1) if words else bullet,
                frozenset(re.findall(r"REJECT|DENY|PEND", bullet)),
                frozenset(re.findall(r"`([A-Z_]+)`", bullet)),
                bullet,
            )
            bullet = None
    h5 = next(item for item in order if item.startswith("**H5 conversion**"))

    steps: dict[int, str] = {}
    cost_share: dict[str, str] = {}
    notes: list[str] = []
    intro: list[str] = []
    current: tuple[str, Any] | None = None
    for line in _section(lines, "### 8.6", "### 8.7"):
        step = re.match(r"^(\d)\. (.*)$", line)
        sub = re.match(r"^   - (.*)$", line)
        note = re.match(r"^- (.*)$", line)
        if not steps and not step:
            if line.strip() and current == ("intro", 0):
                intro[-1] += " " + line.strip()
            elif line.strip():
                intro.append(line.strip())
            current = ("intro", 0) if line.strip() else None
            continue
        if step:
            steps[int(step.group(1))] = step.group(2).strip()
            current = ("step", int(step.group(1)))
        elif sub:
            words = sub.group(1).strip()
            key = (
                "COPAY"
                if words.startswith("`COPAY`")
                else "DEDUCTIBLE_COINSURANCE"
                if words.startswith("`DEDUCTIBLE_COINSURANCE`")
                else "OUT_OF_NETWORK"
            )
            cost_share[key] = words
            current = ("cost", key)
        elif note:
            notes.append(note.group(1).strip())
            current = ("note", len(notes) - 1)
        elif line.startswith(" ") and line.strip() and current:
            kind, key = current
            if kind == "step":
                steps[key] += " " + line.strip()
            elif kind == "cost":
                cost_share[key] += " " + line.strip()
            else:
                notes[key] += " " + line.strip()
        elif not line.strip():
            current = None
    return Spec(rules, order, h5, table_head, steps, cost_share, notes, intro)


def readme_assumptions(text: str) -> list[tuple[str, str]]:
    """(ID, text) of the golden assumptions tables, word for word."""
    return re.findall(r"^\| (A-R\d+|A\d+) \| (.*) \|$", text, re.MULTILINE)


def load_cases(folder: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted((GOLDEN / folder).glob("*.json")):
        cases += json.loads(path.read_text(encoding="utf-8")).get("cases", [])
    return cases


# --- calculator checks ------------------------------------------------------------------------


def _num(row: Mapping[str, Any], field: str) -> float:
    value = row.get(field, 0)
    return value if isinstance(value, int | float) and not isinstance(value, bool) else 0


def _cost_share(row: Mapping[str, Any]) -> float:
    return _num(row, "deductible_cents") + _num(row, "copay_cents") + _num(row, "coinsurance_cents")


def check_calculator_case(case: Mapping[str, Any], plan: Any) -> list[Finding]:
    """Every listed rule on the expected amounts of one case. `plan` is a curated PlanConfig."""
    case_id, given, expected = case["case_id"], case["given"], case["expected"]
    found: list[Finding] = []

    def bad(check: str, line_no: int | None, detail: str) -> None:
        found.append(Finding("violation", check, case_id, line_no, detail))

    lines = sorted(expected["amounts"]["lines"], key=lambda a: a["line_no"])
    totals = expected["amounts"]["totals"]
    for row, line_no in [*((a, a["line_no"]) for a in lines), (totals, None)]:
        for field in AMOUNT_FIELDS:
            value = row.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool):
                bad("integer cents only", line_no, f"{field} = {value!r}")
            elif value < 0:
                bad("no negative amounts", line_no, f"{field} = {value}")
    for field, value in (expected.get("accumulators_after") or {}).items():
        if not isinstance(value, int) or isinstance(value, bool):
            bad("integer cents only", None, f"accumulators_after.{field} = {value!r}")
        elif value < 0:
            bad("no negative amounts", None, f"accumulators_after.{field} = {value}")
    terms = plan.in_network if given["network"] == "IN_NETWORK" else plan.out_of_network
    if terms is None:
        bad(IDENTITY, None, f"{plan.plan_id} has no {given['network']} terms")
        return found
    before = given["accumulators"]
    remaining_deductible = max(0, terms.deductible_cents - before["deductible_met_cents"])
    remaining_oop = max(0, terms.oop_max_cents - before["oop_met_cents"])
    start_deductible, start_oop = remaining_deductible, remaining_oop
    decisions = {line["line_no"]: line["decision"] for line in given["lines"]}
    approved = [a for a in lines if decisions.get(a["line_no"]) == "APPROVE"]
    owed = 0.0  # sum over approved lines of max(0, allowed - primary paid)
    for a in lines:
        n = a["line_no"]
        if decisions.get(n) != "APPROVE":
            paid = [f for f in AMOUNT_FIELDS if f != "billed_cents" and _num(a, f) != 0]
            if paid:
                bad(
                    "denied or pended lines pay 0",
                    n,
                    f"{decisions.get(n)}: " + ", ".join(f"{f} = {a[f]}" for f in paid),
                )
            continue
        allowed, primary = _num(a, "allowed_cents"), _num(a, "cob_primary_paid_cents")
        target = max(0, allowed - primary)
        owed += target
        paid_total = _num(a, "plan_pays_cents") + _num(a, "member_pays_cents")
        if paid_total != target:
            bad(IDENTITY, n, f"{paid_total} != max(0, {allowed} - {primary}) = {target}")
        if allowed > _num(a, "billed_cents"):
            bad("allowed <= billed", n, f"allowed {allowed} > billed {a.get('billed_cents')}")
        if _num(a, "copay_cents") > allowed:
            bad("copay <= allowed", n, f"copay {a.get('copay_cents')} > allowed {allowed}")
        if _num(a, "deductible_cents") > remaining_deductible:
            bad(
                "deductible applied <= remaining deductible",
                n,
                f"{a.get('deductible_cents')} > remaining {remaining_deductible}",
            )
        if _num(a, "member_pays_cents") > remaining_oop:
            bad(
                "member pays <= remaining out-of-pocket maximum",
                n,
                f"{a.get('member_pays_cents')} > remaining {remaining_oop}",
            )
        remaining_deductible = max(0, remaining_deductible - _num(a, "deductible_cents"))
        remaining_oop = max(0, remaining_oop - _cost_share(a))  # A5: the whole cost share counts

    for field in AMOUNT_FIELDS:
        summed = sum(_num(a, field) for a in lines)
        if _num(totals, field) != summed:
            bad(
                "totals = sum of lines (A8)",
                None,
                f"{field}: total {totals.get(field)} != {summed}",
            )
    paid_total = _num(totals, "plan_pays_cents") + _num(totals, "member_pays_cents")
    if paid_total != owed:
        bad(IDENTITY, None, f"total {paid_total} != sum of max(0, allowed - primary) = {owed}")
    if _num(totals, "deductible_cents") > start_deductible:
        bad(
            "deductible applied <= remaining deductible",
            None,
            f"total {totals.get('deductible_cents')} > remaining {start_deductible}",
        )
    if _num(totals, "member_pays_cents") > start_oop:
        bad(
            "member pays <= remaining out-of-pocket maximum",
            None,
            f"total {totals.get('member_pays_cents')} > remaining {start_oop}",
        )
    if _num(totals, "copay_cents") > _num(totals, "allowed_cents"):
        bad("copay <= allowed", None, "total copay > total allowed")
    after = expected.get("accumulators_after")
    if after is not None:
        want = (
            before["deductible_met_cents"] + sum(_num(a, "deductible_cents") for a in approved),
            before["oop_met_cents"] + sum(_cost_share(a) for a in approved),
        )
        got = (after.get("deductible_met_cents"), after.get("oop_met_cents"))
        if got != want:
            bad(
                "accumulators after = before + the claim's cost share (A5)",
                None,
                f"after {got} != before + claim {want}",
            )
    return found


# --- rules checks -----------------------------------------------------------------------------


def _uses_field(path: str, pattern: str, rule_id: str, line_no: int | None) -> bool:
    """Whether a confidence path (0-based indexes, A-R9) is one of the rule's fields."""
    regex = re.escape(pattern).replace(r"\*", r"(\d+)")
    found = re.match(rf"^{regex}(?:\..*)?$", path)
    if not found:
        return False
    if rule_id in PER_LINE and line_no is not None and "*" in pattern:
        return int(found.group(1)) == line_no - 1
    return True


def derived_outcome(
    failures: Sequence[Mapping[str, Any]], line_outcomes: Sequence[Mapping[str, Any]] | None
) -> str:
    """The claim outcome the failures imply: any REJECT; else Group B DENY over PEND; else
    Group C (DENY when every line is denied); else PASS."""
    if any(f["outcome"] == "REJECT" for f in failures):
        return "REJECT"
    group_b = [f["outcome"] for f in failures if GROUP.get(f["rule_id"]) == "B"]
    if group_b:
        return "DENY" if "DENY" in group_b else "PEND"
    if line_outcomes and all(o["outcome"] == "DENY" for o in line_outcomes):
        return "DENY"
    return "PASS"


def check_rules_case(
    case: Mapping[str, Any],
    spec: Spec,
    fields_used: Mapping[str, tuple[str, ...]] = FIELDS_USED,
) -> list[Finding]:
    """Every rules check on one case; `fields_used` is the H5 field mapping."""
    case_id, expected = case["case_id"], case["expected"]
    found: list[Finding] = []

    def bad(check: str, line_no: int | None, detail: str) -> None:
        found.append(Finding("violation", check, case_id, line_no, detail))

    outcome = expected.get("claim_outcome")
    if not isinstance(outcome, str) or outcome not in STATUS:
        bad("exactly one expected outcome", None, f"claim_outcome = {outcome!r}")
    elif expected.get("status") != STATUS[outcome]:
        bad("status matches the outcome", None, f"{outcome} with status {expected.get('status')}")
    for target in case.get("rules", []):
        if target not in spec.rules and target not in (H5, ALL_RULES):
            bad("targeted rule exists in section 8.3", None, target)
    failures = expected.get("failures") or []
    groups = set()
    for f in failures:
        rule = spec.rules.get(f["rule_id"])
        line_no = f.get("line_no")
        if rule is None:
            bad("failure matches section 8.3", line_no, f"unknown rule {f['rule_id']}")
            continue
        group = GROUP[f["rule_id"]]
        groups.add(group)
        if f["reason_code"] == H5_REASON:
            matches = f["outcome"] == "REJECT"
        else:
            matches = f["outcome"] in rule.outcomes and f["reason_code"] in rule.reasons
        if not matches:
            bad(
                "failure matches section 8.3",
                line_no,
                f"{f['rule_id']} {f['outcome']} {f['reason_code']}",
            )
        if (group == "C") != (line_no is not None):
            bad("line number matches the rule's group", line_no, f"{f['rule_id']} in group {group}")
    if "A" in groups and groups & {"B", "C"}:
        bad("Group A stops the claim", None, "Group B or C failures listed after a Group A one")
    if "B" in groups and "C" in groups:
        bad("Group B stops the claim", None, "Group C failures listed after a Group B one")
    implied = derived_outcome(failures, expected.get("line_outcomes"))
    if outcome in STATUS and implied != outcome:
        bad(
            "outcome follows the group order", None, f"failures give {implied}, case says {outcome}"
        )
    confidences = case["given"].get("field_confidences") or {}
    low = [path for path, value in confidences.items() if value < CONFIDENCE_MIN]
    for f in failures:
        patterns = fields_used.get(f["rule_id"])
        if not patterns:
            continue
        uses = any(
            _uses_field(path, pattern, f["rule_id"], f.get("line_no"))
            for path in low
            for pattern in patterns
        )
        converted = f["reason_code"] == H5_REASON
        if uses and not converted:
            bad(
                "H5: a failure on a low-confidence field becomes REJECT",
                f.get("line_no"),
                f"{f['rule_id']} uses {low}",
            )
        if converted and not uses:
            bad(
                "H5 applied without a low-confidence field the rule uses",
                f.get("line_no"),
                f"{f['rule_id']}; low fields {low}",
            )
    return found


def _lines(claim: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {line["line_no"]: line for line in claim.get("service_lines") or []}


def _line_diagnoses(claim: Mapping[str, Any], line: Mapping[str, Any]) -> tuple[str, ...]:
    letters = {chr(ord("A") + k): d for k, d in enumerate(claim.get("diagnoses") or [])}
    return tuple(str(letters[p]) for p in line.get("diagnosis_pointers") or [] if p in letters)


def decision_conflicts(
    case: Mapping[str, Any], supported: Callable[[str, tuple[str, ...]], bool | None]
) -> list[Finding]:
    """Lines expected to pass that a decided v2 rule would deny: R15 (D-DX-1, diagnoses do not
    satisfy the billing article) and R14 (D-ESI-3, an ESI with another block on its date)."""
    outcomes = case["expected"].get("line_outcomes")
    if not outcomes:
        return []
    claim = case["given"]["claim"]
    lines = _lines(claim)
    notes = (claim.get("clinical_notes") or "").lower()
    found = []
    for outcome in outcomes:
        line = lines.get(outcome["line_no"])
        if outcome["outcome"] == "DENY" or line is None:
            continue
        code, day = str(line.get("procedure_code")), line.get("date_of_service")
        diagnoses = _line_diagnoses(claim, line)
        if supported(code, diagnoses) is False:
            found.append(
                Finding(
                    "conflict",
                    "R15 (D-DX-1) would deny this line",
                    case["case_id"],
                    outcome["line_no"],
                    f"{code} with {', '.join(diagnoses) or 'no diagnosis'}",
                )
            )
        if code in ESI_CODES and "synovial cyst" not in notes:
            blocks = [
                str(other.get("procedure_code"))
                for other in lines.values()
                if other is not line
                and str(other.get("procedure_code")) in BLOCK_CODES
                and other.get("date_of_service") == day
            ]
            if blocks:
                found.append(
                    Finding(
                        "conflict",
                        "R14 (D-ESI-3) would deny this ESI line",
                        case["case_id"],
                        outcome["line_no"],
                        f"{code} with {', '.join(blocks)} on {day}",
                    )
                )
    return found


def candidate_reviews(case: Mapping[str, Any]) -> list[Finding]:
    """D-RULE-1 single-claim candidates whose codes the claim carries (outcome not defined)."""
    by_day: dict[Any, list[str]] = defaultdict(list)
    for line in _lines(case["given"]["claim"]).values():
        by_day[line.get("date_of_service")].append(str(line.get("procedure_code")))
    found = []
    for finding_id, (codes, minimum) in CANDIDATE_TRIGGERS.items():
        for day, day_codes in sorted(by_day.items(), key=lambda item: str(item[0])):
            hits = [c for c in day_codes if c in codes]
            if len(hits) >= minimum:
                found.append(
                    Finding(
                        "review",
                        f"D-RULE-1 candidate {finding_id} may change this case",
                        case["case_id"],
                        None,
                        f"{', '.join(hits)} on {day}",
                    )
                )
                break
    return found


# --- coverage ---------------------------------------------------------------------------------


def situations(
    case: Mapping[str, Any], plan: Any, benefit: Callable[[str], tuple[str, int | None]]
) -> set[str]:
    """The cost-share situations a calculator case exercises. `benefit` gives a category's
    (cost_share_rule, copay_cents) for the case's plan. Uses expected values: for coverage and
    sampling only, never shown on the sheet."""
    given, expected = case["given"], case["expected"]
    network = given["network"]
    terms = plan.in_network if network == "IN_NETWORK" else plan.out_of_network
    amounts = {a["line_no"]: a for a in expected["amounts"]["lines"]}
    lines = given["lines"]
    approved = [line for line in lines if line["decision"] == "APPROVE"]
    rule = {line["line_no"]: benefit(line["benefit_category"]) for line in approved}
    found: set[str] = set()
    if approved and network == "IN_NETWORK" and all(r == "COPAY" for r, _ in rule.values()):
        found.add("copay only")
    deductible_lines = [
        line
        for line in approved
        if network != "IN_NETWORK" or rule[line["line_no"]][0] == "DEDUCTIBLE_COINSURANCE"
    ]
    if deductible_lines and terms is not None:
        met = given["accumulators"]["deductible_met_cents"]
        if met == 0:
            found.add("deductible not met")
        elif met < terms.deductible_cents:
            found.add("deductible partly met")
        else:
            found.add("deductible met")
    if any(amounts[line["line_no"]]["coinsurance_cents"] > 0 for line in approved):
        found.add("coinsurance")
    after = expected.get("accumulators_after") or {}
    if terms is not None and after.get("oop_met_cents", 0) >= terms.oop_max_cents:
        found.add("out-of-pocket maximum reached")
    if network == "OUT_OF_NETWORK" and plan.plan_type == "PPO":
        found.add("out-of-network PPO")
    if given.get("other_coverage"):
        found.add("COB secondary")
    if len(lines) >= 2 and any(line["decision"] == "DENY" for line in lines):
        found.add("denied line in a multi-line claim")
    if sum(amounts[line["line_no"]]["deductible_cents"] > 0 for line in approved) >= 2:
        found.add("deductible spans lines")
    fees = given.get("fee_schedule") or {}
    fee_key = "inn_allowed_cents" if network == "IN_NETWORK" else "oon_allowed_cents"
    for line in approved:
        a = amounts[line["line_no"]]
        cost_rule, copay = rule[line["line_no"]]
        fee = fees.get(line["procedure_code"], {}).get(fee_key)
        if cost_rule == "COPAY" and copay and a["copay_cents"] == a["allowed_cents"] < copay:
            found.add("copay capped by the allowed amount")
        if fee is not None and line["billed_cents"] < fee * line["units"]:
            found.add("billed below the fee schedule")
        if network != "IN_NETWORK" and cost_rule == "COPAY":
            found.add("out-of-network copay category (A3)")
        if a["cob_primary_paid_cents"] and a["cob_primary_paid_cents"] >= a["allowed_cents"]:
            found.add("COB: primary paid >= allowed")
    if any(line["units"] > 1 for line in lines):
        found.add("units > 1")
    if any(line["decision"] == "PEND" for line in lines):
        found.add("pended line")
    return found


def rules_coverage(cases: Sequence[Mapping[str, Any]]) -> list[tuple[str, int]]:
    """Golden cases per rule, rule variant and later rule (R14, R15, D-RULE-1 candidates)."""
    from scripts.verify.policy_sources import FINDINGS

    def targets(case: Mapping[str, Any]) -> set[str]:
        return set(case.get("rules", []))

    def failing(case: Mapping[str, Any], rule: str, reason: str | None = None) -> bool:
        return any(
            f["rule_id"] == rule and (reason is None or f["reason_code"] == reason)
            for f in case["expected"]["failures"]
        )

    def h5_in(case: Mapping[str, Any], group: str) -> bool:
        return any(
            f["reason_code"] == H5_REASON and GROUP.get(f["rule_id"]) == group
            for f in case["expected"]["failures"]
        )

    def group_b(case: Mapping[str, Any]) -> set[str]:
        return {
            f["outcome"] for f in case["expected"]["failures"] if GROUP.get(f["rule_id"]) == "B"
        }

    def all_lines_denied(case: Mapping[str, Any]) -> bool:
        outcomes = case["expected"]["line_outcomes"]
        return bool(outcomes) and all(o["outcome"] == "DENY" for o in outcomes)

    def bypass(case: Mapping[str, Any]) -> bool:
        return any(
            "NCCI_BYPASS" in (o.get("flags") or []) for o in case["expected"]["line_outcomes"] or []
        )

    rows = [
        (f"{rule}: cases that target it", sum(rule in targets(c) for c in cases)) for rule in GROUP
    ]
    rows += [
        (f"{H5}: cases that target it", sum(H5 in targets(c) for c in cases)),
        ("Clean claim: every rule passes", sum(ALL_RULES in targets(c) for c in cases)),
        (
            "R06 provider not found -> REJECT",
            sum(failing(c, "R06", "RJ_PROVIDER_NOT_FOUND") for c in cases),
        ),
        (
            "R06 enrollment pending -> PEND",
            sum(failing(c, "R06", "PD_PROVIDER_ENROLLMENT") for c in cases),
        ),
        (
            "R08 out of network, not covered -> DENY",
            sum(failing(c, "R08", "DN_OUT_OF_NETWORK") for c in cases),
        ),
        (
            "R08 out of network, covered -> PASS with flag OON",
            sum("OON" in c["expected"]["flags"] for c in cases),
        ),
        ("R11 column-2 line denied", sum(failing(c, "R11", "DN_NCCI_BUNDLED") for c in cases)),
        ("R11 bypass modifier -> flag NCCI_BYPASS", sum(bypass(c) for c in cases)),
        ("H5 on a Group A rule", sum(h5_in(c, "A") for c in cases)),
        ("H5 on a Group B rule", sum(h5_in(c, "B") for c in cases)),
        ("H5 on a Group C rule", sum(h5_in(c, "C") for c in cases)),
        (
            "Group B: DENY and PEND together (DENY wins)",
            sum({"DENY", "PEND"} <= group_b(c) for c in cases),
        ),
        (
            "Group B: REJECT with DENY or PEND (REJECT wins, D8)",
            sum("REJECT" in group_b(c) and bool(group_b(c) & {"DENY", "PEND"}) for c in cases),
        ),
        ("Group C: every line denied -> claim DENY", sum(all_lines_denied(c) for c in cases)),
        (
            "R14 (D-ESI-3): ESI with another block on the same date",
            sum("R14" in targets(c) for c in cases),
        ),
        (
            "R15 (D-DX-1): diagnoses do not satisfy the billing article",
            sum("R15" in targets(c) for c in cases),
        ),
    ]
    changes = {f.finding_id: f.change for f in FINDINGS}
    rows += [
        (f"D-RULE-1 candidate {fid}: {changes[fid]}", sum(fid in targets(c) for c in cases))
        for fid in CANDIDATE_TRIGGERS
    ]
    return rows


# --- samples ----------------------------------------------------------------------------------


def sample_rules(
    cases: Iterable[Mapping[str, Any]], seed: int = SEED, size: int = SAMPLE_SIZE
) -> list[Any]:
    """One H5 conversion case, then cases of different rules (a case's first target), drawn with
    one seeded generator from sorted lists; filled with other cases only if rules run out."""
    rng = random.Random(seed)
    ordered = sorted(cases, key=lambda c: c["case_id"])
    h5_cases = [c for c in ordered if H5 in c.get("rules", [])]
    picked = [rng.choice(h5_cases)] if h5_cases else []
    used = {picked[0]["rules"][0]} if picked else set()
    by_rule: dict[str, list[Any]] = defaultdict(list)
    for case in ordered:
        if H5 not in case.get("rules", []):
            by_rule[case["rules"][0]].append(case)
    rules = sorted(r for r in by_rule if r not in used)
    for rule in rng.sample(rules, min(size - len(picked), len(rules))):
        picked.append(rng.choice(by_rule[rule]))
    if len(picked) < size:
        rest = [c for c in ordered if c not in picked]
        picked += rng.sample(rest, min(size - len(picked), len(rest)))
    return picked


def sample_calculator(
    found: Mapping[str, set[str]], seed: int = SEED
) -> tuple[list[str], list[str]]:
    """(case IDs, situations with no case): one case per situation in SITUATIONS order, never
    the same case twice, drawn with one seeded generator from sorted lists."""
    rng = random.Random(seed)
    picked: list[str] = []
    short: list[str] = []
    for situation in SITUATIONS:
        pool = sorted(
            cid for cid, names in found.items() if situation in names and cid not in picked
        )
        if pool:
            picked.append(rng.choice(pool))
        else:
            short.append(situation)
    return picked, short


def blind_view(case: Mapping[str, Any]) -> dict[str, Any]:
    """What the sheet may show: the inputs, never the expected values, worked steps or title."""
    return {
        "case_id": case["case_id"],
        "rules": case.get("rules"),
        "assumptions": case.get("assumptions"),
        "given": case["given"],
    }


def shown_cases(items: Sequence[Finding], hidden: Collection[str]) -> str:
    """The case IDs of findings, for the sheet. A violation or conflict comes from a case's
    expected values, so on a case in the sheet's sample it is counted, not named, to keep the
    sheet blind; review findings come from the inputs only and are always named."""
    named = [
        f.case_id + (f" (line {f.line_no})" if f.line_no is not None else "")
        for f in items
        if f.kind == "review" or f.case_id not in hidden
    ]
    masked = sum(f.kind != "review" and f.case_id in hidden for f in items)
    if masked:
        named.append(f"{masked} in this sheet's sample (named in {CHECKS_FILE})")
    return ", ".join(named) or "-"


def cob_total_differs(case: Mapping[str, Any]) -> bool:
    """Whether the sum over the approved lines of max(0, allowed - primary paid) differs from
    max(0, total allowed - total primary paid). Only a claim with lines where the primary paid
    more than allowed and lines where it paid less makes the two differ."""
    decisions = {line["line_no"]: line["decision"] for line in case["given"]["lines"]}
    pairs = [
        (_num(a, "allowed_cents"), _num(a, "cob_primary_paid_cents"))
        for a in case["expected"]["amounts"]["lines"]
        if decisions.get(a["line_no"]) == "APPROVE"
    ]
    per_line = sum(max(0, allowed - primary) for allowed, primary in pairs)
    whole = max(0, sum(a for a, _ in pairs) - sum(p for _, p in pairs))
    return per_line != whole


# --- the review sheet ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Reference:
    """What a rules case is decided with: the golden fixture plus curated and raw lookups."""

    members: Mapping[str, Mapping[str, Any]]
    providers: Mapping[str, Mapping[str, Any]]
    networks: Mapping[tuple[str, str], bool]
    authorizations: Sequence[Mapping[str, Any]]
    existing_claims: Sequence[Mapping[str, Any]]
    curated: Any
    icd10: Mapping[str, str]
    pos: Mapping[str, str]
    ncci: Sequence[Any]
    ncci_missing: frozenset[str]  # codes whose NCCI file is not extracted
    mue: Mapping[str, Any]


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _show(container: Mapping[str, Any], key: str) -> str:
    """A claim value as received: absent, null and empty are told apart (R01 cases)."""
    if key not in container:
        return "(missing)"
    value = container[key]
    if value is None:
        return "(null)"
    if value == "" or value == []:
        return "(empty)"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def render_rules_case(
    number: int, view: Mapping[str, Any], ref: Reference, spec: Spec
) -> list[str]:
    given, curated = view["given"], ref.curated
    claim = given["claim"]
    targets = view.get("rules") or []
    out = [f"### Rules case {number} ({view['case_id']})", ""]
    out += ["Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):", ""]
    rows = [spec.rules[t].quote for t in targets if t in spec.rules and t != "DUP"]
    if rows:
        out += [*spec.table_head, *rows, ""]
    if "DUP" in targets:
        out += [f"> {spec.rules['DUP'].quote}", ""]
    if H5 in targets:
        out += [f"> 4. {spec.h5}", ""]
    if ALL_RULES in targets:
        out += ["Every rule in the section 8.3 table.", ""]

    out += [f"**Claim** (source format {given.get('source_format')}):", ""]
    out += ["| Field | Value |", "|---|---|"]
    for key in ("claim_id", "member_id"):
        out.append(f"| {key} | {_cell(_show(claim, key))} |")
    patient = claim.get("patient") if isinstance(claim.get("patient"), Mapping) else None
    if patient is None:
        out.append(f"| patient | {_cell(_show(claim, 'patient'))} |")
    else:
        for key in ("first_name", "last_name", "date_of_birth", "sex"):
            out.append(f"| patient.{key} | {_cell(_show(patient, key))} |")
        address = patient.get("address")
        shown = (
            ", ".join(_show(address, k) for k in ("line1", "city", "state", "zip_code"))
            if isinstance(address, Mapping)
            else _show(patient, "address")
        )
        out.append(f"| patient.address | {_cell(shown)} |")
    for key in (
        "subscriber_is_patient",
        "billing_npi",
        "billing_tin",
        "referring_npi",
        "prior_auth_number",
        "received_date",
        "frequency_code",
        "other_coverage",
        "clinical_notes",
    ):
        out.append(f"| {key} | {_cell(_show(claim, key))} |")

    diagnoses = claim.get("diagnoses") if isinstance(claim.get("diagnoses"), list) else []
    letters = {chr(ord("A") + k): str(d) for k, d in enumerate(diagnoses)}
    out += ["", "**Diagnoses:**", "", "| Pointer | Code | In ICD-10-CM FY2027 |", "|---|---|---|"]
    if not diagnoses:
        out.append(f"| - | {_cell(_show(claim, 'diagnoses'))} | - |")
    for pointer, code in letters.items():
        key = code.replace(".", "").upper()
        lookup = f"yes: {ref.icd10[key]}" if key in ref.icd10 else "no"
        out.append(f"| {pointer} | {_cell(code)} | {_cell(lookup)} |")

    lines = [line for line in claim.get("service_lines") or [] if isinstance(line, Mapping)]
    out += [
        "",
        "**Service lines:**",
        "",
        "| Line | Date of service | Place of service | Code | Modifiers "
        "| Diagnoses (pointer = code) "
        "| Units | Charge (cents) | Rendering NPI |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for line in lines:
        pointers = line.get("diagnosis_pointers")
        shown = (
            ", ".join(f"{p} = {letters.get(p, 'no such diagnosis')}" for p in pointers)
            if isinstance(pointers, list) and pointers
            else _show(line, "diagnosis_pointers")
        )
        out.append(
            f"| {_cell(_show(line, 'line_no'))} | {_cell(_show(line, 'date_of_service'))} | "
            f"{_cell(_show(line, 'place_of_service'))} | {_cell(_show(line, 'procedure_code'))} | "
            f"{_cell(_show(line, 'modifiers'))} | {_cell(shown)} | {_cell(_show(line, 'units'))} | "
            f"{_cell(_show(line, 'charge_cents'))} | {_cell(_show(line, 'rendering_npi'))} |"
        )

    codes = sorted(
        {str(line.get("procedure_code")) for line in lines if line.get("procedure_code")}
    )
    out += ["", "**Code lookups:**", ""]
    for code in codes:
        scope = curated.scope.get(code)
        out.append(
            f"- Procedure code {code}: in the code table; policy {scope.policy_id or 'none'}; "
            f"possible categories {', '.join(scope.candidate_categories)}; "
            f"{curated.descriptions.get(code, '')}"
            if scope
            else f"- Procedure code {code}: not in the code table"
        )
    for place in sorted(
        {str(line.get("place_of_service")) for line in lines if line.get("place_of_service")}
    ):
        name = ref.pos.get(place)
        out.append(
            f"- Place of service {place}: {name}"
            if name
            else f"- Place of service {place}: not a code"
        )
    out.append(f"- NCCI bypass modifiers: {', '.join(sorted(curated.bypass_modifiers))}")

    confidences = given.get("field_confidences") or {}
    out += ["", "**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):", ""]
    out += [f"- {path} = {value}" for path, value in sorted(confidences.items())] or ["- none"]

    out += ["", "**Reference data:**", ""]
    member_id = claim.get("member_id")
    member = ref.members.get(member_id) if isinstance(member_id, str) else None
    if member is None:
        out.append(f"- Member {member_id}: not in the member records")
    else:
        out.append(
            f"- Member {member_id}: plan {member['plan_id']}, coverage {member['coverage_start']} "
            f"to {member.get('coverage_end') or 'open'}"
        )
        plan = curated.plans[member["plan_id"]]
        excluded = sorted(e.procedure_code for e in curated.exclusions if e.plan_id == plan.plan_id)
        out.append(
            f"- Plan {plan.plan_id} ({plan.plan_type}): filing window "
            f"{plan.filing_window_inn_days} "
            f"days in network, {plan.filing_window_oon_days} days out of network; out-of-network "
            f"care covered: {'yes' if plan.oon_covered else 'no'}; referral required for: "
            f"{', '.join(sorted(plan.referral_required_provider_types)) or 'none'}; fixed "
            f"exclusions: {', '.join(excluded) or 'none'}"
        )
        for code in codes:
            scope = curated.scope.get(code)
            for category in scope.candidate_categories if scope else ():
                b = curated.benefit(plan.plan_id, category)
                share = (
                    f"copay {b.copay_cents}" if b.cost_share_rule == "COPAY" else b.cost_share_rule
                )
                out.append(
                    f"- Benefit {plan.plan_id} / {category} (code {code}): covered "
                    f"{'yes' if b.covered else 'no'}, prior authorization "
                    f"{'required' if b.auth_required else 'not required'}, visit limit "
                    f"{b.visit_limit or 'none'}, {share}"
                )
    npis = [("Billing NPI", claim.get("billing_npi"))]
    npis += [
        ("Rendering NPI", n) for n in sorted({str(line.get("rendering_npi")) for line in lines})
    ]
    npis += [("Referring NPI", claim.get("referring_npi"))] if claim.get("referring_npi") else []
    for label, npi in npis:
        provider = ref.providers.get(str(npi))
        out.append(
            f"- {label} {npi}: {provider['name']}, {provider['provider_type']}, "
            f"{provider['enrollment_status']}"
            if provider
            else f"- {label} {npi}: not in the provider records"
        )
    if member is not None:
        row = ref.networks.get((str(claim.get("billing_npi")), member["plan_id"]))
        state = "no row" if row is None else "in network" if row else "out of network"
        out.append(
            f"- Network row for billing NPI {claim.get('billing_npi')} and plan "
            f"{member['plan_id']}: {state} (A-R1)"
        )
    additions = given.get("reference_additions") or {}
    auths = [
        a
        for a in [*ref.authorizations, *additions.get("authorizations", [])]
        if a.get("member_id") == member_id
    ]
    out += [
        f"- Authorization {a['auth_number']}: provider {a['provider_npi']}, code "
        f"{a['procedure_code']}, "
        f"{a['start_date']} to {a['end_date']}, units {a['units_approved'] or 'no limit'}"
        for a in auths
    ] or ["- Authorizations for this member: none"]
    existing = [
        e
        for e in [*ref.existing_claims, *additions.get("existing_claims", [])]
        if e.get("member_id") == member_id
    ]
    out += [
        f"- Existing claim {e['claim_id']}: billing NPI {e['billing_npi']}, date of service "
        f"{e['date_of_service']}, code {e['procedure_code']}, status {e['status']}"
        for e in existing
    ] or ["- Existing claims for this member: none"]
    days = [d for d in (_date(line.get("date_of_service")) for line in lines) if d]
    pairs = [
        p
        for p in ref.ncci
        if p.column1 in codes and p.column2 in codes and any(p.active_on(d) for d in days)
    ]
    out += [
        f"- NCCI pair {p.column1} / {p.column2} (column-2 code {p.column2}): modifier indicator "
        f"{p.modifier_indicator}, effective {p.effective_date}"
        for p in pairs
    ] or ["- NCCI pairs among the claim's codes: none found"]
    missing = sorted(set(codes) & ref.ncci_missing)
    if missing:
        out.append(
            f"- NCCI pairs whose column-1 code is {', '.join(missing)} are not available here: "
            "file f1 is not extracted; look them up in "
            "data/raw/ncci-ptp/ccipra-v323r0-f1/ccipra-v323r0-f1.xlsx"
        )
    for code in codes:
        mue = ref.mue.get(code)
        if mue:
            out.append(
                f"- MUE {code}: at most {mue.max_units} unit{'' if mue.max_units == 1 else 's'} "
                f"per date of service ({mue.adjudication_indicator})"
            )
    out += [
        "",
        "| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) "
        "| Notes |",
        "|---|---|",
        "|  |  |",
        "",
    ]
    return out


def render_calculator_case(
    number: int,
    view: Mapping[str, Any],
    curated: Any,
    spec: Spec,
    name_assumptions: bool = True,
) -> list[str]:
    """One calculator case for a review sheet: inputs and the quoted section 8.6 steps, with blank
    amount cells. `name_assumptions=False` leaves out the assumptions the case names (G3)."""
    given = view["given"]
    plan = curated.plans[given["plan_id"]]
    network = given["network"]
    terms = plan.in_network if network == "IN_NETWORK" else plan.out_of_network
    lines = given["lines"]
    approved = [line for line in lines if line["decision"] == "APPROVE"]
    benefits = {
        category: curated.benefit(plan.plan_id, category)
        for category in sorted(
            {line["benefit_category"] for line in lines if line.get("benefit_category")}
        )
    }
    used = {benefits[line["benefit_category"]].cost_share_rule for line in approved}
    steps = [f"1. {spec.calc_steps[1]}"]
    if network != "IN_NETWORK":
        steps.append(f"2. {spec.calc_steps[2]}")
    steps.append(f"3. {spec.calc_steps[3]}")
    if "COPAY" in used:  # also out of network, so A3 is the reviewer's call, not the sheet's
        steps.append(f"- {spec.cost_share['COPAY']}")
    if network != "IN_NETWORK" or "DEDUCTIBLE_COINSURANCE" in used:
        steps.append(f"- {spec.cost_share['DEDUCTIBLE_COINSURANCE']}")
    if network != "IN_NETWORK":
        steps.append(f"- {spec.cost_share['OUT_OF_NETWORK']}")
    steps += [f"4. {spec.calc_steps[4]}", f"5. {spec.calc_steps[5]}"]
    if given.get("other_coverage"):
        steps.append(f"6. {spec.calc_steps[6]}")
    if len(approved) > 1:
        steps.append(f"7. {spec.calc_steps[7]}")
    if len(approved) < len(lines):
        steps.append(f"- {spec.calc_notes[0]}")

    out = [f"### Calculator case {number} ({view['case_id']})", ""]
    out += ["Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):", ""]
    for step in steps:
        out += [f"> {step}", ""]
    if name_assumptions:
        named = ", ".join(view.get("assumptions") or []) or "none named"
        out += [f"Assumptions the case names (tests/golden/README.md): {named}", ""]
    out.append(
        f"- Plan {plan.plan_id} ({plan.plan_type}), {network}: deductible "
        f"{terms.deductible_cents}, "
        f"coinsurance {terms.coinsurance_bps} basis points, out-of-pocket maximum "
        f"{terms.oop_max_cents} (cents)"
        if terms
        else f"- Plan {plan.plan_id} ({plan.plan_type}): no {network} terms"
    )
    before = given["accumulators"]
    out.append(
        f"- Accumulators before the claim ({network}): deductible met "
        f"{before['deductible_met_cents']}, out-of-pocket met {before['oop_met_cents']} (cents)"
    )
    out += ["", "| Benefit category | Cost share rule | Copay (cents) |", "|---|---|---|"]
    for category, b in benefits.items():
        out.append(
            f"| {category} | {b.cost_share_rule} | "
            f"{b.copay_cents if b.copay_cents is not None else '-'} |"
        )
    out += [
        "",
        "| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |",
        "|---|---|---|",
    ]
    for code, fee in sorted(given["fee_schedule"].items()):
        out.append(f"| {code} | {fee['inn_allowed_cents']} | {fee['oon_allowed_cents']} |")
    out += [
        "",
        "| Line | Code | Units | Billed (cents) | Decision | Benefit category |",
        "|---|---|---|---|---|---|",
    ]
    for line in lines:
        out.append(
            f"| {line['line_no']} | {line['procedure_code']} | {line['units']} | "
            f"{line['billed_cents']} | {line['decision']} | {line.get('benefit_category') or '-'} |"
        )
    other = given.get("other_coverage")
    if other:
        paid = ", ".join(
            f"line {p['line_no']} {p['paid_cents']}" for p in other.get("primary_paid", [])
        )
        out += [
            "",
            f"- Other coverage (our plan is secondary): {other.get('payer_name')}; primary paid "
            f"(cents): {paid}",
        ]
    else:
        out += ["", "- Other coverage: none"]
    out += [
        "",
        "| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |",
        "|---|---|---|---|---|---|---|",
        *[f"| {line['line_no']} |  |  |  |  |  |  |" for line in lines],
        "",
        "Notes:",
        "",
    ]
    return out


def _ncci_unavailable(codes: Iterable[str]) -> set[str]:
    """Codes before the first loaded NCCI part's first column-1 code, when part f1 is absent (as a
    .txt and as an .xlsx)."""
    from app.db import raw

    files = raw._ncci_files()
    if not files or files[0].stem == f"{raw.NCCI_VERSION}-f1":
        return set()
    first = next(raw.read_ncci_records(files[0]), ("",))[0]
    return {c for c in codes if first and c < first}


def load_reference(curated: Any) -> Reference:
    from app.db import raw

    fixture = json.loads((GOLDEN / "rules" / "reference.json").read_text(encoding="utf-8"))
    codes = set(curated.scope)
    return Reference(
        members={m["member_id"]: m for m in fixture["members"]},
        providers={p["npi"]: p for p in fixture["providers"]},
        networks={(n["npi"], n["plan_id"]): n["in_network"] for n in fixture["provider_networks"]},
        authorizations=fixture["authorizations"],
        existing_claims=fixture["existing_claims"],
        curated=curated,
        icd10=raw.read_icd10_codes(),
        pos=raw.read_place_of_service_codes(),
        ncci=raw.read_ncci_pairs(codes),
        ncci_missing=frozenset(_ncci_unavailable(codes)),
        mue=raw.read_mue(codes),
    )


def _d8() -> str:
    """The D8 row of DECISIONS.md (rule order), word for word."""
    for line in (ROOT / "DECISIONS.md").read_text(encoding="utf-8").splitlines():
        if "Rule order (D8)" in line:
            return line.split("|")[2].strip()
    return ""


ANSWER_FIELDS = (
    "sheet_no",
    "case_id",
    "kind",
    "line_no",
    "claim_outcome",
    "status",
    "failures",
    "line_outcomes",
    "flags",
    "allowed_cents",
    "deductible_cents",
    "copay_cents",
    "coinsurance_cents",
    "plan_pays_cents",
    "member_pays_cents",
    "cob_primary_paid_cents",
    "contractual_adjustment_cents",
    "balance_bill_exposure_cents",
    "accumulators_after",
)


def answer_rows(
    rules_pick: Sequence[Mapping[str, Any]], calc_pick: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, case in enumerate(rules_pick, start=1):
        e = case["expected"]
        rows.append(
            {
                "sheet_no": f"Rules {number}",
                "case_id": case["case_id"],
                "kind": "rules",
                "claim_outcome": e["claim_outcome"],
                "status": e["status"],
                "failures": "; ".join(
                    f"{f['rule_id']} {f['outcome']} {f['reason_code']}"
                    + (f" line {f['line_no']}" if f["line_no"] is not None else "")
                    for f in e["failures"]
                ),
                "line_outcomes": "; ".join(
                    f"line {o['line_no']} {o['outcome']} {','.join(o.get('reason_codes') or [])}"
                    + (f" flags {','.join(o['flags'])}" if o.get("flags") else "")
                    for o in e["line_outcomes"] or []
                ),
                "flags": ",".join(e["flags"]),
            }
        )
    for number, case in enumerate(calc_pick, start=1):
        amounts = case["expected"]["amounts"]
        for line in [*amounts["lines"], {**amounts["totals"], "line_no": "total"}]:
            row = {
                "sheet_no": f"Calculator {number}",
                "case_id": case["case_id"],
                "kind": "calculator",
                "line_no": line["line_no"],
                **{f: line[f] for f in ANSWER_FIELDS if f in line and f != "line_no"},
            }
            if line["line_no"] == "total":
                row["accumulators_after"] = json.dumps(case["expected"].get("accumulators_after"))
            rows.append(row)
    return rows


def build(out_dir: Path = OUT_DIR) -> None:
    from app.db.curated import load_curated
    from scripts.verify.model_disagreements import Line, dx_checker

    spec = parse_instructions(INSTRUCTIONS_MD.read_text(encoding="utf-8"))
    assumptions = readme_assumptions(README_MD.read_text(encoding="utf-8"))
    rules_cases, calc_cases = load_cases("rules"), load_cases("calculator")
    curated = load_curated()
    check_dx = dx_checker()

    def supported(code: str, diagnoses: tuple[str, ...]) -> bool | None:
        return check_dx(Line(0, code, diagnoses))

    findings: list[Finding] = []
    for case in rules_cases:
        findings += check_rules_case(case, spec)
        findings += decision_conflicts(case, supported)
        findings += candidate_reviews(case)
    found_situations: dict[str, set[str]] = {}
    for case in calc_cases:
        plan = curated.plans[case["given"]["plan_id"]]
        findings += check_calculator_case(case, plan)

        def benefit(category: str, plan_id: str = plan.plan_id) -> tuple[str, int | None]:
            b = curated.benefit(plan_id, category)
            return b.cost_share_rule, b.copay_cents

        found_situations[case["case_id"]] = situations(case, plan, benefit)
    rules_pick = sample_rules(rules_cases)
    calc_ids, calc_short = sample_calculator(found_situations)
    calc_by_id = {c["case_id"]: c for c in calc_cases}
    calc_pick = [calc_by_id[i] for i in calc_ids]
    ref = load_reference(curated)

    by_check: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_check[f.check].append(f)
    hidden = {c["case_id"] for c in [*rules_pick, *calc_pick]}

    def cases_of(check: str) -> str:
        return shown_cases(by_check.get(check, []), hidden)

    mixed = sum(cob_total_differs(case) for case in calc_cases)

    minutes = MINUTES_PER_RULES_CASE * len(rules_pick) + MINUTES_PER_CALCULATOR_CASE * len(
        calc_pick
    )
    kinds = Counter(f.kind for f in findings)
    lines = [
        "# Golden test spot-check (Task G1)",
        "",
        "For one reviewer. Work out each case by hand from the inputs shown, using only the quoted "
        "INSTRUCTIONS.md text and the assumptions below, then fill in the blank cells. Amounts are "
        "in cents. Mark each assumption and each H5 field mapping ACCEPT or CHANGE.",
        "",
        "**Do not open G_spotcheck_answers.csv until every cell is filled.** The same goes for "
        "G_golden_checks.csv, which holds the details of the automatic checks with expected "
        "amounts.",
        "",
        f"Estimated time: {minutes} minutes ({len(rules_pick)} rules cases x "
        f"{MINUTES_PER_RULES_CASE} minutes, {len(calc_pick)} calculator cases x "
        f"{MINUTES_PER_CALCULATOR_CASE} minutes).",
        "",
        f"## Automatic checks ({len(rules_cases)} rules cases, {len(calc_cases)} calculator cases)",
        "",
        f"Findings: violations {kinds['violation']}, conflicts with later decisions "
        f"{kinds['conflict']}, cases to review against D-RULE-1 {kinds['review']}. Only case IDs "
        "are shown here, so the sheet stays blind.",
        "",
        "| Check | Cases checked | Findings | Cases |",
        "|---|---|---|---|",
        *[
            f"| Calculator: {c} | {len(calc_cases)} | {len(by_check.get(c, []))} | {cases_of(c)} |"
            for c in CALCULATOR_CHECKS
        ],
        *[
            f"| Rules: {c} | {len(rules_cases)} | {len(by_check.get(c, []))} | {cases_of(c)} |"
            for c in RULES_CHECKS
        ],
        *[
            f"| Rules: {c} | {len(rules_cases)} | {len(items)} | {cases_of(c)} |"
            for c, items in sorted(by_check.items())
            if items[0].kind == "review"
        ],
        "",
        "D-ESI-1, D-ESI-2 and D-ESI-4 to D-ESI-7 change coverage-criterion labels, which the rules "
        "cases do not carry, so they do not apply here; D-ESI-3 is R14 above. Group C is "
        "R11-R13 (D8; INSTRUCTIONS.md section 8.3 item 3 now says so).",
        "",
        "In total, the first calculator check compares plan pays + member pays with the sum over "
        "the approved lines of max(0, allowed - primary paid) (A8). That equals max(0, total "
        "allowed - total primary paid) unless one claim has lines where the primary paid more "
        f"than allowed and lines where it paid less; cases where the two differ: {mixed}.",
        "",
        "### Coverage: rules",
        "",
        "| Rule or variant | Golden cases |",
        "|---|---|",
        *[
            f"| {_cell(name)} | {count or '**none**'} |"
            for name, count in rules_coverage(rules_cases)
        ],
        "",
        "### Coverage: cost-share situations (calculator)",
        "",
        "| Situation | Golden cases |",
        "|---|---|",
        *[
            f"| {name} | {sum(name in s for s in found_situations.values()) or '**none**'} |"
            for name in (*SITUATIONS, *EXTRA_SITUATIONS)
        ],
        "",
    ]
    if calc_short:
        lines += [f"No calculator case to sample for: {', '.join(calc_short)}.", ""]
    lines += [
        "## Golden assumptions (tests/golden/README.md, word for word)",
        "",
        "| ID | Assumption | ACCEPT / CHANGE | Notes |",
        "|---|---|---|---|",
        *[f"| {aid} | {_cell(text)} |  |  |" for aid, text in assumptions],
        "",
        "## H5 field mapping used by the automatic checks",
        "",
        "A failing rule becomes REJECT (H5) when one of these fields was read below 0.85.",
        "",
        "| Rule | Fields used | Section 8.3 text it was read from | ACCEPT / CHANGE | Notes |",
        "|---|---|---|---|---|",
    ]
    for rule_id, patterns in FIELDS_USED.items():
        fields = (
            ", ".join(patterns) + (" (the failing line only)" if rule_id in PER_LINE else "")
            if patterns
            else "the missing field itself (the cases do not name it, so not checked)"
        )
        lines.append(f"| {rule_id} | {_cell(fields)} | {_cell(spec.rules[rule_id].text)} |  |  |")
    lines += [
        "",
        f"## Rules cases ({len(rules_pick)}, seed {SEED})",
        "",
        "How the rules apply (INSTRUCTIONS.md section 8.3, word for word):",
        "",
        *[f"> {n}. {item}" for n, item in enumerate(spec.order, start=1)],
        "",
        f"> {spec.rules['DUP'].quote}",
        "",
        f"DECISIONS.md D8, word for word: {_d8()}",
        "",
    ]
    for number, case in enumerate(rules_pick, start=1):
        lines += render_rules_case(number, blind_view(case), ref, spec)
    lines += [
        f"## Calculator cases ({len(calc_pick)}, seed {SEED}: one per situation)",
        "",
        "Situations, in order: " + "; ".join(SITUATIONS) + ".",
        "",
        "How the calculator works (INSTRUCTIONS.md section 8.6, word for word):",
        "",
        *[f"> {paragraph}\n" for paragraph in spec.calc_intro],
    ]
    for number, case in enumerate(calc_pick, start=1):
        lines += render_calculator_case(number, blind_view(case), curated, spec)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / SHEET_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (out_dir / ANSWERS_FILE).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANSWER_FIELDS)
        writer.writeheader()
        writer.writerows(answer_rows(rules_pick, calc_pick))
    with (out_dir / CHECKS_FILE).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=("kind", "check", "case_id", "line_no", "detail"))
        writer.writeheader()
        for item in findings:
            writer.writerow(
                {
                    "kind": item.kind,
                    "check": item.check,
                    "case_id": item.case_id,
                    "line_no": "" if item.line_no is None else item.line_no,
                    "detail": item.detail,
                }
            )
    print(
        f"{len(rules_cases)} rules and {len(calc_cases)} calculator cases checked: "
        + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
        + f"; sheet: {len(rules_pick)} rules and {len(calc_pick)} calculator cases, {minutes} "
        f"minutes; no case for: {', '.join(calc_short) or 'none'}"
    )
    for check, items in sorted(by_check.items()):
        print(f"  {items[0].kind}: {check}: {', '.join(i.case_id for i in items)}")


def main() -> None:
    build()


if __name__ == "__main__":
    main()
