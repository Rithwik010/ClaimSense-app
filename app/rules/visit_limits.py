"""R21, the yearly visit limit (D-RULE-10; §8.3). Runs last in Group C, after R11 to R20, on the
lines of every visit-limited benefit category.

- A line belongs to a category when the category is its procedure code's only candidate (the
  curated loader checks that a code with a visit-limited candidate has no other; app/db/curated.py
  `validate_curated`), so the rule runs before the model chooses a category.
- One visit is one date of service in the category, however many lines it has (D-REV-8).
- The visits the member used in the claim's benefit year count first (stored by finalization,
  D-REV-8), then the claim's dates in date order. Every line of the category on a date beyond the
  plan's limit is denied DN_VISIT_LIMIT, so it never reaches the model.
- Only payable visits use up the limit: a date whose lines an earlier rule denies (R11 to R20) uses
  none, and neither does a date this rule denies.
- The benefit year is the calendar year (D7) of the claim's first date of service, as context
  assembly, finalization and the accumulators read it: a claim crossing 1 January counts every date
  in the first year (a known limitation, D-RULE-10).
- `fields_used` (H5): the member ID, and the date of service and procedure code of every line of
  the category up to the failing date, since the count relies on each of them.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.domain.contracts import IntakeClaim
from app.rules.reference import MissingReference, PlanRef, RulesReference

RULE_ID = "R21"
VISIT_LIMIT = "DN_VISIT_LIMIT"
PASS_DETAIL = "No line is beyond its benefit's visit limit for the year."


def benefit_year_start(day: date) -> date:
    """The benefit year runs from 1 January (D7), as app.db.lookups.benefit_year_start."""
    return date(day.year, 1, 1)


@dataclass(frozen=True)
class VisitLimitHit:
    index: int  # 0-based line index
    detail: str
    fields_used: tuple[str, ...]


def _category(code: str, plan: PlanRef, reference: RulesReference) -> str | None:
    categories = reference.benefit_categories.get(code, ())
    limited = [c for c in categories if c in plan.visit_limits]
    if not limited:
        return None
    if len(categories) != 1:
        raise MissingReference(
            f"{code}: a code in a visit-limited category must have no other candidate category"
        )
    return limited[0]


def check_visit_limits(
    claim: IntakeClaim,
    plan: PlanRef,
    reference: RulesReference,
    denied: Sequence[Sequence[str]],
) -> list[VisitLimitHit]:
    """The lines R21 denies. `denied` holds each line's reasons from R11 to R20."""
    lines = claim.service_lines
    period = benefit_year_start(min(line.date_of_service for line in lines))
    by_category: dict[str, dict[date, list[int]]] = {}
    for i, line in enumerate(lines):
        category = _category(line.procedure_code, plan, reference)
        if category is not None:
            by_category.setdefault(category, {}).setdefault(line.date_of_service, []).append(i)

    hits: list[VisitLimitHit] = []
    for category, days in sorted(by_category.items()):
        limit = plan.visit_limits[category]
        before = reference.visits_used.get((claim.member_id, category, period), 0)
        used = before
        relied_on: list[str] = []
        for day in sorted(days):
            indexes = days[day]
            relied_on += [
                f"service_lines.{i}.{name}"
                for i in indexes
                for name in ("date_of_service", "procedure_code")
            ]
            if all(denied[i] for i in indexes):
                continue  # every line of the date is denied already: no visit
            if used < limit:
                used += 1
                continue
            for i in indexes:
                hits.append(
                    VisitLimitHit(
                        index=i,
                        detail=(
                            f"Line {lines[i].line_no}: the {category} visit on {day.isoformat()} "
                            f"would be visit {used + 1} of benefit year {period.year}, over "
                            f"{plan.plan_id}'s limit of {limit} ({before} used before this "
                            f"claim)."
                        ),
                        fields_used=("member_id", *relied_on),
                    )
                )
    return sorted(hits, key=lambda hit: hit.index)
