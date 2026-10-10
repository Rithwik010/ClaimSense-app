"""P5.4 acceptance check: every amount and every reason in a rendered explanation matches the
decision record it was rendered from. Used by the unit tests (hand-built records) and the
end-to-end test (every golden case, processed and reviewed through the API).

The text explanation is read section by section: each line's decision, reason codes and amounts,
the totals, every rule check with its reason code, the review's overrides and, on a FINAL_PENDED
claim, the processed and awaiting lines. Amounts are formatted here independently of app/explain
(Decimal, not divmod). Anywhere else in the text, an amount or a reason code may appear only when
the record holds it.
"""

import re
from collections import Counter
from decimal import Decimal

from app.domain.contracts import AmountTotals, ClaimStatus, DecisionRecord, LineAmounts

MONEY = re.compile(r"-?\$[\d,]+\.\d{2}")
CODE = re.compile(r"\b(?:RJ|DN|PD)_[A-Z0-9_]+\b|\bMODEL_OUTPUT_INVALID\b")
DECISIONS = {"APPROVE": "Approved", "DENY": "Denied", "PEND": "Needs information"}
AMOUNT_LABELS = {
    "billed_cents": "Billed",
    "allowed_cents": "Allowed",
    "contractual_adjustment_cents": "Contractual adjustment",
    "deductible_cents": "Deductible",
    "copay_cents": "Copay",
    "coinsurance_cents": "Coinsurance",
    "cob_primary_paid_cents": "Paid by the primary plan",
    "plan_pays_cents": "Plan pays",
    "member_pays_cents": "Member pays",
    "balance_bill_exposure_cents": "Balance-bill exposure",
}
LINE = re.compile(r"^  Line (\d+) \(([^)]*)\): (.+), decided by (.+)$")
LISTED = re.compile(r"^  Line (\d+) \(([^)]*)\): (.+)$")
RULE = re.compile(r"^  (R\d\d|DUP) (passed|failed)(?: \((\w+)\))?(?:, line (\d+))?: ")
AMOUNT = re.compile(r"^ +([A-Za-z -]+): (-?\$[\d,]+\.\d{2})$")
OVERRIDE = re.compile(r"^  Line (\d+) changed to ([A-Za-z ]+?)(?: \(([A-Z_]+)\))?: (.*)$")


def dollars(cents: int) -> str:
    value = Decimal(cents) / 100
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"


def amounts(row: LineAmounts | AmountTotals) -> dict[str, str]:
    return {label: dollars(getattr(row, name)) for name, label in AMOUNT_LABELS.items()}


def sections(text: str) -> dict[str, list[str]]:
    """Heading (an unindented line) -> its indented lines."""
    found: dict[str, list[str]] = {}
    current: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            current = found.setdefault(line, [])
        else:
            current.append(line)
    return found


def _record_codes(record: DecisionRecord) -> set[str]:
    codes = {r.reason_code for r in record.rules_outcome.rule_results if r.reason_code}
    for d in record.line_decisions:
        codes |= set(d.reason_codes)
    return codes


def _record_text(record: DecisionRecord) -> str:
    """The record's own free text the explanation may show (amounts or codes in it are its own)."""
    parts = [r.detail for r in record.rules_outcome.rule_results]
    parts += record.output_errors
    for line in record.slm_output.lines if record.slm_output else []:
        parts += [c.evidence for c in line.criteria]
    for ctx in record.context_refs.lines if record.context_refs else []:
        parts += [c.text for c in ctx.criteria]
    if record.review:
        parts += [record.review.reason or ""] + [o.reason for o in record.review.line_overrides]
    return "\n".join(" ".join(p.split()) for p in parts)


