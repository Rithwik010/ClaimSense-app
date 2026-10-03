"""P2.3a parity, frozen for model v1 (PROGRESS_LOG.md section 2): on every train, validation and
test record, the engine gives the claim outcome, claim flags and line outcomes (reasons in order,
NCCI_BYPASS) the generator's rule mirror stored, and the prompt's RULES_RESULT block is what the
engine's outcome renders to (scripts/verify/rules_parity.py).

The dataset check is skipped where the dataset or data/raw/ is absent (CI)."""

import pytest

from app.db import raw
from app.domain.contracts import RulesOutcome
from scripts.verify.rules_parity import (
    DECISION_DIR,
    Record,
    dataset_reference,
    differences,
    load_records,
    prompt_block,
    rules_block,
)
from tests.unit.rules_support import claim_data, line, reference

DATASET_PRESENT = (DECISION_DIR / "train_inputs.jsonl").exists() and raw.raw_available()


@pytest.mark.skipif(not DATASET_PRESENT, reason="model v1 dataset or data/raw/ not present")
def test_every_dataset_record_matches_the_generators_rule_mirror() -> None:
    records = load_records()
    reference = dataset_reference()

    found = {r.record_id: diff for r in records if (diff := differences(r, reference))}

    assert len(records) == 2600
    assert not found, list(found.items())[:10]


STORED = {
    "claim_outcome": "PASS",
    "rule_results": [],
    "line_outcomes": [
        {"line_no": 1, "outcome": "DENY", "reason_codes": ["DN_EXCLUDED"], "flags": []},
        {"line_no": 2, "outcome": "PASS", "reason_codes": [], "flags": []},
    ],
    "flags": [],
}
BLOCK = (
    "RULES_RESULT\n"
    "Claim outcome: PASS\n"
    "Line 1: DENIED by rule (DN_EXCLUDED); do not decide this line\n"
    "Line 2: PASS"
)


def _record(stored: dict, message: str) -> Record:
    lines = [line(procedure_code="97140"), line(line_no=2)]
    return Record("train", "DEC-1", claim_data(service_lines=lines), stored, "IN_NETWORK", message)


def test_the_rules_block_is_rendered_as_the_prompt_shows_it() -> None:
    outcome = RulesOutcome.model_validate({**STORED, "flags": ["OON"]})

    assert rules_block(outcome).splitlines()[1] == "Claim outcome: PASS (claim flags: OON)"
    assert prompt_block(f"CLAIM\nx\n\n{BLOCK}\n\nPLAN_BENEFITS\ny") == BLOCK


def test_a_matching_record_has_no_differences() -> None:
    record = _record(STORED, f"CLAIM\n\n{BLOCK}\n\nPLAN_BENEFITS")

    assert differences(record, reference()) == []


def test_a_different_line_outcome_flag_or_prompt_is_reported() -> None:
    stored = {**STORED, "line_outcomes": [STORED["line_outcomes"][1]] * 2, "flags": ["OON"]}
    record = _record(stored, f"CLAIM\n\n{BLOCK.replace('PASS', 'DENY', 1)}\n\nPLAN_BENEFITS")

    found = differences(record, reference())

    assert found[0] == "claim flags [] != ['OON']"
    assert found[1].startswith("line 1:")
    assert found[-1] == "the prompt's RULES_RESULT block differs from the engine's"
