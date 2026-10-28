"""D-UI-6: the reason table covers every internal reason code the system can produce, in the agreed
shape; one label set for every claim status."""

import ast
import csv
import re
from pathlib import Path

import pytest

from app.db import raw
from app.domain.contracts import ClaimStatus, LineDecision
from app.explain.codes import official
from app.explain.reasons import (
    FLAG_ONLY_RULES,
    OUTCOME_LABELS,
    REASONS,
    REVIEWER_DENIED,
    REVIEWER_PENDED,
    STATUS_OUTCOMES,
    claim_outcome,
    provider_outcome,
)
from app.rules.confidence import LOW_CONFIDENCE_REASON
from app.rules.line_edits import RULE_OF
from tests.unit.ui_records import final, model_record, rule_record

ROOT = Path(__file__).resolve().parents[2]
CODE = re.compile(r"^(?:(?:RJ|DN|PD)_[A-Z0-9_]+|MODEL_OUTPUT_INVALID)$")
# What a provider sentence never holds: rule IDs, internal codes and the jargon behind them.
JARGON = re.compile(
    r"\bR[0-9]{2}\b|\bDUP\b|_|\b(?:NCCI|MUE|LCD|CARC|RARC|H5|PTP|ESI|model|SLM)\b", re.IGNORECASE
)


def produced_codes() -> set[str]:
    """Every string constant in the application that looks like an internal reason code: the
    codes the rules, the line derivation and output validation can write."""
    found = set()
    for path in (ROOT / "app").rglob("*.py"):
        if path.parent.name == "explain":
            continue  # the table itself and the explanation labels
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if CODE.match(node.value):
                    found.add(node.value)
    return found


def mapped_codes() -> set[str]:
    with (ROOT / "data" / "curated" / "reason_code_map.csv").open(encoding="utf-8") as f:
        return {row["internal_code"] for row in csv.DictReader(f)}


def test_every_reason_code_the_system_can_produce_has_an_entry() -> None:
    codes = produced_codes()
    assert len(codes) >= 24  # the scan found the codes (rules, derivation, validation)
    assert LOW_CONFIDENCE_REASON in codes and "PD_MISSING_DOCUMENTATION" in codes

    missing = (codes | mapped_codes() | {REVIEWER_DENIED, REVIEWER_PENDED}) - set(REASONS)

    assert missing == set()


def test_every_entry_is_a_code_the_system_produces_or_a_reviewer_key() -> None:
    assert set(REASONS) - produced_codes() - mapped_codes() == {REVIEWER_DENIED, REVIEWER_PENDED}


def test_rules_r01_to_r20_and_the_duplicate_check_are_all_accounted_for() -> None:
    covered = {rule for entry in REASONS.values() for rule in entry.rules}
    wanted = {f"R{n:02d}" for n in range(1, 21)} | {"DUP"}

    assert wanted - covered == set(FLAG_ONLY_RULES)
    for code, rule in RULE_OF.items():  # the line rules' own map agrees with the table
        assert REASONS[code].rules == (rule,)


@pytest.mark.parametrize("code", sorted(REASONS))
def test_each_entry_has_a_short_reason_a_plain_sentence_and_what_to_check(code: str) -> None:
    entry = REASONS[code]

    assert 0 < len(entry.short) <= 60 and "\n" not in entry.short
    assert entry.short[0].isupper() and not entry.short.endswith(".")
    sentences = [s for s in re.split(r"(?<=[.])\s+", entry.provider) if s]
    assert 1 <= len(sentences) <= 2 and entry.provider.endswith(".")
    assert JARGON.findall(entry.provider) == [], entry.provider
    assert entry.check or entry.detail  # something to check, fixed or from the claim
    for check in entry.check:
        assert check.text and JARGON.findall(check.text.replace("{line}", "")) == []
        assert check.field is None or not check.text.endswith(".")


def test_the_wording_promises_nothing_and_names_no_process_we_lack() -> None:
    text = " ".join(
        f"{e.short} {e.provider} {' '.join(c.text for c in e.check)}" for e in REASONS.values()
    ).lower()

    for word in ("appeal", "resubmit", "will be paid", "guarantee", "fault", "error by"):
        assert word not in text


def test_every_claim_status_has_exactly_one_label() -> None:
    assert set(STATUS_OUTCOMES) == set(ClaimStatus)
    assert set(STATUS_OUTCOMES.values()) <= set(OUTCOME_LABELS)
    assert list(OUTCOME_LABELS.values()) == [
        "Not processed",
        "In review",
        "Approved",
        "Partly approved",
        "Pended",
        "Denied",
        "Rejected",
    ]
    for status in ClaimStatus:
        assert claim_outcome(status, None) == STATUS_OUTCOMES[status]


def test_mixed_line_outcomes_count_as_partly_approved() -> None:
    paid = model_record(
        ClaimStatus.FINAL_PENDED,
        [final(1, LineDecision.APPROVE), final(2, LineDecision.PEND)],
    )
    on_hold = model_record(ClaimStatus.FINAL_PENDED, [final(1, LineDecision.PEND)])

    assert claim_outcome(ClaimStatus.FINAL_PENDED, paid) == "PARTLY_APPROVED"
    assert claim_outcome(ClaimStatus.FINAL_PENDED, on_hold) == "PENDED"
    assert claim_outcome(ClaimStatus.FINAL_PARTIAL, paid) == "PARTLY_APPROVED"


def test_a_claim_not_processed_is_in_review_to_its_provider() -> None:
    assert provider_outcome("NOT_PROCESSED") == "IN_REVIEW"
    assert provider_outcome("DENIED") == "DENIED"
    rejected = rule_record(ClaimStatus.REJECTED, "R04", "RJ_MEMBER_NOT_FOUND", ["member_id"])
    assert claim_outcome(ClaimStatus.REJECTED, rejected) == "REJECTED"


def test_the_yearly_visit_limit_is_worded_for_providers() -> None:
    """R21 (D-RULE-10): a provider reads plain words for DN_VISIT_LIMIT, never the code."""
    entry = REASONS["DN_VISIT_LIMIT"]
    assert entry.rules == ("R21",)
    assert not JARGON.search(entry.short) and not JARGON.search(entry.provider)
    assert "N640" not in entry.provider and "119" not in entry.provider


@pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present (the X12 lists)")
def test_the_visit_limit_codes_show_their_official_descriptions() -> None:
    """DN_VISIT_LIMIT's CARC 119 and RARC N640 (data/curated/reason_code_map.csv) are shown with the
    official X12 descriptions (app/explain/codes.py), not as bare codes."""
    descriptions = official()
    assert descriptions["CARC"]["119"] and descriptions["RARC"]["N640"]
