"""Group C, rules v2: limits from the LCDs and billing articles (R14 to R20; D-RULE-2 to D-RULE-4,
D-RULE-7). They run after R11 to R13 on every line; a line's reasons and flags follow rule order.

A rule denies a line only when the LCD or article is explicit and the check needs nothing beyond
the claim; a limit worded "usually" or with a documented exception gives a flag (D-RULE-2).

- R14 (L33906): an ESI line is denied when another block is billed on the same date: a different
  ESI code or a facet joint injection. Add-on level codes, radiofrequency denervation and the same
  code on another line are not other blocks; a facet injection whose own diagnoses show a facet
  synovial cyst is the LCD's exception. Every billed line counts. A denied ESI's own add-on lines
  on that date are denied with it (D-RULE-7).
- R15 (D-DX-1, D-RULE-4): a line's own diagnoses (its pointers) must meet one of its code's
  billing-article alternatives; codes without an article are not checked.
- R16 (L35050): a home sleep test line with a parasomnia diagnosis among its own is denied.
- R17 (L34594, "usually"): a nerve conduction line with no needle EMG line anywhere on the claim
  gets the flag NCS_WITHOUT_EMG.
- R18 (L33906): transforaminal levels per date, per primary code and its add-on, counted per side
  (an RT or LT line on its side; modifier 50 or no side modifier on both; each unit one level):
  above 2 on a side, the add-on lines counting on that side are denied. An interlaminar or caudal
  ESI with modifier 50 is denied.
- R19 (L33930, A57787): a third-level facet code is denied; facet codes of both spinal regions on
  one date give each facet line that date the flag FACET_TWO_REGIONS.
- R20 (L34520): more than 8 hours from the testing codes on the claim give each testing line the
  flag EXTENDED_TESTING.
The code roles and diagnosis sets come from data/curated/ (rule_code_roles.csv,
rule_diagnosis_sets.csv), the article coverage from the MCD current articles.
"""

from dataclasses import dataclass

from app.domain.contracts import IntakeClaim, ServiceLine
from app.rules.reference import DiagnosisSupportRef, RulesReference

MULTIPLE_BLOCKS = "DN_MULTIPLE_BLOCKS"
DX_NOT_SUPPORTED = "DN_DX_NOT_SUPPORTED"
HOME_TEST_PARASOMNIA = "DN_HOME_TEST_PARASOMNIA"
ESI_LEVELS = "DN_ESI_LEVELS"
FACET_LEVELS = "DN_FACET_LEVELS"
NCS_WITHOUT_EMG = "NCS_WITHOUT_EMG"
FACET_TWO_REGIONS = "FACET_TWO_REGIONS"
EXTENDED_TESTING = "EXTENDED_TESTING"
REASON_RULES = {
    MULTIPLE_BLOCKS: "R14",
    DX_NOT_SUPPORTED: "R15",
    HOME_TEST_PARASOMNIA: "R16",
    ESI_LEVELS: "R18",
    FACET_LEVELS: "R19",
}
ESI_ROLES = ("ESI_INTERLAMINAR", "ESI_TRANSFORAMINAL")
BLOCK_ROLES = (*ESI_ROLES, "FACET_INJECTION")
MAX_LEVELS = 2
MAX_TESTING_MINUTES = 8 * 60
SIDES = ("RT", "LT")
BILATERAL = "50"


@dataclass(frozen=True)
class LineHit:
    """One rule result on one line: a reason code (the line is denied) or a flag."""

    rule_id: str
    index: int  # 0-based line index
    code: str  # internal reason code or flag
    is_flag: bool
    detail: str
    fields_used: tuple[str, ...]


def _role(reference: RulesReference, line: ServiceLine) -> str | None:
    role = reference.code_roles.get(line.procedure_code)
    return role.role if role else None


def _pointed(claim: IntakeClaim, line: ServiceLine) -> list[tuple[int, str]]:
    """(index in the claim's diagnoses, code) of the line's own diagnoses, in pointer order."""
    out = []
    for pointer in line.diagnosis_pointers:
        k = ord(pointer) - ord("A")
        if 0 <= k < len(claim.diagnoses):
            out.append((k, claim.diagnoses[k]))
    return out


def _dx_fields(claim: IntakeClaim, i: int) -> tuple[str, ...]:
    line = claim.service_lines[i]
    return (
        f"service_lines.{i}.procedure_code",
        f"service_lines.{i}.diagnosis_pointers",
        *(f"diagnoses.{k}" for k, _ in _pointed(claim, line)),
    )


def _fields(indexes: list[int], *names: str) -> tuple[str, ...]:
    return tuple(f"service_lines.{i}.{name}" for i in indexes for name in names)


