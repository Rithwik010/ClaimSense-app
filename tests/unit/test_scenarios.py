"""Scenario engine and claim corpus (P3.4): labels agree with the notes, rules, context and sources.
Skipped when data/raw/ is absent (CI)."""

from datetime import date, timedelta

import pytest

from app.db import raw
from app.db.curated import load_curated
from app.domain.contracts import CriterionStatus, LineDecision, SLMOutput
from app.ml.prompt import NOT_APPLICABLE, NOT_DOCUMENTED, lines_to_decide
from training.generate.notes import LEAKAGE

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")

MODEL_REASONS = {
    "DN_NOT_MEDICALLY_NECESSARY",
    "DN_CONDITIONAL_EXCLUSION",
    "PD_MISSING_DOCUMENTATION",
}


def _train() -> set[str]:
    return {p for p, x in load_curated().policies.items() if x.split == "TRAIN"}


@pytest.fixture(scope="module")
def builders() -> dict:
    from training.generate.scenarios import ScenarioBuilder

    everything = set(load_curated().policies)
    return {
        "A": ScenarioBuilder(11, "A", _train(), _train()),
        "B": ScenarioBuilder(12, "B", everything, everything),
    }


def check(scenario) -> None:  # noqa: ANN001
    from training.generate.codebook import load_codebook

    codebook = load_codebook()
    curated = codebook.curated
    claim, rules, context, target = (
        scenario.claim,
        scenario.rules,
        scenario.context,
        scenario.target,
    )
    assert not LEAKAGE.search(claim.clinical_notes)
    assert not LEAKAGE.search(claim.model_dump_json())
    decide = lines_to_decide(rules)
    assert [c.line_no for c in context.lines] == decide
    if target is None:
        assert decide == []
        return
    SLMOutput.model_validate(target.model_dump())
    assert [line.line_no for line in target.lines] == decide
    contexts = {c.line_no: c for c in context.lines}
    for line in target.lines:
        line_context = contexts[line.line_no]
        code = line_context.procedure_code
        retrieved = {c.criterion_id: c for c in line_context.criteria}
        assert line.benefit_category in {
            f.benefit_category for f in line_context.candidate_benefits
        }
        assert [r.criterion_id for r in line.criteria] == list(retrieved)  # every one, in order
        for result in line.criteria:
            policy = curated.policies[retrieved[result.criterion_id].policy_id]
            if code not in policy.procedure_codes:
                assert result.status is CriterionStatus.NOT_APPLICABLE
            if result.status is CriterionStatus.NOT_APPLICABLE:
                assert result.evidence == NOT_APPLICABLE
            elif result.status is CriterionStatus.NOT_DOCUMENTED:
                assert result.evidence == NOT_DOCUMENTED
            else:
                assert result.evidence in claim.clinical_notes
        assert set(line.reasons) <= MODEL_REASONS
        if line.decision == LineDecision.APPROVE:
            assert not line.reasons and not line.missing_information
            assert {c.status for c in line.criteria} <= {
                CriterionStatus.MET,
                CriterionStatus.NOT_APPLICABLE,
            }
            service = claim.service_lines[line.line_no - 1]
            diagnoses = [claim.diagnoses[ord(p) - ord("A")] for p in service.diagnosis_pointers]
            assert codebook.supported(code, diagnoses)
        elif line.decision == LineDecision.PEND:
            assert line.reasons == ["PD_MISSING_DOCUMENTATION"] and line.missing_information
        else:
            assert len(line.reasons) == 1 and not line.missing_information
        if "NCCI_BYPASS" in line_context.rule_flags:
            assert target.complexity.value == "HIGH"


def test_every_scenario_type_is_consistent(builders: dict) -> None:
    from training.generate.scenarios import ALL_LINES_DENIED, SCENARIO_TYPES

    for template_set, builder in builders.items():
        for scenario_type in SCENARIO_TYPES + ALL_LINES_DENIED:
            for n in range(12):
                check(builder.build(scenario_type, f"CLM-{template_set}-{scenario_type}-{n}"))


def test_train_scenarios_never_use_test_only_policies(builders: dict) -> None:
    from training.generate.scenarios import SCENARIO_TYPES

    test_only = {p for p, x in load_curated().policies.items() if x.split == "TEST_ONLY"}
    for n in range(120):
        scenario = builders["A"].build(SCENARIO_TYPES[n % len(SCENARIO_TYPES)], f"CLM-S-{n}")
        assert not set(scenario.policy_ids) & test_only
        retrieved = {c.policy_id for line in scenario.context.lines for c in line.criteria}
        assert not retrieved & test_only


def test_decisions_follow_the_planned_states(builders: dict) -> None:
    builder = builders["A"]
    expected = {
        "approve_single": "APPROVE",
        "deny_dx": "DENY",
        "deny_criterion": "DENY",
        "deny_exclusion": "DENY",
        "pend_missing": "PEND",
    }
    for scenario_type, decision in expected.items():
        for n in range(10):
            scenario = builder.build(scenario_type, f"CLM-D-{n}")
            assert [label["decision"] for label in scenario.line_labels] == [decision]
            if scenario_type == "deny_exclusion":
                assert scenario.target.lines[0].reasons == ["DN_CONDITIONAL_EXCLUSION"]


def test_same_seed_same_scenarios() -> None:
    from training.generate.scenarios import SCENARIO_TYPES, ScenarioBuilder

    first = ScenarioBuilder(5, "A", _train(), _train())
    second = ScenarioBuilder(5, "A", _train(), _train())
    for n, scenario_type in enumerate(SCENARIO_TYPES):
        a = first.build(scenario_type, f"CLM-{n}")
        b = second.build(scenario_type, f"CLM-{n}")
        assert a.claim == b.claim and a.target == b.target and a.context == b.context


def test_claim_corpus_expected_outcomes(tmp_path) -> None:  # noqa: ANN001
    from training.generate.claims import write_corpus
    from training.generate.common import read_jsonl
    from training.generate.reference import generate_reference

    report = write_corpus(tmp_path, seed=3, forms=False)
    records = read_jsonl(tmp_path / "claims.jsonl")
    assert report["claims"] == len(records) >= 200
    reference, _ = generate_reference()
    members = {m["member_id"]: m for m in reference.members}
    curated = load_curated()
    keys = {}
    for record in records:
        claim, expected, kind = record["claim"], record["expected"], record["scenario_type"]
        assert record["metadata"]["seed"] == 3 and record["metadata"]["template_id"] in ("A", "B")
        days = [date.fromisoformat(line["date_of_service"]) for line in claim["service_lines"]]
        received = date.fromisoformat(claim["received_date"])
        key = (
            claim["member_id"],
            claim["billing_npi"],
            tuple(sorted(days)),
            tuple(line["procedure_code"] for line in claim["service_lines"]),
        )
        if kind == "DUP_duplicate":
            assert key in keys and expected["reason_codes"] == ["RJ_DUPLICATE"]
        keys[key] = record
        if kind == "R04_member_not_found":
            assert claim["member_id"] not in members
        member = members.get(claim["member_id"])
        if kind == "R05_not_eligible":
            end = member["coverage_end"]
            assert any(day < member["coverage_start"] or (end and day > end) for day in days)
        if kind == "R07_late_filing":
            window = curated.plans[member["plan_id"]].filing_window_inn_days
            assert received - max(days) > timedelta(days=window)
        if expected["rule_outcome"] == "PASS":
            assert expected["claim_decision"] in ("APPROVE", "DENY", "PEND", "PARTIAL")
            assert received - max(days) <= timedelta(days=90)
