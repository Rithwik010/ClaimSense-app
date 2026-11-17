"""D-MEM-2, D-MEM-3: the member's views, built from hand-built records and serialized as the API
serializes them (pydantic, as FastAPI does). Each view has exactly its listed fields, and its JSON
holds no clinical note, model output, criterion, rule ID, internal reason code, reviewer ID or
reason, or field confidence; a claim not final shows "being processed" and nothing of its
recommendation; the benefits are the plan's terms and the stored amounts as they are."""

import json
import re
from datetime import date
from typing import Any

import pytest
from pydantic import TypeAdapter

from app.calculator.engine import Accumulators, NetworkTerms
from app.domain.contracts import ClaimStatus, LineOverride
from app.explain.member import (
    HEADINGS,
    MESSAGES,
    ON_HOLD_BY_RULES,
    PROCESSING,
    MemberBenefits,
    MemberClaim,
    MemberProfile,
    member_benefits,
    member_claim,
    member_profile,
)
from tests.unit.ui_records import (
    APPROVE,
    CRITERION_TEXT,
    DENY,
    EXCLUSION_TEXT,
    NOTE,
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
CLAIM_FIELDS = {
    "claim_id",
    "received",
    "service_date",
    "provider_name",
    "final",
    "outcome",
    "heading",
    "message",
    "eob",
    "billed_cents",
    "plan_pays_cents",
    "patient_pays_cents",
    "services",  # plain procedure names (D-MEM-2)
    "appeal",  # the member's view of an appeal (D-APL-1)
    "can_appeal",
}
SECRETS = (NOTE, NOTE[:30], CRITERION_TEXT, EXCLUSION_TEXT, "reviewer-7", "1970-03-04", "Main St")
REASON = "The note shows the criterion; overridden on review."


def as_json(view: Any, kind: type) -> dict[str, Any]:  # noqa: ANN401
    return json.loads(TypeAdapter(kind).dump_json(view))


def problems(data: dict[str, Any]) -> list[str]:
    text = json.dumps(data)
    found = HIDDEN.findall(text)
    found += [secret for secret in (*SECRETS, REASON) if secret in text]
    found += [key for key in ("confidence", "evidence", "criteria") if key in text]
    return found


def view(status: ClaimStatus, record) -> dict[str, Any]:  # noqa: ANN001
    built = member_claim(
        status,
        record,
        claim(),
        claim_id="CLM-UI-0001",
        received=date(2026, 10, 9),
        provider_name="Valley Clinic",
    )
    return as_json(built, MemberClaim)


PAID = breakdown(
    amounts(1, 30000, 20000, deductible=5000, coinsurance=3000),
    amounts(2, 30000, 15000, copay=2500),
)
PARTLY = breakdown(amounts(1, 30000, 20000, deductible=5000, coinsurance=3000), amounts(2, 30000))
OVERRIDE = LineOverride(line_no=2, decision=DENY, reason=REASON)


@pytest.mark.parametrize(
    ("status", "record", "outcome", "eob", "totals"),
    [
        (
            ClaimStatus.FINAL_APPROVED,
            model_record(ClaimStatus.FINAL_APPROVED, [final(1, APPROVE), final(2, APPROVE)], PAID),
            "APPROVED",
            True,
            PAID.totals,
        ),
        (
            ClaimStatus.FINAL_PARTIAL,
            model_record(
                ClaimStatus.FINAL_PARTIAL,
                [final(1, APPROVE), final(2, DENY, "REVIEWER")],
                PARTLY,
                review=review(OVERRIDE),
            ),
            "PARTLY_APPROVED",
            True,
            PARTLY.totals,
        ),
        (
            ClaimStatus.FINAL_PENDED,  # an approved (paid) line: partly approved (D-REV-7)
            model_record(ClaimStatus.FINAL_PENDED, [final(1, APPROVE), final(2, PEND)], PARTLY),
            "PARTLY_APPROVED",
            True,
            PARTLY.totals,
        ),
        (
            ClaimStatus.FINAL_DENIED,
            model_record(
                ClaimStatus.FINAL_DENIED,
                [final(1, DENY), final(2, DENY)],
                breakdown(amounts(1, 30000), amounts(2, 30000)),
            ),
            "DENIED",
            True,
            breakdown(amounts(1, 30000), amounts(2, 30000)).totals,
        ),
        (
            ClaimStatus.DENIED_BY_RULE,
            rule_record(ClaimStatus.DENIED_BY_RULE, "R05", "DN_NOT_ELIGIBLE", ["member_id"]),
            "DENIED",
            True,
            None,  # no calculation
        ),
        (
            ClaimStatus.REJECTED,
            rule_record(ClaimStatus.REJECTED, "R03", "RJ_INVALID_NPI", ["billing_npi"]),
            "REJECTED",
            False,
            None,
        ),
        (
            ClaimStatus.PENDED_BY_RULE,
            rule_record(
                ClaimStatus.PENDED_BY_RULE, "R06", "PD_PROVIDER_ENROLLMENT", ["billing_npi"]
            ),
            "PENDED",
            False,
            None,
        ),
    ],
    ids=lambda v: v.value if isinstance(v, ClaimStatus) else None,
)
def test_a_final_claim_shows_its_outcome_and_the_records_totals(
    status: ClaimStatus, record, outcome: str, eob: bool, totals
) -> None:  # noqa: ANN001
    shown = view(status, record)

    assert set(shown) == CLAIM_FIELDS
    assert problems(shown) == []
    assert (shown["final"], shown["outcome"], shown["eob"]) == (True, outcome, eob)
    assert shown["heading"] == HEADINGS[outcome]
    assert shown["message"] == (
        MESSAGES[outcome] if eob or outcome != "PENDED" else ON_HOLD_BY_RULES
    )
    assert (shown["billed_cents"], shown["plan_pays_cents"], shown["patient_pays_cents"]) == (
        (totals.billed_cents, totals.plan_pays_cents, totals.member_pays_cents)
        if totals
        else (None, None, None)
    )
    assert (shown["received"], shown["service_date"], shown["provider_name"]) == (
        "2026-10-09",
        "2026-10-05",
        "Valley Clinic",
    )


@pytest.mark.parametrize("status", [ClaimStatus.RECEIVED, ClaimStatus.AWAITING_REVIEW])
def test_until_final_a_claim_is_being_processed_and_nothing_else(status: ClaimStatus) -> None:
    """Even with a recommendation and amounts in the record, nothing of them is shown."""
    record = model_record(status, [final(1, APPROVE), final(2, DENY)], PARTLY)

    for shown in (view(status, record), view(status, None)):
        assert set(shown) == CLAIM_FIELDS and problems(shown) == []
        assert shown["heading"] == "Your claim is being processed" == HEADINGS[PROCESSING]
        assert (shown["final"], shown["outcome"], shown["eob"]) == (False, PROCESSING, False)
        assert [shown[k] for k in ("billed_cents", "plan_pays_cents", "patient_pays_cents")] == [
            None,
            None,
            None,
        ]


def test_the_benefits_are_the_plans_terms_and_the_stored_amounts_as_they_are() -> None:
    benefits = member_benefits(
        member_id="MBR-000123",
        plan_id="PLN-PPO-GOLD",
        plan_name="ClaimSense PPO Gold",
        plan_type="PPO",
        year_start=date(2026, 1, 1),
        as_of=date(2026, 10, 20),
        terms={
            "OUT_OF_NETWORK": NetworkTerms(100000, 4000, 600000),
            "IN_NETWORK": NetworkTerms(50000, 2000, 300000),
        },
        stored={"IN_NETWORK": Accumulators(46500, 47700)},  # nothing stored out of network
        visit_limits={"REHAB_THERAPY": 30},
        visits_used={"REHAB_THERAPY": 7, "OTHER": 2},
    )

    shown = as_json(benefits, MemberBenefits)

    assert problems(shown) == []
    # What is left and the share used are the calculator's (D-MEM-5), worked by hand:
    # in network 500.00 - 465.00 = 35.00 left, 465/500 = 93.00% (9300); 3000.00 - 477.00 =
    # 2523.00 left, 477/3000 = 15.90% (1590). Out of network nothing met: all left, 0. Visits:
    # 30 - 7 = 23 left, 7/30 = 23.33% rounded down (2333).
    assert shown == {
        "member_id": "MBR-000123",
        "plan_id": "PLN-PPO-GOLD",
        "plan_name": "ClaimSense PPO Gold",
        "plan_type": "PPO",
        "benefit_year_start": "2026-01-01",
        "benefit_year_end": "2026-12-31",
        "as_of": "2026-10-20",
        "networks": [
            {
                "network": "IN_NETWORK",
                "period_start": "2026-01-01",
                "deductible_met_cents": 46500,
                "deductible_cents": 50000,
                "oop_met_cents": 47700,
                "oop_max_cents": 300000,
                "deductible_left_cents": 3500,
                "deductible_met_bps": 9300,
                "oop_left_cents": 252300,
                "oop_met_bps": 1590,
            },
            {
                "network": "OUT_OF_NETWORK",
                "period_start": "2026-01-01",
                "deductible_met_cents": 0,
                "deductible_cents": 100000,
                "oop_met_cents": 0,
                "oop_max_cents": 600000,
                "deductible_left_cents": 100000,
                "deductible_met_bps": 0,
                "oop_left_cents": 600000,
                "oop_met_bps": 0,
            },
        ],
        "visits": [
            {
                "benefit_category": "REHAB_THERAPY",
                "visit_limit": 30,
                "visits_used": 7,
                "visits_left": 23,
                "used_bps": 2333,
            }
        ],
    }


def test_a_stored_amount_above_its_limit_is_shown_as_stored() -> None:
    benefits = member_benefits(
        member_id="MBR-000152",
        plan_id="PLN-HMO",
        plan_name="ClaimSense HMO Select",
        plan_type="HMO",
        year_start=date(2026, 1, 1),
        as_of=date(2026, 10, 20),
        terms={"IN_NETWORK": NetworkTerms(25000, 2000, 400000)},
        stored={"IN_NETWORK": Accumulators(25000, 400000)},
        visit_limits={"REHAB_THERAPY": 20},
        visits_used={"REHAB_THERAPY": 23},
    )

    assert [n.network for n in benefits.networks] == ["IN_NETWORK"]
    assert (benefits.networks[0].deductible_met_cents, benefits.networks[0].oop_met_cents) == (
        25000,
        400000,
    )
    assert benefits.visits[0].visits_used == 23 and benefits.visits[0].visit_limit == 20


def test_the_profile_is_name_member_id_plan_and_coverage_dates_only() -> None:
    profile = member_profile(
        member_id="MBR-000123",
        first_name="Ana",
        last_name="Lopez",
        plan_id="PLN-PPO-GOLD",
        plan_name="ClaimSense PPO Gold",
        plan_type="PPO",
        coverage_start=date(2025, 1, 1),
        coverage_end=None,
    )

    shown = as_json(profile, MemberProfile)

    assert shown == {
        "member_id": "MBR-000123",
        "name": "Ana Lopez",
        "plan_id": "PLN-PPO-GOLD",
        "plan_name": "ClaimSense PPO Gold",
        "plan_type": "PPO",
        "coverage_start": "2025-01-01",
        "coverage_end": None,
    }
    assert problems(shown) == []
