"""The checks run on every file before a Kaggle upload (scripts/verify/kaggle_upload_check.py):
records come from the generator, show only age and sex for the patient and the team's own code
descriptions. The AMA descriptor guard needs data/raw and runs with the script."""

import json

from app.db.curated import load_curated
from scripts.verify.kaggle_upload_check import record_problems

USER = """CLAIM
Claim ID: CLM-V2TR-00000
Patient: 78-year-old, sex M
Service lines:
  1. 2026-10-10 | POS 11 | 99203 {desc} | modifiers: none | units 1 | diagnoses: A
"""


def write(tmp_path, user: str, generator: str = "scenarios-v2"):  # noqa: ANN001, ANN201
    path = tmp_path / "train.jsonl"
    record = {
        "messages": [{"role": "user", "content": user}],
        "metadata": {"generator_version": generator, "record_id": "DV2-TR-00001"},
    }
    path.write_text(json.dumps(record) + "\n")
    return path


def test_a_generated_record_with_our_description_passes(tmp_path) -> None:  # noqa: ANN001
    descriptions = load_curated().descriptions
    path = write(tmp_path, USER.format(desc=descriptions["99203"]))

    assert record_problems(path, descriptions) == ([], {"99203"}, 1)


def test_another_description_a_name_or_a_foreign_record_is_a_problem(tmp_path) -> None:  # noqa: ANN001
    descriptions = load_curated().descriptions
    user = USER.format(desc="Some other text").replace("78-year-old, sex M", "Jane Doe")
    problems = record_problems(write(tmp_path, user, "unknown"), descriptions)[0]

    assert [p.split(": ", 1)[1] for p in problems] == [
        "generator 'unknown'",
        "patient shown as 'Jane Doe'",
        "99203 shown as 'Some other text', not our description",
    ]
