"""P2.3b: rules v2 (app/rules/lcd_edits.py) on the edges the golden cases leave out. The golden
rules cases (tests/golden/rules/R14_* to R20_*, checked on sheet G4) cover each rule's main path.
Runs in CI: the code roles and diagnosis sets are curated; the article coverage is synthetic."""

from typing import Any

from app.db.curated import load_curated
from app.db.rules_reference import rule_refs
from app.domain.contracts import IntakeClaim
from app.rules.confidence import apply_h5
from app.rules.line_edits import check_line_edits
from tests.unit.rules_support import PLAN, claim_data, line, reference


def v2_reference(**covered: Any):  # noqa: ANN201
    support, roles, sets = rule_refs(load_curated())
    return reference(
        diagnosis_support=support,
        code_roles=roles,
        diagnosis_sets=sets,
        article_covered=covered or {"A56651": {1: frozenset({"M5412", "M5416"})}},
    )


def claim(diagnoses: list[str], *lines: dict[str, Any]) -> IntakeClaim:
    return IntakeClaim.model_validate(
        claim_data(
            diagnoses=diagnoses,
            service_lines=[line(line_no=n, **x) for n, x in enumerate(lines, start=1)],
        )
    )


def outcomes(claim_: IntakeClaim, ref) -> list[tuple[str, list[str], list[str]]]:  # noqa: ANN001
    _, lines = check_line_edits(claim_, PLAN, ref)
    return [(o.outcome, o.reason_codes, o.flags) for o in lines]


def test_r18_counts_cervical_transforaminal_levels_per_side() -> None:
    """64479 and its add-on 64480: three levels on the right deny the right add-on line."""
    found = claim(
        ["M5412"],
        {"procedure_code": "64479", "modifiers": ["RT"]},
        {"procedure_code": "64480", "modifiers": ["RT"], "units": 2},
        {"procedure_code": "64480", "modifiers": ["LT"]},
    )

    assert outcomes(found, v2_reference()) == [
        ("PASS", [], []),
        ("DENY", ["DN_ESI_LEVELS"], []),
        ("PASS", [], []),  # left: 64479 1 + 64480 1 = 2
    ]


def test_a_third_level_facet_code_is_denied_and_flagged_for_two_regions() -> None:
    found = claim(["M47812"], {"procedure_code": "64492"}, {"procedure_code": "64493"})
    facets = {"A57787": {1: frozenset({"M47812"})}}  # 64492 has no article (not checked)

    assert outcomes(found, v2_reference(**facets)) == [
        ("DENY", ["DN_FACET_LEVELS"], ["FACET_TWO_REGIONS"]),
        ("PASS", [], ["FACET_TWO_REGIONS"]),
    ]


def test_a_low_confidence_cyst_diagnosis_turns_the_r14_denial_into_reject() -> None:
    """R14 reads the facet line's diagnoses (the synovial cyst exception), so H5 applies to them."""
    found = claim(
        ["M5416", "M47816"],
        {"procedure_code": "64483", "diagnosis_pointers": ["A"]},
        {"procedure_code": "64493", "diagnosis_pointers": ["B"]},
    )
    results, _ = check_line_edits(found, PLAN, v2_reference())
    r14 = next(r for r in results if r.rule_id == "R14" and not r.passed)

    converted = apply_h5(r14, {"diagnoses.1": 0.5}, 0.85)

    assert (converted.outcome.value, converted.reason_code) == ("REJECT", "RJ_LOW_CONFIDENCE_FIELD")


def test_a_rule_that_only_flags_passes_and_names_the_flagged_lines() -> None:
    found = claim(["G5601"], {"procedure_code": "95910"})

    results, _ = check_line_edits(found, PLAN, v2_reference())
    r17 = next(r for r in results if r.rule_id == "R17")

    assert r17.passed and r17.detail == "No line is denied; flagged: line 1 NCS_WITHOUT_EMG."
