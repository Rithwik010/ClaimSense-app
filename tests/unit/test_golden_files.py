"""Golden files are well formed (tests/golden/README.md). The engines are tested against them in
their own tasks; this checks structure, contracts, codes and arithmetic consistency only."""

import json
import re
from datetime import date
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
from scripts.verify import calculator_fixture
from scripts.verify.rules_fixture import raw_in_use, read_fixture

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
    """FY2027 billable codes: from data/raw/ or, without it (CI), from the golden rules fixture,
    which holds every case diagnosis that is in the real table (D-CI-1)."""
    if raw_in_use():
        return frozenset(raw.read_icd10_codes())
    return frozenset(read_fixture()["icd10_codes"][str(raw.ICD10_FISCAL_YEAR)])


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


@cache
def _rvus() -> dict[str, Decimal]:
    """Non-facility total RVUs: from data/raw/ or, without it (CI), from the golden calculator
    fixture, which holds every code the cases give a fee for (D-CI-2)."""
    if raw_in_use():
        codes = {code for case in CALC_CASES for code in case["given"]["fee_schedule"]}
        return {code: e.nonfacility_total_rvu for code, e in raw.read_pfs(codes).items()}
    return calculator_fixture.rvus(calculator_fixture.read_fixture())


@pytest.mark.parametrize("case", CALC_CASES, ids=ids(CALC_CASES))
def test_calculator_fee_inputs_match_the_fee_schedule_rule(case: dict[str, Any]) -> None:
    curated = load_curated()
    fee = curated.fee_rule
    for code, amounts in case["given"]["fee_schedule"].items():
        inn, oon = allowed_amounts(
            _rvus()[code],
            Decimal(fee.conversion_factor),
            fee.in_network_bps,
            fee.out_of_network_bps,
        )
        assert (amounts["inn_allowed_cents"], amounts["oon_allowed_cents"]) == (inn, oon)


# --- End-to-end ----------------------------------------------------------------------------------

E2E_CASES = load_cases("e2e")
FINAL_STATUS = {
    "APPROVE": "FINAL_APPROVED",
    "DENY": "FINAL_DENIED",
    "PEND": "FINAL_PENDED",
    "PARTIAL": "FINAL_PARTIAL",
}


def derived_decision(decisions: list[str]) -> str:
    found = set(decisions)
    if "PEND" in found:
        return "PEND"
    if found == {"DENY"}:
        return "DENY"
    if found == {"APPROVE"}:
        return "APPROVE"
    return "PARTIAL"


def test_e2e_covers_every_outcome() -> None:
    assert 25 <= len(E2E_CASES) <= 40 and len(set(ids(E2E_CASES))) == len(E2E_CASES)
    statuses = {c["expected"]["final"]["status"] for c in E2E_CASES}
    assert statuses == {
        "REJECTED",
        "DENIED_BY_RULE",
        "PENDED_BY_RULE",
        "FINAL_APPROVED",
        "FINAL_DENIED",
        "FINAL_PENDED",
        "FINAL_PARTIAL",
    }
    tiers = {(c["expected"]["recommendation"] or {}).get("review_tier") for c in E2E_CASES}
    assert {"QUICK", "STANDARD", "FULL"} <= tiers
    formats = {c["given"]["source_format"] for c in E2E_CASES}
    assert formats == {"JSON", "DIGITAL_PDF", "SCANNED"}
    actions = {(c["given"]["review_action"] or {}).get("action") for c in E2E_CASES}
    assert {"ACCEPT", "OVERRIDE"} <= actions


