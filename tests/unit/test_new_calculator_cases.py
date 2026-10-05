"""P2.4-G: the drafting code for the new calculator golden cases (D-GOLD-2) and their blind sheet
(scripts/verify/new_calculator_cases.py).

The computation is checked against every existing golden calculator case, which the G1-G2
spot-check confirmed; the drafted cases themselves are accepted only after an independent check
(H12), so their expected values are not asserted here beyond the invariants and situations.
Tests that build the drafts need the PFS file and are skipped where data/raw/ is absent (CI).
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from app.db import raw
from app.db.curated import load_curated
from app.domain.contracts import CostBreakdown
from scripts.verify.golden_checks import check_calculator_case, situations
from scripts.verify.new_calculator_cases import (
    DRAFTS,
    build_case,
    build_sheet,
    compute,
    load_fees,
)

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "calculator"
GOLDEN_CASES = [
    case
    for path in sorted(GOLDEN.glob("*.json"))
    for case in json.loads(path.read_text(encoding="utf-8")).get("cases", [])
]
requires_raw = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")


@cache
def _drafted() -> tuple[dict[str, Any], ...]:
    curated = load_curated()
    fees = load_fees({line.procedure_code for d in DRAFTS for line in d.lines}, curated)
    return tuple(build_case(draft, curated, fees) for draft in DRAFTS)


def _drafted_case(case_id: str) -> dict[str, Any]:
    return next(case for case in _drafted() if case["case_id"] == case_id)


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["case_id"] for c in GOLDEN_CASES])
def test_the_computation_reproduces_every_golden_calculator_case(case: dict[str, Any]) -> None:
    result = compute(case["given"], load_curated())

    assert result.lines == case["expected"]["amounts"]["lines"]
    assert result.totals == case["expected"]["amounts"]["totals"]
    assert result.accumulators_after == case["expected"]["accumulators_after"]


@requires_raw
def test_the_worked_steps_reproduce_the_golden_wording() -> None:
    curated = load_curated()
    codes = {line["procedure_code"] for case in GOLDEN_CASES for line in case["given"]["lines"]}
    fees = load_fees(codes, curated)

    differing = [
        case["case_id"]
        for case in GOLDEN_CASES
        if compute(case["given"], curated, fees).steps != case["worked_steps"]
    ]

    assert not differing


def test_the_drafts_are_the_last_golden_case_ids() -> None:
    """Accepted in G3: C53-C56 follow C01-C52 with no gap."""
    numbers = sorted(int(case["case_id"][1:]) for case in GOLDEN_CASES)

    assert numbers == list(range(1, 57))
    assert [draft.case_id for draft in DRAFTS] == ["C53", "C54", "C55", "C56"]


@requires_raw
def test_the_script_still_drafts_exactly_the_accepted_golden_cases() -> None:
    golden = {case["case_id"]: case for case in GOLDEN_CASES}

    assert [golden[case["case_id"]] for case in _drafted()] == list(_drafted())


@requires_raw
def test_the_drafts_follow_the_contract_and_the_golden_invariants() -> None:
    curated = load_curated()
    for case in _drafted():
        CostBreakdown.model_validate(case["expected"]["amounts"])
        assert check_calculator_case(case, curated.plans[case["given"]["plan_id"]]) == []


def _situations(case: dict[str, Any]) -> set[str]:
    curated = load_curated()
    plan = curated.plans[case["given"]["plan_id"]]

    def benefit(category: str) -> tuple[str, int | None]:
        b = curated.benefit(plan.plan_id, category)
        return b.cost_share_rule, b.copay_cents

    return situations(case, plan, benefit)


@requires_raw
def test_each_draft_exercises_its_d_gold_2_situation() -> None:
    split, capped, cob, oop = (_drafted_case(f"C{n}") for n in (53, 54, 55, 56))

    assert "deductible spans lines" in _situations(split)
    assert "copay capped by the allowed amount" in _situations(capped)
    copay = load_curated().benefit(capped["given"]["plan_id"], "OFFICE_VISIT_SPECIALIST")
    line = capped["given"]["lines"][0]
    fee = capped["given"]["fee_schedule"][line["procedure_code"]]["inn_allowed_cents"]
    assert line["billed_cents"] < copay.copay_cents and fee * line["units"] < copay.copay_cents
    assert "COB: primary paid >= allowed" in _situations(cob)
    assert "out-of-pocket maximum reached" in _situations(oop)
    rows = oop["expected"]["amounts"]["lines"]
    assert rows[0]["member_pays_cents"] > 0 and rows[-1]["member_pays_cents"] == 0  # partway


def _ints(value: Any) -> set[int]:
    if isinstance(value, bool):
        return set()
    if isinstance(value, int):
        return {value}
    if isinstance(value, dict):
        return set().union(*(_ints(v) for v in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_ints(v) for v in value), set())
    return set()


@requires_raw
def test_the_sheet_shows_inputs_only() -> None:
    curated = load_curated()
    cases = _drafted()

    sheet = build_sheet(cases, curated)

    assert "Assumptions the case names" not in sheet and "Situations" not in sheet
    assert not any(re.search(r"^\| A-R", line) for line in sheet.splitlines())
    assert [sheet.count(f"| A{n} |") for n in range(1, 10)] == [1] * 9
    blocks = re.split(r"^### ", sheet, flags=re.MULTILINE)[1:]
    assert [block.split("(")[1].split(")")[0] for block in blocks] == [c["case_id"] for c in cases]
    for case, block in zip(cases, blocks, strict=True):
        assert case["title"] not in sheet
        assert not any(step.strip() in sheet for step in case["worked_steps"])
        plan = curated.plans[case["given"]["plan_id"]]
        terms = plan.in_network if case["given"]["network"] == "IN_NETWORK" else plan.out_of_network
        shown = _ints(case["given"]) | {
            terms.deductible_cents,
            terms.coinsurance_bps,
            terms.oop_max_cents,
            *(
                curated.benefit(plan.plan_id, line["benefit_category"]).copay_cents or 0
                for line in case["given"]["lines"]
            ),
        }
        answers = {v for v in _ints(case["expected"]) if v >= 100} - shown
        unquoted = "\n".join(line for line in block.splitlines() if not line.startswith(">"))
        leaked = sorted(v for v in answers if re.search(rf"\b{v}\b", unquoted))
        assert not leaked, (case["case_id"], leaked)
        answer_rows = [
            line for line in block.splitlines() if re.fullmatch(r"\| \d+ (\|  )+\|", line)
        ]
        assert len(answer_rows) == len(case["given"]["lines"])