def mismatches(record: DecisionRecord, text: str) -> list[str]:
    """Every amount or reason of the text explanation that does not match the record."""
    problems: list[str] = []
    parts = sections(text)

    def check(name: str, got: object, want: object) -> None:
        if got != want:
            problems.append(f"{name}: explanation {got!r}, record {want!r}")

    summary = parts.get("Summary", [])
    check("status", any(f"({record.status.value})" in s for s in summary[:1]), True)

    # Lines: decision, reason codes and amounts of each.
    blocks: dict[int, dict] = {}
    current: dict | None = None
    for row in parts.get("Lines", []):
        if found := LINE.match(row):
            current = {"label": found.group(3), "reasons": [], "amounts": {}}
            blocks[int(found.group(1))] = current
        elif current is not None and row.startswith("    Reason: "):
            current["reasons"] += CODE.findall(row)
        elif current is not None and (found := AMOUNT.match(row)) and row.startswith("      "):
            current["amounts"][found.group(1)] = found.group(2)
    check("lines", sorted(blocks), sorted(d.line_no for d in record.line_decisions))
    by_line = {a.line_no: a for a in (record.amounts.lines if record.amounts else [])}
    for d in record.line_decisions:
        block = blocks.get(d.line_no, {"label": None, "reasons": [], "amounts": {}})
        check(f"line {d.line_no} decision", block["label"], DECISIONS[d.decision.value])
        check(f"line {d.line_no} reasons", block["reasons"], list(d.reason_codes))
        want = amounts(by_line[d.line_no]) if d.line_no in by_line else {}
        check(f"line {d.line_no} amounts", block["amounts"], want)

    # Totals.
    totals = {}
    for row in parts.get("Totals", []):
        if found := AMOUNT.match(row):
            totals[found.group(1)] = found.group(2)
    check("totals", totals, amounts(record.amounts.totals) if record.amounts else {})

    # Rule checks, each with its reason code.
    rules = []
    for row in parts.get("Rule checks", []):
        if found := RULE.match(row):
            rule_id, result, outcome, line_no = found.groups()
            rules.append([rule_id, result == "passed", outcome, line_no and int(line_no), None])
        elif rules and row.startswith("    Reason: "):
            rules[-1][4] = (CODE.findall(row) or [row.split(": ", 1)[1].split(" ")[0]])[0]
    check(
        "rule checks",
        rules,
        [
            [r.rule_id, r.passed, None if r.passed else r.outcome.value, r.line_no, r.reason_code]
            for r in record.rules_outcome.rule_results
        ],
    )

    # Review overrides.
    overrides = [
        [int(m.group(1)), m.group(2), m.group(3), m.group(4)]
        for row in parts.get("Review", [])
        if (m := OVERRIDE.match(row))
    ]
    check(
        "overrides",
        overrides,
        [
            [o.line_no, DECISIONS[o.decision.value], o.benefit_category, " ".join(o.reason.split())]
            for o in (record.review.line_overrides if record.review else [])
        ],
    )

    # FINAL_PENDED: the lines processed and the lines awaiting documentation (D-REV-7).
    pended = record.status is ClaimStatus.FINAL_PENDED
    for heading, wanted in (
        (
            "Lines processed",
            [d.line_no for d in record.line_decisions if d.decision.value != "PEND"],
        ),
        (
            "Lines awaiting documentation",
            [d.line_no for d in record.line_decisions if d.decision.value == "PEND"],
        ),
    ):
        listed = [int(m.group(1)) for row in parts.get(heading, []) if (m := LISTED.match(row))]
        check(
            heading, (heading in parts, sorted(listed)), (pended, sorted(wanted) if pended else [])
        )

    # Anywhere: no amount and no reason code the record does not hold.
    free = _record_text(record)
    known = set()
    for row in [*(record.amounts.lines if record.amounts else [])]:
        known |= set(amounts(row).values())
    if record.amounts:
        known |= set(amounts(record.amounts.totals).values())
    stray = [m for m in MONEY.findall(text) if m not in known and m not in free]
    check("amounts not in the record", stray, [])
    codes = _record_codes(record)
    stray = sorted({c for c in CODE.findall(text) if c not in codes and c not in free})
    check("reason codes not in the record", stray, [])
    missing = sorted(c for c in codes if c not in text)
    check("record reason codes missing", missing, [])
    return problems


def html_mismatches(html: str, text: str) -> list[str]:
    """The HTML explanation shows the same amounts and reason codes as the text one."""
    problems = []
    if Counter(MONEY.findall(html)) != Counter(MONEY.findall(text)):
        problems.append("the HTML and the text explanation show different amounts")
    if set(CODE.findall(html)) != set(CODE.findall(text)):
        problems.append("the HTML and the text explanation show different reason codes")
    return problems
