"""D-UI-6: the provider's explanation and billing (app/explain/provider.py) on hand-built records.
No rule IDs or internal codes; the reasons and what to check in plain words, with the values the
claim carries; billed minus the reductions is the allowed amount and the allowed amount is what the
plan, the patient and another plan pay, to the cent; a sentence for each reduction that happened."""

import json
import re
from dataclasses import asdict

import pytest

from app.domain.contracts import ClaimStatus, CriterionStatus, LineOverride, Network
from app.explain.provider import ProviderExplanation, provider_explanation
from app.explain.reasons import claim_outcome
from tests.unit.ui_records import (
    APPROVE,
    CRITERION_TEXT,
    DENY,
    EXCLUSION_TEXT,
    PEND,
    amounts,
    breakdown,
    claim,
    final,
    model_record,
    review,
    rule_record,
)

HIDDEN = re.compile(
    r"\bR(?:0[1-9]|1[0-9]|20)\b|\bDUP\b|\b(?:RJ|DN|PD|RV)_[A-Z0-9_]+\b"
    r"|\bMODEL_OUTPUT_INVALID\b|\bPOL-[A-Z]+-[0-9]{3}\.c[0-9]+\b"
)
TO_ALLOWED = ("allowed_amount", "out_of_network", "not_paid")
MET, NOT_MET, NOT_DOC = CriterionStatus.MET, CriterionStatus.NOT_MET, CriterionStatus.NOT_DOCUMENTED


def explain(record, claim_=None, confidences=None, rate=2000) -> ProviderExplanation:  # noqa: ANN001
    return provider_explanation(
        claim_outcome(record.status, record),
        record,
        claim_ or claim(),
        confidences or {},
        0.85,
        rate,
    )


def arithmetic(view: ProviderExplanation) -> list[str]:
    assert view.billing is not None
    found = []
    for line in view.billing.lines:
        cut = sum(r.amount_cents or 0 for r in line.reductions if r.kind in TO_ALLOWED)
        if line.billed_cents - cut != line.allowed_cents:
            found.append(f"line {line.line_no}: billed - reductions")
        if line.plan_pays_cents + line.patient_pays_cents + line.other_plan_paid_cents != (
            line.allowed_cents
        ):
            found.append(f"line {line.line_no}: plan + patient + other plan")
        if any(r.amount_cents == 0 for r in line.reductions):
            found.append(f"line {line.line_no}: a zero reduction")
    return found


def texts(view: ProviderExplanation, part: str) -> list[str]:
    return [item.text for item in getattr(view, part)]


def test_an_approved_claim_shows_billing_with_a_sentence_per_reduction() -> None:
    record = model_record(
        ClaimStatus.FINAL_APPROVED,
        [final(1, APPROVE)],
        breakdown(amounts(1, 30000, allowed=24000, deductible=5000, coinsurance=3800)),
        review=review(),
    )

    view = explain(record, claim(1))

    assert (view.outcome, view.heading) == ("APPROVED", "Claim approved")
    assert view.why == view.review == view.codes == []
    assert arithmetic(view) == []
    (line,) = view.billing.lines
    assert [r.text for r in line.reductions] == [
        "Reduced by $60.00 to the plan's allowed amount for this service.",
        "$50.00 applied to the patient's deductible: the amount the patient pays before the "
        "plan starts paying.",
        "Coinsurance: the patient pays 20% of the allowed amount after the deductible ($38.00).",
    ]
    assert (line.plan_pays_cents, line.patient_pays_cents) == (15200, 8800)


def test_coinsurance_limited_by_the_out_of_pocket_maximum_names_no_rate() -> None:
    record = model_record(
        ClaimStatus.FINAL_APPROVED,
        [final(1, APPROVE)],
        breakdown(amounts(1, 30000, allowed=24000, deductible=5000, coinsurance=1000)),
    )

    (line,) = explain(record, claim(1)).billing.lines

    assert line.reductions[-1].text == (
        "Coinsurance: the patient's share of the allowed amount after the deductible ($10.00), "
        "limited by the plan's out-of-pocket maximum."
    )


