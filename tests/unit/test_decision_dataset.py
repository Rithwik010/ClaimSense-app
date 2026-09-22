"""P3.5 decision dataset: checks pass, splits are separated, and the checks catch leakage.
Skipped when data/raw/ is absent (CI)."""

import copy
import json

import pytest

from app.db import raw

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")

SIZES = {"train": 60, "validation": 15, "test": 45}


@pytest.fixture(scope="module")
def built() -> dict:
    from training.generate.decision_dataset import build_dataset

    return build_dataset(seed=99, sizes=SIZES)


def test_checks_pass_and_sizes_match(built: dict) -> None:
    from training.generate.decision_dataset import run_checks

    checks = run_checks(built)
    assert checks["problems"] == []
    assert {split: len(records) for split, (records, _) in built["splits"].items()} == SIZES
    assert checks["test_records_with_unseen_policies"] == SIZES["test"] // 3


def test_template_sets_per_split(built: dict) -> None:
    for split, (records, _) in built["splits"].items():
        sets = {r["metadata"]["template_id"] for r in records}
        assert sets == ({"B"} if split == "test" else {"A"})


def test_records_are_chat_triples_with_prompt_version(built: dict) -> None:
    from app.ml.prompt import PROMPT_VERSION, system_prompt

    for records, _ in built["splits"].values():
        for record in records:
            roles = [m["role"] for m in record["messages"]]
            assert roles == ["system", "user", "assistant"]
            assert record["messages"][0]["content"] == system_prompt()
            assert record["metadata"]["prompt_version"] == PROMPT_VERSION
            for key in ("generator_version", "seed", "scenario_type", "policy_id", "template_id"):
                assert key in record["metadata"]
            assert "LINES TO DECIDE:" in record["messages"][1]["content"]
            json.loads(record["messages"][2]["content"])


def test_leakage_and_label_errors_are_caught(built: dict) -> None:
    from app.db.curated import load_curated
    from training.generate.checks import check_record

    curated = load_curated()
    records, inputs = built["splits"]["train"]
    record, record_inputs = records[0], copy.deepcopy(inputs[0])
    assert check_record(record_inputs, record["messages"], curated) == []

    leaked = copy.deepcopy(record_inputs)
    leaked["claim"]["clinical_notes"] += " The injection was approved last year."
    assert any("leakage" in p for p in check_record(leaked, record["messages"], curated))

    wrong = copy.deepcopy(record["messages"])
    target = json.loads(wrong[-1]["content"])
    target["lines"][0]["criteria"].append(
        {"criterion_id": "POL-ZZZ-999.c1", "status": "MET", "evidence": "x"}
    )
    wrong[-1]["content"] = json.dumps(target)
    problems = check_record(record_inputs, wrong, curated)
    assert any("unknown criterion" in p for p in problems)


def test_same_seed_same_dataset(built: dict) -> None:
    from training.generate.decision_dataset import build_dataset

    again = build_dataset(seed=99, sizes=SIZES)
    for split in SIZES:
        assert again["splits"][split][0] == built["splits"][split][0]
