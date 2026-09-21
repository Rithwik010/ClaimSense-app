"""Golden files are well formed (tests/golden/README.md). The engines are tested against them in
their own tasks; this checks structure, contracts, codes and arithmetic consistency only."""

import json
import re
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.calculator.fee_schedule import allowed_amounts
from app.db import raw
from app.db.curated import load_curated
from app.domain.contracts import CostBreakdown, IntakeClaim, npi_is_valid

GOLDEN = Path(__file__).resolve().parents[1] / "golden"
STATUS = {
    "PASS": "RECEIVED",
    "REJECT": "REJECTED",
    "DENY": "DENIED_BY_RULE",
    "PEND": "PENDED_BY_RULE",
}
CONTRACT_RULES = {"R01", "R02", "R03"}
requires_raw = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")


def load_cases(folder: str) -> list[dict[str, Any]]:
    cases = []
    for path in sorted((GOLDEN / folder).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cases.extend(data.get("cases", []))
    return cases


RULE_CASES = load_cases("rules")
CALC_CASES = load_cases("calculator")
README = (GOLDEN / "README.md").read_text(encoding="utf-8")


def ids(cases: list[dict[str, Any]]) -> list[str]:
    return [c["case_id"] for c in cases]


def test_case_counts_and_unique_ids() -> None:
    assert len(RULE_CASES) >= 80
    assert len(CALC_CASES) >= 50
    for cases in (RULE_CASES, CALC_CASES):
        assert len(set(ids(cases))) == len(cases)


# --- Rules ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", RULE_CASES, ids=ids(RULE_CASES))
def test_rules_case_is_well_formed(case: dict[str, Any]) -> None:
    reasons = load_curated().reason_codes
    expected = case["expected"]
    assert case["worked_steps"]
    assert expected["status"] == STATUS[expected["claim_outcome"]]
    for failure in expected["failures"]:
        assert re.fullmatch(r"R[0-9]{2}|DUP", failure["rule_id"])
        entry = reasons[failure["reason_code"]]
        assert entry.outcome == failure["outcome"]
    if expected["claim_outcome"] != "PASS":
        assert expected["failures"], "a stopped claim needs at least one failure"
    for path, value in case["given"]["field_confidences"].items():
        assert re.fullmatch(r"[a-z_]+(\.([a-z_0-9]+))*", path) and 0.0 <= value <= 1.0


@pytest.mark.parametrize("case", RULE_CASES, ids=ids(RULE_CASES))
def test_rules_case_line_outcomes_cover_every_line(case: dict[str, Any]) -> None:
    outcomes = case["expected"]["line_outcomes"]
    if outcomes is None:
        return
    lines = case["given"]["claim"]["service_lines"]
    assert [o["line_no"] for o in outcomes] == [line["line_no"] for line in lines]
    denied = [o for o in outcomes if o["outcome"] == "DENY"]
    assert all(o["reason_codes"] for o in denied)
    if case["expected"]["claim_outcome"] == "DENY":
        assert len(denied) == len(outcomes), "a Group C claim denial means every line is denied"


@pytest.mark.parametrize("case", RULE_CASES, ids=ids(RULE_CASES))
def test_invalid_claims_are_contract_rule_cases(case: dict[str, Any]) -> None:
    rules = {f["rule_id"] for f in case["expected"]["failures"]}
    try:
        IntakeClaim.model_validate(case["given"]["claim"])
    except ValidationError:
        assert rules & CONTRACT_RULES, "only R01-R03 cases may hold contract-invalid claims"
    else:
        assert "R01" not in rules and "R03" not in rules


def test_reference_fixture_npis_are_valid() -> None:
    reference = json.loads((GOLDEN / "rules" / "reference.json").read_text(encoding="utf-8"))
    assert all(npi_is_valid(p["npi"]) for p in reference["providers"])
    assert {m["plan_id"] for m in reference["members"]} <= set(load_curated().plans)


@cache
def _icd10() -> frozenset[str]:
    return frozenset(raw.read_icd10_codes())


@requires_raw
@pytest.mark.parametrize("case", RULE_CASES, ids=ids(RULE_CASES))
def test_rules_case_codes_exist_unless_r02(case: dict[str, Any]) -> None:
    if any(f["rule_id"] in CONTRACT_RULES for f in case["expected"]["failures"]):
        return
    claim = case["given"]["claim"]
    assert {d.replace(".", "").upper() for d in claim["diagnoses"]} <= _icd10()
    assert {line["procedure_code"] for line in claim["service_lines"]} <= set(load_curated().scope)


# --- Calculator ----------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CALC_CASES, ids=ids(CALC_CASES))
def test_calculator_case_is_consistent(case: dict[str, Any]) -> None:
    curated = load_curated()
    given, expected = case["given"], case["expected"]
    assert case["worked_steps"]
    assert given["plan_id"] in curated.plans
    for assumption in case["assumptions"]:
        assert f"| {assumption} |" in README
    breakdown = CostBreakdown.model_validate(expected["amounts"])
    lines = {line["line_no"]: line for line in given["lines"]}
    for amounts in breakdown.lines:
        line = lines[amounts.line_no]
        assert amounts.billed_cents == line["billed_cents"]
        if line["decision"] != "APPROVE":
            assert (
                amounts.allowed_cents == amounts.plan_pays_cents == amounts.member_pays_cents == 0
            )
            continue
        assert line["benefit_category"] in curated.categories
        cost_share = amounts.deductible_cents + amounts.copay_cents + amounts.coinsurance_cents
        assert amounts.allowed_cents <= amounts.billed_cents
        if amounts.cob_primary_paid_cents == 0:
            assert amounts.plan_pays_cents == amounts.allowed_cents - cost_share
            assert amounts.member_pays_cents == cost_share
    for field in type(breakdown.totals).model_fields:
        assert getattr(breakdown.totals, field) == sum(getattr(a, field) for a in breakdown.lines)


@requires_raw
@pytest.mark.parametrize("case", CALC_CASES, ids=ids(CALC_CASES))
def test_calculator_fee_inputs_match_the_fee_schedule_rule(case: dict[str, Any]) -> None:
    curated = load_curated()
    fee = curated.fee_rule
    pfs = raw.read_pfs(set(case["given"]["fee_schedule"]))
    for code, amounts in case["given"]["fee_schedule"].items():
        entry = pfs[code]
        inn, oon = allowed_amounts(
            entry.nonfacility_total_rvu,
            Decimal(fee.conversion_factor),
            fee.in_network_bps,
            fee.out_of_network_bps,
        )
        assert (amounts["inn_allowed_cents"], amounts["oon_allowed_cents"]) == (inn, oon)