@pytest.mark.parametrize("case", E2E_CASES, ids=ids(E2E_CASES))
def test_e2e_case_is_consistent(case: dict[str, Any]) -> None:
    from app.domain.contracts import ReviewAction, SLMOutput

    given, expected = case["given"], case["expected"]
    assert case["worked_steps"]
    assert all(npi_is_valid(p["npi"]) for p in given["reference_additions"]["providers"])
    recommendation = expected["recommendation"]
    if recommendation is None:  # stopped by the rules: final at intake
        assert expected["final"]["status"] == expected["status_after_processing"]
        assert expected["rules"]["failures"]
        return
    IntakeClaim.model_validate(given["claim"])
    ReviewAction.model_validate(given["review_action"])
    if recommendation["output_valid"]:
        SLMOutput.model_validate(given["model_answer"])
    for stage in (recommendation, expected["final"]):
        breakdown = CostBreakdown.model_validate(stage["amounts"])
        for field in type(breakdown.totals).model_fields:
            total = sum(getattr(line, field) for line in breakdown.lines)
            assert getattr(breakdown.totals, field) == total
    decisions = [line["decision"] for line in recommendation["line_decisions"]]
    assert recommendation["claim_decision"] == derived_decision(decisions)
    final = [line["decision"] for line in expected["final"]["line_decisions"]]
    assert expected["final"]["claim_decision"] == derived_decision(final)
    assert expected["final"]["status"] == FINAL_STATUS[derived_decision(final)]


# --- RAG queries and blind review ----------------------------------------------------------------


def test_rag_queries() -> None:
    data = json.loads((GOLDEN / "rag" / "queries.json").read_text(encoding="utf-8"))
    queries = data["queries"]
    known = load_curated().criteria()
    assert 40 <= len(queries) <= 50
    assert len({q["query_id"] for q in queries}) == len(queries)
    assert sum(1 for q in queries if not q["expected_criterion_ids"]) >= 5
    for query in queries:
        assert query["plan_id"] in load_curated().plans and query["query"]
        assert 1 <= len(query["expected_criterion_ids"]) <= 3 or query.get("why_empty")
        assert set(query["expected_criterion_ids"]) <= set(known)
    covered = {cid.split(".")[0] for q in queries for cid in q["expected_criterion_ids"]}
    assert covered == set(load_curated().policies)


def live_retriever_or_skip():  # noqa: ANN201
    from app.core.settings import get_settings
    from app.rag.embedding import model_files_present
    from training.generate.decision_dataset import live_retriever

    if not model_files_present(get_settings().embedding_cache_dir):
        pytest.skip("embedding model not cached")
    retriever, label = live_retriever()
    try:
        retriever.retrieve("probe", "PLN-HMO", date(2026, 11, 2))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Qdrant collection not available ({type(exc).__name__})")
    return retriever, label


def test_blind_review_claims_and_sheet() -> None:
    from app.domain.contracts import ContextPackage, RulesOutcome
    from app.ml.prompt import lines_to_decide

    data = json.loads((GOLDEN / "blind_review" / "claims.json").read_text(encoding="utf-8"))
    claims = data["claims"]
    assert len(claims) == 30
    sheet = (GOLDEN / "blind_review" / "review_sheet.csv").read_text(encoding="utf-8").splitlines()
    rows = [row.split(",")[:2] for row in sheet[1:]]
    expected_rows = []
    for claim in claims:
        IntakeClaim.model_validate(claim["claim"])
        ContextPackage.model_validate(claim["context"])
        rules = RulesOutcome.model_validate(claim["rules_outcome"])
        expected_rows += [[claim["claim_id"], str(n)] for n in lines_to_decide(rules)]
        assert "model_answer" not in claim and "target" not in claim
    assert rows == expected_rows


@requires_raw
def test_blind_review_is_reproducible() -> None:
    """Regenerates the claims with the retrieval they were built with (the live retriever needs
    the embedding model and Qdrant's coverage_policies collection; skipped without them)."""
    from training.generate.blind_review import build

    committed = json.loads((GOLDEN / "blind_review" / "claims.json").read_text(encoding="utf-8"))
    if committed.get("retrieval", "simulated") == "simulated":
        document, sheet, _ = build()
    else:
        document, sheet, _ = build(*live_retriever_or_skip())
    assert json.loads(json.dumps(document)) == committed
    assert sheet == (GOLDEN / "blind_review" / "review_sheet.csv").read_text(encoding="utf-8")