def test_copay_other_plan_and_out_of_network_amounts_get_their_sentences() -> None:
    copay = model_record(
        ClaimStatus.FINAL_APPROVED,
        [final(1, APPROVE)],
        breakdown(amounts(1, 13100, allowed=7431, copay=2500, primary=4000)),
    )
    out = model_record(
        ClaimStatus.FINAL_APPROVED,
        [final(1, APPROVE)],
        breakdown(
            amounts(
                1,
                30000,
                allowed=18000,
                deductible=0,
                coinsurance=7200,
                network=Network.OUT_OF_NETWORK,
            )
        ),
        network=Network.OUT_OF_NETWORK,
    )

    first = explain(copay, claim(1))
    second = explain(out, claim(1), rate=4000)

    assert arithmetic(first) == [] and arithmetic(second) == []
    assert [r.kind for r in first.billing.lines[0].reductions] == [
        "allowed_amount",
        "copay",
        "other_plan",
        "note",
    ]
    assert first.billing.lines[0].reductions[-1].text == (
        "After the other plan's payment, the patient pays $0.00."
    )
    assert second.billing.lines[0].reductions[0].text == (
        "$120.00 above the plan's allowed amount for an out-of-network provider; the plan does "
        "not pay this part."
    )
    assert "pays 40% of the allowed amount" in second.billing.lines[0].reductions[1].text


def test_a_partly_approved_claim_explains_the_unpaid_line_and_bills_the_paid_one() -> None:
    record = model_record(
        ClaimStatus.FINAL_PARTIAL,
        [final(1, APPROVE), final(2, DENY, "RULE", ["DN_NCCI_BUNDLED"])],
        breakdown(amounts(1, 30000, allowed=24000, copay=5000), amounts(2, 30000)),
        statuses={1: [MET]},
        review=review(),
    )

    view = explain(record)

    assert (view.outcome, view.heading) == ("PARTLY_APPROVED", "Claim partly approved")
    assert [(i.line_no, i.text) for i in view.why] == [
        (
            2,
            "This service is normally part of another service billed on the same date, so it is "
            "not paid separately.",
        )
    ]
    assert "Procedure code on line 2: 99214" in texts(view, "review")
    assert "Modifiers on line 2: none" in texts(view, "review")
    assert [c.code for g in view.codes for c in g.codes] == ["236"]
    assert arithmetic(view) == []
    unpaid = view.billing.lines[1]
    assert not unpaid.paid and unpaid.reductions[0].text == (
        "Not paid: included in another service on the claim."
    )


def test_a_pended_line_lists_the_documentation_it_needs_in_the_criterion_s_words() -> None:
    record = model_record(
        ClaimStatus.FINAL_PENDED, [final(1, PEND)], statuses={1: [NOT_DOC]}, review=review()
    )

    view = explain(record, claim(1))

    assert (view.outcome, view.heading) == ("PENDED", "Claim on hold: more information needed")
    assert texts(view, "review") == [f"Documentation that shows: {CRITERION_TEXT}"]
    assert view.codes == [] and view.billing is None  # pended lines get no codes (D-CARC-2)


def test_a_denied_line_names_the_criterion_or_the_exclusion_not_met() -> None:
    criterion = model_record(
        ClaimStatus.FINAL_DENIED, [final(1, DENY)], statuses={1: [NOT_MET]}, review=review()
    )
    exclusion = model_record(
        ClaimStatus.FINAL_DENIED,
        [final(1, DENY, codes=["DN_CONDITIONAL_EXCLUSION"])],
        statuses={1: [MET, NOT_MET]},
        review=review(),
    )

    assert f"Coverage criterion not met: {CRITERION_TEXT}" in texts(explain(criterion), "review")
    assert f"Exclusion that applies: {EXCLUSION_TEXT}" in texts(explain(exclusion), "review")


