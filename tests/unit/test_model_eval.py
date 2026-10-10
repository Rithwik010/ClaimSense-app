"""Model evaluation (P4.2 / P4.4) on a small generated test split with stub models.
Skipped when data/raw/ is absent (CI)."""

import json

import pytest

from app.db import raw

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")


class Answers:
    """Answers each record with its target (perfect) or with fixed text."""

    def __init__(self, targets: dict[str, str] | None = None, text: str = "") -> None:
        self.name = "stub"
        self.targets = targets or {}
        self.text = text
        self.calls = 0

    def complete(self, system: str, user: str, attempt: int = 1) -> str:
        self.calls += 1
        return self.targets.get(user, self.text)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory) -> tuple:  # noqa: ANN001
    from training.generate.common import write_jsonl
    from training.generate.decision_dataset import build_dataset

    out = tmp_path_factory.mktemp("decision")
    built = build_dataset(seed=3, sizes={"train": 3, "validation": 3, "test": 24})
    records, inputs = built["splits"]["test"]
    write_jsonl(out / "test.jsonl", records)
    write_jsonl(out / "test_inputs.jsonl", inputs)
    validation_records, validation_inputs = built["splits"]["validation"]
    write_jsonl(out / "validation.jsonl", validation_records)
    write_jsonl(out / "validation_inputs.jsonl", validation_inputs)
    (out / "summary.json").write_text(json.dumps({"generator_version": "t", "seed": 3}))
    targets = {r["messages"][1]["content"]: r["messages"][2]["content"] for r in records}
    return out, targets, len(records)


def test_a_perfect_model_scores_one_everywhere(dataset, tmp_path) -> None:  # noqa: ANN001
    from training.evaluate.model import results_markdown, run

    directory, targets, count = dataset
    report = run(Answers(targets), "perfect", directory, tmp_path)

    metrics = report["metrics"]
    assert metrics["records"] == count
    assert metrics["valid_output_rate"] == 1.0
    assert metrics["decisions"]["accuracy"] == 1.0 and metrics["decisions"]["macro_f1"] == 1.0
    assert metrics["criterion_status_accuracy"] == 1.0
    assert metrics["evidence_quoted_rate"] in (1.0, None)
    assert metrics["claim_decision_accuracy"] == 1.0
    assert metrics["groups"]["unseen_policies"]["records"] == 8  # a third of the test split
    assert "| perfect | stub |" in results_markdown(tmp_path)
    assert "| test |" in results_markdown(tmp_path)  # the split a run was measured on


def test_the_ablation_removes_only_the_retrieved_criteria(dataset, tmp_path) -> None:  # noqa: ANN001
    """P4.4: what retrieval contributes. The claim, the rules result and the plan benefits stay."""
    from training.evaluate.model import run, without_criteria

    directory, _, _ = dataset
    seen: list[str] = []

    class Recorder(Answers):
        def complete(self, system: str, user: str, attempt: int = 1) -> str:
            seen.append(user)
            return super().complete(system, user)

    report = run(Recorder(text="{}"), "ablated", directory, tmp_path, ablate_criteria=True)

    assert report["context"] == "no retrieved criteria"
    assert all("No criteria retrieved." in prompt for prompt in seen)
    assert all("RULES_RESULT" in prompt and "PLAN_BENEFITS" in prompt for prompt in seen)

    inputs = {"claim": {}, "rules_outcome": {}, "context": {"lines": [{"criteria": [1, 2]}]}}
    stripped = without_criteria(inputs)
    assert stripped["context"]["lines"] == [{"criteria": []}]
    assert inputs["context"]["lines"][0]["criteria"] == [1, 2]  # the original is untouched


def test_the_validation_split_can_be_evaluated_as_a_diagnostic(dataset, tmp_path) -> None:  # noqa: ANN001
    """P4.4: the same-template, seen-policy ceiling, to tell a wording gap from a policy one."""
    from training.evaluate.model import results_markdown, run

    directory, _, _ = dataset
    report = run(Answers(text="nonsense"), "diagnostic", directory, tmp_path, split="validation")

    assert report["split"] == "validation"
    assert report["metrics"]["records"] == 3  # the validation split, not the 24 test records
    assert "| validation |" in results_markdown(tmp_path)


def test_invalid_answers_count_as_pend(dataset, tmp_path) -> None:  # noqa: ANN001
    from training.evaluate.model import run

    directory, _, count = dataset
    report = run(Answers(text="I think it is fine."), "garbage", directory, tmp_path)

    metrics = report["metrics"]
    assert metrics["valid_output_rate"] == 0.0
    confusion = metrics["decisions"]["confusion_matrix"]["rows_gold_columns_predicted"]
    assert all(row[0] == 0 and row[2] == 0 for row in confusion)  # every line predicted PEND


def test_a_stopped_run_resumes(dataset, tmp_path) -> None:  # noqa: ANN001
    from training.evaluate.model import run

    directory, targets, count = dataset
    first = Answers(targets)
    run(first, "resume", directory, tmp_path, limit=5)
    second = Answers(targets)
    report = run(second, "resume", directory, tmp_path)

    assert (first.calls, second.calls) == (5, count - 5)
    assert report["metrics"]["records"] == count
    assert "5/" in (tmp_path / "resume.log").read_text()


def test_a_run_does_not_resume_on_another_engine(dataset, tmp_path) -> None:  # noqa: ANN001
    from training.evaluate.model import run

    directory, targets, _ = dataset
    run(Answers(targets), "engine", directory, tmp_path, limit=2, engine="ollama 1")

    with pytest.raises(SystemExit, match="must not mix engines"):
        run(Answers(targets), "engine", directory, tmp_path, engine="ollama 2")
    report = run(Answers(targets), "engine", directory, tmp_path, engine="ollama 1")
    assert report["engine"] == "ollama 1"


def test_a_dropped_connection_is_retried_then_fails() -> None:
    from app.ml.client import ModelUnavailable
    from training.evaluate.model import complete_with_retry

    class Flaky:
        name = "flaky"

        def __init__(self, failures: int) -> None:
            self.failures = failures

        def complete(self, system: str, user: str, attempt: int = 1) -> str:
            if self.failures:
                self.failures -= 1
                raise ModelUnavailable("down")
            return "ok"

    waits: list[float] = []
    assert complete_with_retry(Flaky(2), "s", "u", waits.append) == "ok"
    assert waits == [15, 45]
    with pytest.raises(ModelUnavailable):
        complete_with_retry(Flaky(3), "s", "u", waits.append)
