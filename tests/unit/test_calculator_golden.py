"""The calculator against the 56 golden calculator cases (tests/golden/calculator/, assumptions A1
to A9 in tests/golden/README.md). Never change an expected value to make a test pass (H12).

Every case carries its own fee inputs (D6), so these tests run in CI without data/raw/.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    adjustments,
    allowed_amount,
    calculate,
)
from app.db.curated import load_curated
from app.domain.contracts import CostShareRule, LineDecision, Network, OtherCoverage

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "calculator"
CASES = [
    case
    for path in sorted(GOLDEN.glob("*.json"))
    for case in json.loads(path.read_text(encoding="utf-8")).get("cases", [])
]
# Cases needing a step a later P2.4 checkpoint adds; strict, so each must still fail until then.
NOT_YET = {
    # checkpoint 4: coordination of benefits (A6)
    *("C36", "C37", "C38", "C39", "C40", "C41", "C55"),
}


def inputs(given: dict[str, Any]) -> dict[str, Any]:
    curated = load_curated()
    plan = curated.plans[given["plan_id"]]
    network = Network(given["network"])
    terms = plan.in_network if network is Network.IN_NETWORK else plan.out_of_network
    assert terms is not None
    other = given["other_coverage"]
    return {
        "lines": [
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
        "network": network,
        "terms": NetworkTerms(terms.deductible_cents, terms.coinsurance_bps, terms.oop_max_cents),
        "benefits": {
            category: CostShareTerms(CostShareRule(b.cost_share_rule), b.copay_cents)
            for (plan_id, category), b in curated.benefits.items()
            if plan_id == given["plan_id"]
        },
        "fees": {code: FeeEntry(**fee) for code, fee in given["fee_schedule"].items()},
        "accumulators": Accumulators(**given["accumulators"]),
        "other_coverage": OtherCoverage.model_validate(other) if other else None,
    }


def test_there_are_56_cases() -> None:
    assert len(CASES) == 56
    assert len({case["case_id"] for case in CASES}) == 56


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_allowed_amount_and_adjustments(case: dict[str, Any]) -> None:
    """Steps 1 and 2 (A1, A9) on every approved line."""
    given = inputs(case["given"])
    expected = {a["line_no"]: a for a in case["expected"]["amounts"]["lines"]}
    for line in given["lines"]:
        if line.decision is not LineDecision.APPROVE:
            continue
        allowed = allowed_amount(line, given["network"], given["fees"][line.procedure_code])
        contractual, balance_bill = adjustments(line.billed_cents, allowed, given["network"])
        want = expected[line.line_no]
        assert (allowed, contractual, balance_bill) == (
            want["allowed_cents"],
            want["contractual_adjustment_cents"],
            want["balance_bill_exposure_cents"],
        )


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            case,
            id=case["case_id"],
            marks=[pytest.mark.xfail(strict=True, reason="later P2.4 checkpoint")]
            if case["case_id"] in NOT_YET
            else [],
        )
        for case in CASES
    ],
)
def test_golden_calculator_case(case: dict[str, Any]) -> None:
    result = calculate(**inputs(case["given"]))

    assert result.amounts.model_dump() == case["expected"]["amounts"]
    assert result.accumulators_after == Accumulators(**case["expected"]["accumulators_after"])
