"""D-EOB-1: the patient's explanation of benefits, built from hand-built records: the calculator's
amounts and the billing sentences per line, the plain reason and standard codes of a line not
paid, a pending line's note, and a claim the rules denied (its charges only, no other amount)."""

from app.domain.contracts import ClaimStatus
from app.explain.eob import NO_CALCULATION, NOT_A_BILL, PENDING_NOTE, YearToDate, patient_eob
from tests.unit.ui_records import (
    APPROVE,
    DENY,
    PEND,
    amounts,
    breakdown,
    claim,
    final,
    model_record,
    rule_record,
)

DESCRIPTIONS = {"64483": "Spine injection, one level", "99214": "Office visit, established"}
YTD = YearToDate("IN_NETWORK", "2026-01-01", 50000, 150000, 72000, 600000)


def eob(record, status: ClaimStatus, outcome: str, ytd: YearToDate | None = YTD):  # noqa: ANN001, ANN201
    return patient_eob(
        status,
        outcome,
        record,
        claim(),
        plan_name="PPO Gold",
        provider_name="Valley Clinic",
        descriptions=DESCRIPTIONS,
        year_to_date=ytd,
        coinsurance_bps=2000,
    )


def test_a_partly_approved_claim_line_by_line() -> None:
    record = model_record(
        ClaimStatus.FINAL_PARTIAL,
        [final(1, APPROVE), final(2, DENY)],
        breakdown(amounts(1, 30000, 20000, deductible=5000, coinsurance=3000), amounts(2, 30000)),
    )

    found = eob(record, ClaimStatus.FINAL_PARTIAL, "PARTLY_APPROVED")

    assert (found.patient_name, found.member_id, found.plan_name) == (
        "Ana Lopez",
        "MBR-000123",
        "PPO Gold",
    )
    assert found.network == "IN_NETWORK" and found.received == "2026-10-09"
    paid, denied = found.lines
    assert (paid.status, paid.service, paid.date_of_service) == (
        "PAID",
        "Spine injection, one level",
        "2026-10-05",
    )
    assert (paid.billed_cents, paid.allowed_cents, paid.plan_pays_cents) == (30000, 20000, 12000)
    assert paid.patient_pays_cents == 8000
    assert paid.notes == [
        "Reduced by $100.00 to the plan's allowed amount for this service.",
        "$50.00 applied to the patient's deductible: the amount the patient pays before the plan "
        "starts paying.",
        "Coinsurance: the patient pays 20% of the allowed amount after the deductible ($30.00).",
    ]
    assert denied.status == "NOT_PAID" and denied.notes[0].startswith("Not paid: ")
    assert denied.codes and denied.codes[0].startswith("CO-")
    assert found.totals is not None and found.totals.patient_pays_cents == 8000
    assert found.notes == [NOT_A_BILL] and found.year_to_date == YTD


def test_a_pending_line_says_it_waits_for_information() -> None:
    record = model_record(
        ClaimStatus.FINAL_PENDED,
        [final(1, APPROVE), final(2, PEND)],
        breakdown(amounts(1, 30000, 20000), amounts(2, 30000)),
    )

    found = eob(record, ClaimStatus.FINAL_PENDED, "PARTLY_APPROVED")

    assert [line.status for line in found.lines] == ["PAID", "PENDING"]
    assert found.lines[1].notes[0].startswith("Not paid yet: ")
    assert found.lines[1].codes == []  # a pended line gets no codes
    assert found.notes == [NOT_A_BILL, PENDING_NOTE]


def test_a_claim_the_rules_denied_shows_its_charges_and_why() -> None:
    record = rule_record(ClaimStatus.DENIED_BY_RULE, "R05", "DN_NOT_ELIGIBLE", ["member_id"])

    found = eob(record, ClaimStatus.DENIED_BY_RULE, "DENIED", ytd=None)

    assert found.totals is None and found.year_to_date is None and found.network is None
    assert [(line.billed_cents, line.allowed_cents) for line in found.lines] == [
        (30000, None),
        (30000, None),
    ]
    assert all(line.status == "NOT_PAID" for line in found.lines)
    assert found.notes[0] == NOT_A_BILL and found.notes[-1] == NO_CALCULATION
    assert len(found.notes) == 3  # the claim's plain reason between them
    assert found.codes and found.codes[0].startswith("CO-")
