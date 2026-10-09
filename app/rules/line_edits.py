"""Group C (line level): R11 to R13, then rules v2 R14 to R20 (§8.3, app/rules/lcd_edits.py). A
failing line is denied and the claim continues with the other lines; when every line is denied, the
claim is denied (D8). A flag never denies.

R11 to R13 follow the generator's rule mirror (training/generate/codebook.py `line_rule_outcomes`),
which the trained model saw (frozen for model v1); the parity test checks they agree, and that
R14 to R20 change exactly the lines listed in tests/golden/rules/v2_dataset_changes.csv.

- R11 (A-R3, D-RULE-8): for every ordered pair of lines on the same date of service, the first
  NCCI edit active that day with line A's code in column 1 and line B's in column 2 applies
  (indicator 9: none). With indicator 1 and an NCCI PTP-associated modifier reported where the
  2026 NCCI Policy Manual places it (`bypassing_modifiers`), line B passes with the flag
  NCCI_BYPASS (the model and the reviewer check the documentation); otherwise line B is denied.
- R12 (A-R4): the units of one code on one date of service, added over the lines, above the MUE
  limit deny every line of that code and date.
- R13: a code on the plan's fixed exclusion list is denied.
A line failing several rules lists every reason, and its flags, in rule order (A-R11); the first
reason is the primary one (D-RULE-3).
"""

from app.domain.contracts import (
    IntakeClaim,
    LineRuleOutcome,
    RuleOutcomeValue,
    RuleResult,
    ServiceLine,
)
from app.rules.lcd_edits import PASS_DETAILS, REASON_RULES, check_lcd_edits
from app.rules.reference import PlanRef, RulesReference
from app.rules.results import failed, line_fields, passed

BYPASS_FLAG = "NCCI_BYPASS"
NO_EDIT = "9"  # modifier indicator: the edit does not apply
BYPASS_ALLOWED = "1"
RULE_OF = {"DN_NCCI_BUNDLED": "R11", "DN_MUE_EXCEEDED": "R12", "DN_EXCLUDED": "R13"} | REASON_RULES


def _in_place(
    line: ServiceLine, other: ServiceLine, modifier: str, reference: RulesReference
) -> bool:
    """Whether `modifier` on `line` stands where the manual places it (D-RULE-8)."""
    ref = reference.ptp_modifiers[modifier]
    is_em = line.procedure_code in reference.em_codes
    if ref.placement in ("NOT_EM", "PROCEDURE"):  # 59 and X modifiers; 58, 78, 79
        return not is_em
    if ref.placement == "EM_WITH_PROCEDURE":  # 24, 25, 57
        paired = reference.global_days.get(other.procedure_code)
        return (
            is_em
            and other.procedure_code not in reference.em_codes
            and (not ref.paired_global_days or paired in ref.paired_global_days)
        )
    return ref.placement == "EITHER"  # 27, 91; anatomic modifiers are checked in pairs


def bypassing_modifiers(a: ServiceLine, b: ServiceLine, reference: RulesReference) -> list[str]:
    """The modifiers on two lines that bypass an NCCI edit with indicator 1. With the manual's
    NCCI PTP-associated modifiers in the reference (D-RULE-8): each where the manual places it, and
    anatomic modifiers when both lines carry one and they share none (different sites). Without
    them (a v1 reference): XE, XP, XS or XU on either line (A-R3 v1)."""
    if not reference.ptp_modifiers:
        return sorted(reference.bypass_modifiers & {*a.modifiers, *b.modifiers})
    found = {
        modifier
        for line, other in ((a, b), (b, a))
        for modifier in line.modifiers
        if modifier in reference.ptp_modifiers
        and reference.ptp_modifiers[modifier].placement != "DIFFERENT_SITES"
        and _in_place(line, other, modifier, reference)
    }
    sites = [
        {m for m in line.modifiers if m in reference.ptp_modifiers}
        & {m for m, ref in reference.ptp_modifiers.items() if ref.placement == "DIFFERENT_SITES"}
        for line in (a, b)
    ]
    if sites[0] and sites[1] and not sites[0] & sites[1]:
        found |= sites[0] | sites[1]
    return sorted(found)


def _fields(rule_id: str, index: int | None, line_count: int) -> list[str]:
    """R11 pairs two lines, so every line's fields count; R12 and R13 use the failing line."""
    if rule_id == "R11":
        return line_fields(line_count, "procedure_code", "modifiers", "date_of_service")
    lines = range(line_count) if index is None else [index]
    if rule_id == "R12":
        names = ("units", "procedure_code", "date_of_service")
        return [f"service_lines.{i}.{name}" for name in names for i in lines]
    return [f"service_lines.{i}.procedure_code" for i in lines] + ["member_id"]