def check_r14(claim: IntakeClaim, reference: RulesReference) -> list[LineHit]:
    lines = claim.service_lines
    cyst = reference.diagnosis_sets.get("FACET_SYNOVIAL_CYST", frozenset())
    hits: list[LineHit] = []
    for i, line in enumerate(lines):
        if _role(reference, line) not in ESI_ROLES:
            continue
        same_day = [
            j
            for j, other in enumerate(lines)
            if j != i and other.date_of_service == line.date_of_service
        ]
        others = [
            j
            for j in same_day
            if _role(reference, lines[j]) in BLOCK_ROLES
            and lines[j].procedure_code != line.procedure_code
        ]
        facets = [j for j in others if _role(reference, lines[j]) == "FACET_INJECTION"]
        blocking = [
            j
            for j in others
            if not (j in facets and cyst & {dx for _, dx in _pointed(claim, lines[j])})
        ]
        if not blocking:
            continue
        fields = _fields([i, *others], "procedure_code", "date_of_service")
        fields += tuple(f for j in facets for f in _dx_fields(claim, j)[1:])
        blocks = ", ".join(f"line {lines[j].line_no} {lines[j].procedure_code}" for j in blocking)
        hits.append(
            LineHit(
                "R14",
                i,
                MULTIPLE_BLOCKS,
                False,
                f"Line {line.line_no}: ESI {line.procedure_code} with another block on "
                f"{line.date_of_service.isoformat()} ({blocks}).",
                fields,
            )
        )
        for j in same_day:
            role = reference.code_roles.get(lines[j].procedure_code)
            if (
                role is not None
                and role.role == "ESI_TRANSFORAMINAL_ADDON"
                and role.primary_code == line.procedure_code
                and all(h.index != j for h in hits)
            ):
                hits.append(
                    LineHit(
                        "R14",
                        j,
                        MULTIPLE_BLOCKS,
                        False,
                        f"Line {lines[j].line_no}: add-on {lines[j].procedure_code} of the "
                        f"denied ESI on line {line.line_no} (D-RULE-7).",
                        fields + _fields([j], "procedure_code", "date_of_service"),
                    )
                )
    return hits


def supported(
    claim: IntakeClaim, line: ServiceLine, support: DiagnosisSupportRef, reference: RulesReference
) -> bool:
    """Whether the line's own diagnoses meet one of the article's alternatives (D-RULE-4)."""
    groups = reference.article_covered.get(support.billing_article, {})
    diagnoses = [dx for _, dx in _pointed(claim, line)]

    def has(group: int, among: list[str]) -> bool:
        return any(dx in groups.get(group, frozenset()) for dx in among)

    for alternative in support.alternatives:
        if any(
            group in support.group_modifiers
            and not support.group_modifiers[group] & set(line.modifiers)
            for group in alternative
        ):
            continue
        first = support.first_group
        if first is not None and first in alternative:
            rest = [g for g in alternative if g != first]
            if has(first, diagnoses[:1]) and all(has(g, diagnoses[1:]) for g in rest):
                return True
            continue
        if all(has(group, diagnoses) for group in alternative):
            return True
    return False


def check_r15(claim: IntakeClaim, reference: RulesReference) -> list[LineHit]:
    hits = []
    for i, line in enumerate(claim.service_lines):
        support = reference.diagnosis_support.get(line.procedure_code)
        if support is None or supported(claim, line, support, reference):
            continue
        fields = _dx_fields(claim, i)
        if support.group_modifiers:
            fields += (f"service_lines.{i}.modifiers",)
        hits.append(
            LineHit(
                "R15",
                i,
                DX_NOT_SUPPORTED,
                False,
                f"Line {line.line_no}: no diagnosis of the line supports {line.procedure_code} "
                f"under {support.billing_article}.",
                fields,
            )
        )
    return hits


def check_r16(claim: IntakeClaim, reference: RulesReference) -> list[LineHit]:
    parasomnia = reference.diagnosis_sets.get("PARASOMNIA", frozenset())
    hits = []
    for i, line in enumerate(claim.service_lines):
        found = sorted(parasomnia & {dx for _, dx in _pointed(claim, line)})
        if _role(reference, line) == "HOME_SLEEP_TEST" and found:
            hits.append(
                LineHit(
                    "R16",
                    i,
                    HOME_TEST_PARASOMNIA,
                    False,
                    f"Line {line.line_no}: home sleep test {line.procedure_code} for a "
                    f"parasomnia ({', '.join(found)}).",
                    _dx_fields(claim, i),
                )
            )
    return hits


def check_r17(claim: IntakeClaim, reference: RulesReference) -> list[LineHit]:
    lines = claim.service_lines
    if any(_role(reference, line) == "NEEDLE_EMG" for line in lines):
        return []
    fields = _fields(list(range(len(lines))), "procedure_code")
    return [
        LineHit(
            "R17",
            i,
            NCS_WITHOUT_EMG,
            True,
            f"Line {line.line_no}: nerve conduction with no needle EMG on the claim.",
            fields,
        )
        for i, line in enumerate(lines)
        if _role(reference, line) == "NERVE_CONDUCTION"
    ]


