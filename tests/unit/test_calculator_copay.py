"""Calculator against the golden copay cases (in-network COPAY lines, §8.6).

Every golden calculator file runs in test_calculator_golden.py (P2.4); this file keeps the copay
checks of the walking skeleton.
"""

import json
from pathlib import Path

import pytest

from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    calculate,
)
from app.db.curated import load_curated
from app.domain.contracts import CostShareRule, LineDecision, Network

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "calculator"
CASES = json.loads((GOLDEN / "copay.json").read_text())["cases"]


def inputs(given: dict) -> dict:
    curated = load_curated()
    plan = curated.plans[given["plan_id"]]
    network = Network(given["network"])
    terms = plan.in_network if network is Network.IN_NETWORK else plan.out_of_network
    assert terms is not None
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
    }


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_copay_matches_golden(case: dict) -> None:
    result = calculate(**inputs(case["given"]))

    assert result.amounts.model_dump() == case["expected"]["amounts"]
    assert result.accumulators_after == Accumulators(**case["expected"]["accumulators_after"])


def test_denied_and_pended_lines_report_billed_only() -> None:
    given = json.loads(json.dumps(CASES[0]["given"]))
    given["lines"][0]["decision"] = "PEND"
    given["lines"][0]["benefit_category"] = None

    result = calculate(**inputs(given))

    line = result.amounts.lines[0].model_dump()
    assert (line.pop("line_no"), line.pop("billed_cents")) == (1, 19000)
    assert set(line.values()) == {0}
    assert result.accumulators_after == Accumulators(0, 0)


def test_copay_is_capped_at_the_remaining_out_of_pocket_maximum() -> None:
    given = json.loads(json.dumps(CASES[0]["given"]))  # PPO Gold PCP copay 2500, OOP max 300000
    given["accumulators"] = {"deductible_met_cents": 50000, "oop_met_cents": 299000}

    result = calculate(**inputs(given))

    line = result.amounts.lines[0]
    assert (line.copay_cents, line.member_pays_cents, line.plan_pays_cents) == (1000, 1000, 10899)
    assert result.accumulators_after == Accumulators(50000, 300000)
