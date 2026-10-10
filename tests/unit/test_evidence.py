"""D-EVID-1: the evidence guard (app/ml/evidence.py) and how the explanation reads its entries."""

from app.domain.contracts import CriterionResult, CriterionStatus, SLMLine, SLMOutput
from app.explain.render import guarded
from app.ml.evidence import evidence_guard
from app.ml.validate import ValidationResult

NOTES = "Pain 7/10 after 6 weeks of physical therapy. MRI shows L4-L5 disc herniation."
S = CriterionStatus


def answer(*criteria: tuple[str, S, str]) -> ValidationResult:
    return ValidationResult(
        SLMOutput(
            lines=[
                SLMLine(
                    line_no=1,
                    decision="APPROVE",
                    benefit_category="PAIN_MANAGEMENT",
                    criteria=[
                        CriterionResult(criterion_id=cid, status=status, evidence=evidence)
                        for cid, status, evidence in criteria
                    ],
                    reasons=[],
                    missing_information=[],
                )
            ],
            complexity="LOW",
        ),
        (),
    )


def test_a_met_criterion_whose_quote_is_not_in_the_notes_counts_as_not_documented() -> None:
    result = answer(
        ("POL-PAIN-001.c1", S.MET, "6 weeks of physical therapy"),
        ("POL-PAIN-001.c2", S.MET, "MRI shows a large L5-S1 herniation"),
        ("POL-PAIN-001.c3", S.NOT_MET, "not in the notes either"),
    )

    checked, notes = evidence_guard(result, NOTES)

    assert [c.status for c in checked.output.lines[0].criteria] == [
        S.MET,
        S.NOT_DOCUMENTED,
        S.NOT_MET,  # the guard checks MET quotes only
    ]
    assert notes == ["EVIDENCE_NOT_IN_NOTES: line 1 POL-PAIN-001.c2"]
    assert result.output.lines[0].criteria[1].status is S.MET  # the model's answer is kept
    assert guarded(notes + ["CALCULATION_FAILED: x"]) == {(1, "POL-PAIN-001.c2")}


def test_quoted_answers_and_invalid_answers_pass_unchanged() -> None:
    quoted = answer(("POL-PAIN-001.c1", S.MET, "MRI shows L4-L5 disc herniation"))
    invalid = ValidationResult(None, ("does not parse",))

    assert evidence_guard(quoted, NOTES) == (quoted, [])
    assert evidence_guard(invalid, NOTES) == (invalid, [])
