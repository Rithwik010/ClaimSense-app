"""P3.2: every number in each generated SBC matches the curated plan data (loaded into the DB)."""

import re

import pytest

from app.db.curated import load_curated
from training.generate.sbc import CATEGORY_LABELS, dollars, percent, render_markdown, render_sbc

PLANS = list(load_curated().plans)


def expected_figures(plan_id: str) -> tuple[set[str], set[str], set[int]]:
    curated = load_curated()
    plan = curated.plans[plan_id]
    money = {dollars(plan.in_network.deductible_cents), dollars(plan.in_network.oop_max_cents)}
    rates = {percent(plan.in_network.coinsurance_bps)}
    days = {plan.filing_window_inn_days}
    if plan.out_of_network:
        money |= {
            dollars(plan.out_of_network.deductible_cents),
            dollars(plan.out_of_network.oop_max_cents),
        }
        rates.add(percent(plan.out_of_network.coinsurance_bps))
        days.add(plan.filing_window_oon_days)
    for category in curated.categories:
        benefit = curated.benefit(plan_id, category)
        if benefit.copay_cents:
            money.add(dollars(benefit.copay_cents))
        if benefit.visit_limit:
            days.add(benefit.visit_limit)
    return money, rates, days


@pytest.mark.parametrize("plan_id", PLANS)
def test_every_figure_matches_the_plan(plan_id: str) -> None:
    curated = load_curated()
    text = render_markdown(curated.plans[plan_id], render_sbc(curated.plans[plan_id], curated))
    money, rates, numbers = expected_figures(plan_id)

    found_money = set(re.findall(r"\$[0-9,]+\.[0-9]{2}", text))
    found_rates = set(re.findall(r"[0-9]+(?:\.[0-9]+)?%", text))
    found_numbers = {
        int(n) for n in re.findall(r"within ([0-9]+) days|to ([0-9]+) visits", text) for n in n if n
    }

    assert found_money == money
    assert found_rates == rates
    assert found_numbers == numbers


@pytest.mark.parametrize("plan_id", PLANS)
def test_authorization_and_exclusions_match(plan_id: str) -> None:
    curated = load_curated()
    sections = render_sbc(curated.plans[plan_id], curated)
    for category in curated.categories:
        label = CATEGORY_LABELS[category]
        required = curated.benefit(plan_id, category).auth_required
        assert (label in sections["Prior authorization"]) == required, category
    for exclusion in curated.exclusions:
        description = curated.descriptions[exclusion.procedure_code]
        assert (description in sections["Excluded services"]) == (exclusion.plan_id == plan_id)


def test_plans_without_out_of_network_say_so() -> None:
    curated = load_curated()
    sections = render_sbc(curated.plans["PLN-HMO"], curated)
    assert "Out-of-network care is not covered" in sections["Important questions"]
    assert "Not covered" in sections["What you pay for covered services"]


def test_dollar_and_percent_formatting() -> None:
    assert dollars(50000) == "$500.00"
    assert dollars(1100000) == "$11,000.00"
    assert dollars(2505) == "$25.05"
    assert percent(2000) == "20%"
    assert percent(2550) == "25.50%"