def test_a_reviewer_s_denial_has_plain_words_though_it_carries_no_code() -> None:
    record = model_record(
        ClaimStatus.FINAL_DENIED,
        [final(1, DENY, "REVIEWER", [])],
        review=review(LineOverride(line_no=1, decision=DENY, reason="Repeat within 30 days.")),
    )

    view = explain(record, claim(1))

    assert texts(view, "why") == ["A reviewer decided that the plan does not pay for this service."]
    assert "Repeat within 30 days" not in json.dumps(asdict(view))  # the reviewer's own text


def test_a_low_confidence_rejection_lists_what_was_read_and_what_could_not_be() -> None:
    record = rule_record(
        ClaimStatus.REJECTED,
        "R01",
        "RJ_LOW_CONFIDENCE_FIELD",
        ["billing_npi", "service_lines.0.units"],
    )
    filed = claim(1)
    del filed["billing_npi"]
    confidences = {"billing_npi": 0.0, "service_lines.0.units": 0.61, "member_id": 0.5}

    view = explain(record, filed, confidences)

    assert (view.outcome, view.heading) == ("REJECTED", "Claim rejected")
    assert texts(view, "review")[:2] == [
        "Billing provider NPI: could not be read",
        "Units on line 1, read as: 1",
    ]
    assert "Member ID" not in " ".join(texts(view, "review"))  # not a field the rule used


BAD_NPI = "Billing provider NPI on the claim: 1234567890 (not a valid NPI)"
REJECTIONS = [
    (
        "R01",
        "RJ_MISSING_FIELD",
        ["patient.date_of_birth"],
        "Patient date of birth: not on the claim",
    ),
    ("R03", "RJ_INVALID_NPI", ["billing_npi", "referring_npi"], BAD_NPI),
    ("R04", "RJ_MEMBER_NOT_FOUND", ["member_id"], "Member ID on the claim: MBR-000123"),
    ("DUP", "RJ_DUPLICATE", ["member_id"], "Date of service on line 1: 10/05/2026"),
    ("R02", "RJ_INVALID_CODE", [], "Diagnosis codes on the claim: M54.50, M54.16"),
]


@pytest.mark.parametrize(("rule", "code", "fields", "expected"), REJECTIONS)
def test_a_rejection_shows_the_values_the_claim_carries(
    rule: str, code: str, fields: list[str], expected: str
) -> None:
    filed = claim(1)
    filed["billing_npi"] = "1234567890"  # fails the check digit

    view = explain(rule_record(ClaimStatus.REJECTED, rule, code, fields), filed)

    assert expected in texts(view, "review")


def test_no_provider_explanation_holds_a_rule_id_or_an_internal_code() -> None:
    records = [
        model_record(
            ClaimStatus.FINAL_PARTIAL,
            [final(1, APPROVE), final(2, DENY, "RULE", ["DN_MUE_EXCEEDED"])],
            breakdown(amounts(1, 30000, allowed=24000), amounts(2, 30000)),
            rule_results=None,
        ),
        model_record(
            ClaimStatus.FINAL_PENDED, [final(1, PEND, "VALIDATION", ["MODEL_OUTPUT_INVALID"])]
        ),
        rule_record(ClaimStatus.DENIED_BY_RULE, "R15", "DN_DX_NOT_SUPPORTED", [], line_no=1),
        rule_record(ClaimStatus.PENDED_BY_RULE, "R06", "PD_PROVIDER_ENROLLMENT", ["billing_npi"]),
        rule_record(ClaimStatus.REJECTED, "R02", "RJ_LOW_CONFIDENCE_FIELD", ["diagnoses"]),
    ]
    for record in records:
        view = explain(record, claim(), {"diagnoses.0": 0.4})
        assert HIDDEN.findall(json.dumps(asdict(view))) == []
        assert view.why and view.review
