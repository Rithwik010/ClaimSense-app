"""The calculator's invariants on 5,000 seeded random claims (P2.4).

Every claim's result, in the golden case format, goes through the same checks the golden cases
pass (scripts/verify/golden_checks.check_calculator_case): plan pays + member pays = max(0, allowed
- primary paid); allowed <= billed; no negative amounts; integer cents; member pays <= the
remaining out-of-pocket maximum and deductible applied <= the remaining deductible (working totals);
copay <= allowed; denied and pended lines pay 0; totals = sum of lines (A8); accumulators after =
before + the claim's cost share (A5).

Claims vary plans, networks, cost-share rules, units, billed above and below the fee, accumulators
at and near their limits, COB with the primary paying above, at and below allowed or nothing, and
denied and pended lines. Plain seeded Python (`random.Random`), no property-testing library.
"""

import random
from functools import cache
from typing import Any

from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    calculate,
)
from app.db.curated import load_curated
from app.domain.contracts import CostShareRule, LineDecision, Network, OtherCoverage
from scripts.verify.golden_checks import check_calculator_case, situations

SEED = 20261004
CLAIMS = 5000


def _near(rng: random.Random, limit: int) -> int:
    """An accumulator value: none met, just under, exactly at, above or anywhere below the limit."""
    return rng.choice(
        [0, max(0, limit - rng.randint(1, 3000)), limit, limit + rng.randint(1, 500)]
        + [rng.randint(0, limit)] * 2
    )


def random_claim(rng: random.Random, number: int) -> dict[str, Any]:
    curated = load_curated()
    plan = rng.choice(sorted(curated.plans.values(), key=lambda p: p.plan_id))
    network = "OUT_OF_NETWORK" if plan.out_of_network and rng.random() < 0.3 else "IN_NETWORK"
    terms = plan.in_network if network == "IN_NETWORK" else plan.out_of_network
    categories = sorted(c for p, c in curated.benefits if p == plan.plan_id)
    lines, fees, primary = [], {}, []
    for line_no in range(1, rng.choice([1, 1, 2, 2, 3, 4, 5]) + 1):
        code = f"R{rng.randint(1, 40):04d}"
        fee = fees.setdefault(
            code,
            {
                "inn_allowed_cents": (inn := rng.randint(100, 60000)),
                "oon_allowed_cents": inn * 4 // 5,
            },
        )
        units = rng.choice([1, 1, 1, 2, 3, 4])
        per_unit = fee["inn_allowed_cents" if network == "IN_NETWORK" else "oon_allowed_cents"]
        billed = max(1, round(per_unit * units * rng.uniform(0.3, 2.0)))
        decision = rng.choices(["APPROVE", "DENY", "PEND"], weights=[75, 15, 10])[0]
        lines.append(
            {
                "line_no": line_no,
                "procedure_code": code,
                "units": units,
                "billed_cents": billed,
                "decision": decision,
                "benefit_category": rng.choice(categories) if decision == "APPROVE" else None,
            }
        )
        if rng.random() < 0.35:  # this line paid by a primary plan: above, at or below allowed
            allowed = min(billed, per_unit * units)
            paid = rng.choice(
                [rng.randint(1, max(1, allowed)), allowed, allowed + rng.randint(1, 5000), 0]
            )
            primary.append({"line_no": line_no, "paid_cents": paid})
    return {
        "case_id": f"P{number:05d}",
        "given": {
            "plan_id": plan.plan_id,
            "network": network,
            "accumulators": {
                "deductible_met_cents": _near(rng, terms.deductible_cents),
                "oop_met_cents": _near(rng, terms.oop_max_cents),
            },
            "fee_schedule": fees,
            "lines": lines,
            "other_coverage": (
                {"payer_name": "Primary Plan", "primary_paid": primary} if primary else None
            ),
        },
    }


def run(case: dict[str, Any]) -> dict[str, Any]:
    """The calculator on a golden-format case; returns the case with `expected` filled in."""
    curated = load_curated()
    given = case["given"]
    plan = curated.plans[given["plan_id"]]
    network = Network(given["network"])
    terms = plan.in_network if network is Network.IN_NETWORK else plan.out_of_network
    result = calculate(
        lines=[
            CalcLine(
                line_no=line["line_no"],
                procedure_code=line["procedure_code"],
                units=line["units"],
                billed_cents=line["billed_cents"],
                decision=LineDecision(line["decision"]),
                benefit_category=line["benefit_category"],
            )
            for line in given["lines"]
        ],
        network=network,
        terms=NetworkTerms(terms.deductible_cents, terms.coinsurance_bps, terms.oop_max_cents),
        benefits={
            category: CostShareTerms(CostShareRule(b.cost_share_rule), b.copay_cents)
            for (plan_id, category), b in curated.benefits.items()
            if plan_id == plan.plan_id
        },
        fees={code: FeeEntry(**fee) for code, fee in given["fee_schedule"].items()},
        accumulators=Accumulators(**given["accumulators"]),
        other_coverage=(
            OtherCoverage.model_validate(given["other_coverage"])
            if given["other_coverage"]
            else None
        ),
    )
    after = result.accumulators_after
    return {
        **case,
        "expected": {
            "amounts": result.amounts.model_dump(),
            "accumulators_after": {
                "deductible_met_cents": after.deductible_met_cents,
                "oop_met_cents": after.oop_met_cents,
            },
        },
    }


@cache
def _results() -> tuple[dict[str, Any], ...]:
    rng = random.Random(SEED)
    return tuple(run(random_claim(rng, n)) for n in range(1, CLAIMS + 1))


def test_every_invariant_holds_on_5000_random_claims() -> None:
    curated = load_curated()

    findings = [
        finding
        for case in _results()
        for finding in check_calculator_case(case, curated.plans[case["given"]["plan_id"]])
    ]

    assert len(_results()) == CLAIMS
    assert not findings, findings[:5]


def test_the_random_claims_reach_every_situation() -> None:
    """The generator is varied enough: every cost-share situation appears many times."""
    curated = load_curated()
    counts: dict[str, int] = {}
    for case in _results():
        plan = curated.plans[case["given"]["plan_id"]]

        def benefit(category: str, plan_id: str = plan.plan_id) -> tuple[str, int | None]:
            b = curated.benefit(plan_id, category)
            return b.cost_share_rule, b.copay_cents

        for name in situations(case, plan, benefit):
            counts[name] = counts.get(name, 0) + 1
    wanted = {
        "copay only",
        "deductible not met",
        "deductible partly met",
        "deductible met",
        "coinsurance",
        "out-of-pocket maximum reached",
        "out-of-network PPO",
        "COB secondary",
        "COB: primary paid >= allowed",
        "denied line in a multi-line claim",
        "pended line",
        "deductible spans lines",
        "copay capped by the allowed amount",
        "billed below the fee schedule",
        "units > 1",
        "out-of-network copay category (A3)",
    }

    assert {name: counts.get(name, 0) for name in wanted if counts.get(name, 0) < 20} == {}