def check_line_edits(
    claim: IntakeClaim, plan: PlanRef, reference: RulesReference
) -> tuple[list[RuleResult], list[LineRuleOutcome]]:
    """The Group C results (a passed result per rule no line fails, then each failure by line and
    rule order) and one outcome per line."""
    lines = claim.service_lines
    reasons: list[list[str]] = [[] for _ in lines]
    flags: list[list[str]] = [[] for _ in lines]
    details: dict[tuple[int, str], str] = {}
    fields_of: dict[tuple[int, str], list[str]] = {}

    for i, a in enumerate(lines):
        for j, b in enumerate(lines):
            if i == j or a.date_of_service != b.date_of_service:
                continue
            indicator = reference.ncci_indicator(
                a.procedure_code, b.procedure_code, a.date_of_service
            )
            if indicator is None or indicator == NO_EDIT:
                continue
            edit = (
                f"NCCI edit {a.procedure_code}/{b.procedure_code} (modifier indicator "
                f"{indicator}) with line {a.line_no}"
            )
            bypass = bypassing_modifiers(a, b, reference)
            if indicator == BYPASS_ALLOWED and bypass:
                if BYPASS_FLAG not in flags[j]:
                    flags[j].append(BYPASS_FLAG)
            elif "DN_NCCI_BUNDLED" not in reasons[j]:
                reasons[j].append("DN_NCCI_BUNDLED")
                details[(j, "R11")] = f"Line {b.line_no} is bundled: {edit}, no bypass allowed."

    for i, line in enumerate(lines):
        limit = reference.mue.get(line.procedure_code)
        total = sum(
            other.units
            for other in lines
            if other.procedure_code == line.procedure_code
            and other.date_of_service == line.date_of_service
        )
        if limit is not None and total > limit:
            reasons[i].append("DN_MUE_EXCEEDED")
            details[(i, "R12")] = (
                f"Line {line.line_no}: {total} units of {line.procedure_code} on "
                f"{line.date_of_service.isoformat()} exceed the MUE limit {limit}."
            )

    for i, line in enumerate(lines):
        if line.procedure_code in plan.excluded_codes:
            reasons[i].append("DN_EXCLUDED")
            details[(i, "R13")] = (
                f"Line {line.line_no}: {line.procedure_code} is excluded by {plan.plan_id}."
            )

    flagged: dict[str, list[str]] = {}
    for hit in check_lcd_edits(claim, reference):
        if hit.is_flag:
            flags[hit.index].append(hit.code)
            flagged.setdefault(hit.rule_id, []).append(
                f"line {lines[hit.index].line_no} {hit.code}"
            )
        else:
            reasons[hit.index].append(hit.code)
            details[(hit.index, hit.rule_id)] = hit.detail
            fields_of[(hit.index, hit.rule_id)] = list(hit.fields_used)

    failures = [
        failed(
            RULE_OF[reason],
            RuleOutcomeValue.DENY,
            reason,
            details[(i, RULE_OF[reason])],
            fields_of.get((i, RULE_OF[reason])) or _fields(RULE_OF[reason], i, len(lines)),
            line_no=lines[i].line_no,
        )
        for i in range(len(lines))
        for reason in reasons[i]
    ]
    failing_rules = {result.rule_id for result in failures}
    passes = [
        passed(rule_id, detail, _fields(rule_id, None, len(lines)))
        for rule_id, detail in (
            ("R11", "No NCCI edit denies a line."),
            ("R12", "No code exceeds its MUE limit on a date of service."),
            ("R13", f"No code is on {plan.plan_id}'s exclusion list."),
        )
        if rule_id not in failing_rules
    ] + [
        passed(
            rule_id,
            f"No line is denied; flagged: {', '.join(flagged[rule_id])}."
            if rule_id in flagged
            else detail,
            line_fields(len(lines), "procedure_code"),
        )
        for rule_id, detail in PASS_DETAILS.items()
        if rule_id not in failing_rules
    ]
    outcomes = [
        LineRuleOutcome(
            line_no=line.line_no,
            outcome="DENY" if reasons[i] else "PASS",
            reason_codes=reasons[i],
            flags=flags[i],
        )
        for i, line in enumerate(lines)
    ]
    return passes + failures, outcomes
