"""What a set of v3 fact sheets teaches, cell by cell (D-V3-6; SPEC.md "Sizes and top-ups").

A cell is one thing the model must see enough examples of, with its floor in config.yaml
(`top_up.floors`):

- `policy_decision`: the lines the model decides, per policy and line decision;
- `criterion_status`: each criterion's label status on those lines;
- `tricky`: per policy, the facts stated at a borderline, contradicted and corrected, missing,
  negated (an exclusion stated in the negative) or hedged;
- `borderline`: per borderline criterion, the facts on each side of its threshold.

A fact counts only when it belongs to a line the model decides: a line a rule denies is shown to
the model as decided, so its facts teach no label.

The training split is topped up until every cell reaches its floor (dataset.top_up_sheets); the
other splits keep the natural distribution. scripts/verify/v3_coverage.py reports the same cells.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

KINDS = ("policy_decision", "criterion_status", "tricky", "borderline")
NO_CRITERIA = "(no criteria)"

Cell = tuple[str, str]  # (kind, name)


def policy_of(criterion_id: str) -> str:
    return criterion_id.split(".")[0]


def line_policies(context: Mapping[str, Any]) -> dict[int, str]:
    """Each line's policy: the policy of its first retrieved criterion, else no criteria."""
    return {
        line["line_no"]: policy_of(line["criteria"][0]["criterion_id"])
        if line["criteria"]
        else NO_CRITERIA
        for line in context["lines"]
    }


def sheet_cells(sheet: Mapping[str, Any]) -> Counter[Cell]:
    """The cells one sheet adds to, with how many examples of each."""
    found: Counter[Cell] = Counter()
    policies = line_policies(sheet["inputs"]["context"])
    decided = {line["line_no"] for line in sheet["label"]["target"]["lines"]}
    for line in sheet["label"]["target"]["lines"]:
        policy = policies.get(line["line_no"], NO_CRITERIA)
        found[("policy_decision", f"{policy} {line['decision']}")] += 1
        for criterion in line["criteria"]:
            found[("criterion_status", f"{criterion['criterion_id']} {criterion['status']}")] += 1
    for fact in sheet["facts"]:
        if fact["kind"] != "criterion" or not decided & set(fact.get("lines") or []):
            continue
        policy = policy_of(fact["criterion_id"])
        status = fact["status"]
        if status.startswith("borderline"):
            found[("tricky", f"{policy} borderline")] += 1
            side = status.removeprefix("borderline_")
            found[("borderline", f"{fact['criterion_id']} {side}")] += 1
        elif status in ("contradicted", "missing"):
            found[("tricky", f"{policy} {status}")] += 1
        if fact.get("negated"):
            found[("tricky", f"{policy} negated")] += 1
        if fact.get("hedge"):
            found[("tricky", f"{policy} hedged")] += 1
    return found


def cell_counts(sheets: Iterable[Mapping[str, Any]]) -> Counter[Cell]:
    total: Counter[Cell] = Counter()
    for sheet in sheets:
        total.update(sheet_cells(sheet))
    return total


def below(counts: Mapping[Cell, int], floors: Mapping[str, int]) -> dict[Cell, int]:
    """Every cell under its floor, with how many examples it still needs. Only cells that occur
    at all count: a cell no sheet can produce (a status a criterion never takes) has no floor."""
    return {
        cell: floors[cell[0]] - n
        for cell, n in sorted(counts.items())
        if cell[0] in floors and n < floors[cell[0]]
    }


def by_kind(counts: Mapping[Cell, int]) -> dict[str, dict[str, int]]:
    found: dict[str, dict[str, int]] = {kind: {} for kind in KINDS}
    for (kind, name), n in sorted(counts.items()):
        found[kind][name] = n
    return found
