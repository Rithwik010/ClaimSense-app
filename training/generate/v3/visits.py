"""No generated claim sends a line beyond its plan's yearly visit limit to the model (D-V3-8).

The same count as rule R21 (D-RULE-10, on branch p7-visit-limit-review-codes): in a visit-limited
benefit category (a code whose only candidate category has a `visit_limit` on the member's plan),
one visit per date of service among the lines that pass the rules; the visits the member used in
the claim's benefit year (the calendar year of its first date of service) count first, then the
claim's dates in date order. A line on a date beyond the limit would be denied by R21 before the
model, so it must not be a model training example: the generator drops such a claim and draws
another (the visits stay within the limits). Plain dicts, as the sheets and records hold them.
"""

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from app.db.curated import CuratedData


def usage_index(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str, date], int]:
    """(member ID, benefit category, period start) -> visits used, from visit_usage rows."""
    found = {}
    for row in rows:
        start = row["period_start"]
        start = start if isinstance(start, date) else date.fromisoformat(start)
        found[(row["member_id"], row["benefit_category"], start)] = int(row["visits_used"])
    return found


def over_limit_lines(
    claim: Mapping[str, Any],
    rules_outcome: Mapping[str, Any],
    plan_of: Mapping[str, str],
    usage: Mapping[tuple[str, str, date], int],
    curated: CuratedData,
) -> list[int]:
    """The line numbers that pass the rules but fall on a date beyond the visit limit."""
    plan = plan_of.get(claim["member_id"])
    if plan is None:
        return []
    passing = {o["line_no"] for o in rules_outcome["line_outcomes"] if o["outcome"] == "PASS"}
    lines = claim["service_lines"]
    first = min(date.fromisoformat(str(line["date_of_service"])) for line in lines)
    period = date(first.year, 1, 1)
    days: dict[str, dict[date, list[int]]] = {}
    for line in lines:
        scope = curated.scope.get(line["procedure_code"])
        if scope is None or len(scope.candidate_categories) != 1:
            continue
        category = scope.candidate_categories[0]
        if curated.benefit(plan, category).visit_limit is None:
            continue
        day = date.fromisoformat(str(line["date_of_service"]))
        days.setdefault(category, {}).setdefault(day, []).append(line["line_no"])
    over: list[int] = []
    for category, by_day in days.items():
        limit = curated.benefit(plan, category).visit_limit
        used = usage.get((claim["member_id"], category, period), 0)
        for day in sorted(by_day):
            numbers = by_day[day]
            if not passing & set(numbers):
                continue  # every line of the date is denied by a rule: no visit
            if used < limit:
                used += 1
            else:
                over += [n for n in numbers if n in passing]
    return sorted(over)