def _sides(line: ServiceLine) -> set[str]:
    side = set(SIDES) & set(line.modifiers)
    return side if len(side) == 1 and BILATERAL not in line.modifiers else set(SIDES)


def check_r18(claim: IntakeClaim, reference: RulesReference) -> list[LineHit]:
    lines = claim.service_lines
    hits = []
    for primary, role in sorted(reference.code_roles.items()):
        if role.role != "ESI_TRANSFORAMINAL":
            continue
        addons = {
            code
            for code, r in reference.code_roles.items()
            if r.role == "ESI_TRANSFORAMINAL_ADDON" and r.primary_code == primary
        }
        for day in sorted({x.date_of_service for x in lines if x.procedure_code == primary}):
            group = [
                i
                for i, x in enumerate(lines)
                if x.date_of_service == day and x.procedure_code in {primary, *addons}
            ]
            levels = {s: sum(lines[i].units for i in group if s in _sides(lines[i])) for s in SIDES}
            over = {s for s, n in levels.items() if n > MAX_LEVELS}
            fields = _fields(group, "procedure_code", "units", "modifiers", "date_of_service")
            for i in group:
                if lines[i].procedure_code in addons and _sides(lines[i]) & over:
                    hits.append(
                        LineHit(
                            "R18",
                            i,
                            ESI_LEVELS,
                            False,
                            f"Line {lines[i].line_no}: transforaminal levels on "
                            f"{day.isoformat()}: right {levels['RT']}, left {levels['LT']}, "
                            f"more than {MAX_LEVELS}.",
                            fields,
                        )
                    )
    for i, line in enumerate(lines):
        if _role(reference, line) == "ESI_INTERLAMINAR" and BILATERAL in line.modifiers:
            hits.append(
                LineHit(
                    "R18",
                    i,
                    ESI_LEVELS,
                    False,
                    f"Line {line.line_no}: interlaminar or caudal ESI {line.procedure_code} "
                    "billed bilaterally.",
                    _fields([i], "procedure_code", "modifiers"),
                )
            )
    return sorted(hits, key=lambda h: h.index)


def check_r19(claim: IntakeClaim, reference: RulesReference) -> list[LineHit]:
    lines = claim.service_lines
    hits = [
        LineHit(
            "R19",
            i,
            FACET_LEVELS,
            False,
            f"Line {line.line_no}: {line.procedure_code} is a third-level facet procedure.",
            _fields([i], "procedure_code"),
        )
        for i, line in enumerate(lines)
        if _role(reference, line) == "FACET_THIRD_LEVEL"
    ]
    for day in sorted({x.date_of_service for x in lines}):
        facets = [
            i
            for i, x in enumerate(lines)
            if x.date_of_service == day
            and (role := reference.code_roles.get(x.procedure_code)) is not None
            and role.role.startswith("FACET_")
        ]
        regions = {reference.code_roles[lines[i].procedure_code].spinal_region for i in facets}
        if len(regions) > 1:
            fields = _fields(facets, "procedure_code", "date_of_service")
            hits += [
                LineHit(
                    "R19",
                    i,
                    FACET_TWO_REGIONS,
                    True,
                    f"Line {lines[i].line_no}: facet procedures in two spinal regions on "
                    f"{day.isoformat()}.",
                    fields,
                )
                for i in facets
            ]
    return hits


def check_r20(claim: IntakeClaim, reference: RulesReference) -> list[LineHit]:
    lines = claim.service_lines
    timed = [
        (i, role.minutes_per_unit)
        for i, line in enumerate(lines)
        if (role := reference.code_roles.get(line.procedure_code)) is not None
        and role.role == "TESTING_TIME"
        and role.minutes_per_unit
    ]
    minutes = sum(lines[i].units * per_unit for i, per_unit in timed)
    if minutes <= MAX_TESTING_MINUTES:
        return []
    fields = _fields([i for i, _ in timed], "procedure_code", "units")
    return [
        LineHit(
            "R20",
            i,
            EXTENDED_TESTING,
            True,
            f"Line {lines[i].line_no}: {minutes} testing minutes on the claim, more than 8 hours.",
            fields,
        )
        for i, _ in timed
    ]


CHECKS = (check_r14, check_r15, check_r16, check_r17, check_r18, check_r19, check_r20)
PASS_DETAILS = {
    "R14": "No ESI line meets another block on its date.",
    "R15": "Every checked line's diagnoses support its code.",
    "R16": "No home sleep test line is for a parasomnia.",
    "R17": "No nerve conduction line is billed without needle EMG.",
    "R18": "No ESI exceeds its level limits.",
    "R19": "No third-level facet procedure and no two spinal regions on one date.",
    "R20": "No more than 8 hours of testing.",
}


def check_lcd_edits(claim: IntakeClaim, reference: RulesReference) -> list[LineHit]:
    """Every R14 to R20 result, in rule order."""
    return [hit for check in CHECKS for hit in check(claim, reference)]
