"""Generator v2 (Part 2 step 3): every check passes on a small dataset; splits, styles and policies
are kept apart; labels are the pipeline's derivation; the new situations appear; the checks catch
planted faults. Skipped when data/raw/ is absent (CI)."""

import copy
import json
from collections import Counter

import pytest

from app.db import raw

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")

SIZES = {"train": 90, "validation": 15, "test": 45}


@pytest.fixture(scope="module")
def built() -> dict:
    from training.generate.decision_dataset_v2 import build_dataset_v2

    return build_dataset_v2(seed=77, sizes=SIZES)


@pytest.fixture(scope="module")
def checks(built: dict) -> dict:
    from training.generate.decision_dataset_v2 import run_checks_v2

    return run_checks_v2(built)


def test_every_check_passes_and_sizes_match(built: dict, checks: dict) -> None:
    assert checks["problems"] == []
    assert {split: len(records) for split, (records, _) in built["splits"].items()} == SIZES
    assert checks["test_records_with_unseen_policies"] == SIZES["test"] // 3


def test_templates_cover_every_v2_criterion() -> None:
    from app.db.curated import load_curated
    from training.generate.codebook import load_codebook
    from training.generate.scenarios_v2 import template_problems

    assert template_problems(load_curated("v2").policies, set(load_codebook().icd10)) == []


def test_styles_and_policies_per_split(built: dict) -> None:
    from training.generate.scenarios_v2 import TEST_ONLY_POLICIES, TEST_ONLY_STYLE, TRAIN_STYLES

    for split, (records, _) in built["splits"].items():
        styles = {r["metadata"]["note_style"] for r in records}
        policies = {p for r in records for p in r["metadata"]["policy_ids"]}
        if split == "test":
            assert TEST_ONLY_STYLE in styles
        else:
            assert styles <= set(TRAIN_STYLES) and not policies & TEST_ONLY_POLICIES


def test_records_use_decision_v3_policy_set_v2_and_the_rules_version(built: dict) -> None:
    from app.ml.prompt import PROMPT_V3, system_prompt
    from app.rules import RULES_VERSION

    for records, inputs in built["splits"].values():
        for record, record_inputs in zip(records, inputs, strict=True):
            meta = record["metadata"]
            assert (meta["policy_set"], meta["prompt_version"]) == ("v2", PROMPT_V3)
            assert meta["rules_version"] == RULES_VERSION
            assert record["messages"][0]["content"] == system_prompt(PROMPT_V3)
            assert json.loads(record["messages"][2]["content"]) == record_inputs["target"]


def test_labels_are_the_pipeline_derivation(built: dict) -> None:
    from app.domain.contracts import ContextPackage, RulesOutcome, SLMOutput
    from app.ml.validate import ValidationResult
    from app.workflow.decisions import final_line_decisions

    for records, inputs in built["splits"].values():
        for record, record_inputs in zip(records, inputs, strict=True):
            rules = RulesOutcome.model_validate(record_inputs["rules_outcome"])
            context = ContextPackage.model_validate(record_inputs["context"])
            target = SLMOutput.model_validate(record_inputs["target"])
            decisions = final_line_decisions(rules, ValidationResult(target, ()), context)
            labels = record["metadata"]["line_labels"]
            assert [(d.decision.value, d.source) for d in decisions] == [
                (label["decision"], label["source"]) for label in labels
            ]


def test_exclusions_are_never_met_and_requirements_never_not_applicable(built: dict) -> None:
    for _, inputs in built["splits"].values():
        for record_inputs in inputs:
            types = {
                c["criterion_id"]: c.get("criterion_type")
                for line in record_inputs["context"]["lines"]
                for c in line["criteria"]
            }
            for line in record_inputs["target"]["lines"]:
                for result in line["criteria"]:
                    kind = types[result["criterion_id"]]
                    assert not (kind == "exclusion" and result["status"] == "MET")
                    assert not (kind == "requirement" and result["status"] == "NOT_APPLICABLE")


def test_the_new_situations_appear_in_training(built: dict) -> None:
    records, inputs = built["splits"]["train"]
    text = "\n".join(r["messages"][1]["content"] for r in records)
    modifiers = Counter(
        m for i in inputs for line in i["claim"]["service_lines"] for m in line["modifiers"]
    )
    scenarios = {r["metadata"]["scenario_type"] for r in records}

    assert "flag NCCI_BYPASS (modifier" in text
    assert {"ncs_without_emg", "facet_two_regions", "extended_testing"} & scenarios
    assert modifiers  # bypass modifiers reach the claims (25, 57, 59, X, RT/LT)


def test_every_claim_passes_groups_a_and_b_with_its_authorizations(built: dict) -> None:
    """D-GEN-5: the authorizations a claim needs are in the record and the engine accepts it."""
    for _, inputs in built["splits"].values():
        for record_inputs in inputs:
            assert record_inputs["rules_outcome"]["claim_outcome"] == "PASS"
            numbers = {a["auth_number"] for a in record_inputs["authorizations"]}
            claimed = record_inputs["claim"]["prior_auth_number"]
            assert claimed is None or claimed in numbers


def test_the_checks_catch_planted_faults(built: dict) -> None:
    from training.generate.checks_v2 import check_record_v2
    from training.generate.decision_dataset_v2 import run_checks_v2

    records, inputs = built["splits"]["train"]
    index = next(
        i
        for i, r in enumerate(inputs)
        if any(c["status"] == "MET" for line in r["target"]["lines"] for c in line["criteria"])
    )
    faulty = copy.deepcopy(built)
    record, record_inputs = faulty["splits"]["train"][0][index], faulty["splits"]["train"][1][index]
    target = record_inputs["target"]
    line = next(
        line for line in target["lines"] if any(c["status"] == "MET" for c in line["criteria"])
    )
    met = next(c for c in line["criteria"] if c["status"] == "MET")
    met["evidence"] = "A sentence that is not in the notes."
    line["decision"] = "PEND" if line["decision"] != "PEND" else "DENY"
    record["messages"][2]["content"] = json.dumps(target)
    record_inputs["authorizations"] = []
    faulty["splits"]["train"] = ([record], [record_inputs])
    faulty["splits"]["validation"] = ([], [])
    faulty["splits"]["test"] = ([], [])

    problems = "\n".join(run_checks_v2(faulty)["problems"])

    assert "check 3" in problems and "check 2" in problems
    assert check_record_v2 is not None
