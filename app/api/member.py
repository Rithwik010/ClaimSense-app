"""The member's own pages (D-MEM-1, D-MEM-2, D-MEM-3). A member is a patient: they see the claims
in which they are the patient (claim.member_id is their member ID), each decided claim's
explanation of benefits (the patient EOB of D-EOB-1), their benefits this benefit year and their
profile.

Members only (403 for every other role; the claims, review, plan and metrics endpoints are 403 for
a member). Another member's claim is 404, the same answer as a claim that does not exist. Read
only: nothing here files, processes, corrects or reviews a claim. A claim shows its outcome once it
is final, and until then only "Your claim is being processed". Built from the decision record, the
stored accumulators and visit usage and the plan (app/explain/member.py); amounts are the
calculator's (H1).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.claims import claim_eob
from app.api.deps import MemberUser, get_session, get_today, member_only
from app.auth.users import AuthUser
from app.db import lookups
from app.db.models import Claim, Member, Provider
from app.domain.contracts import ClaimStatus, Network
from app.explain.eob import PatientEob
from app.explain.member import (
    NOT_FINAL,
    MemberBenefits,
    MemberClaim,
    MemberProfile,
    member_benefits,
    member_claim,
    member_profile,
)
from app.workflow.pipeline import latest_record

router = APIRouter(prefix="/v1/member", tags=["member"], dependencies=[Depends(member_only)])
SessionDep = Annotated[Session, Depends(get_session)]


def _member(session: Session, user: AuthUser) -> Member:
    """The member this login is linked to (a member user always has one on file: migration 0011's
    check and foreign key)."""
    member = session.get(Member, user.member_id) if user.member_id else None
    if member is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this login is not linked to a member")
    return member


def _own_claim(session: Session, claim_id: str, user: AuthUser) -> Claim:
    """The claim, if its patient is this member; otherwise 404, as if it did not exist."""
    row = session.get(Claim, claim_id)
    if row is None or user.member_id is None or row.member_id != user.member_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"claim {claim_id} not found")
    return row


def _view(session: Session, row: Claim) -> MemberClaim:
    claim_status = ClaimStatus(row.status)
    record = None
    if claim_status not in NOT_FINAL:  # nothing of a recommendation in review is read
        try:
            record = latest_record(session, row.claim_id)
        except ValidationError:  # stored under an older contract: shown by its status only
            record = None
    npi = row.intake.get("billing_npi")
    provider = session.get(Provider, npi) if isinstance(npi, str) else None
    return member_claim(
        claim_status,
        record,
        row.intake,
        claim_id=row.claim_id,
        received=row.received_date,
        provider_name=provider.name if provider else None,
    )


@router.get("/claims")
def list_claims(session: SessionDep, user: MemberUser) -> list[MemberClaim]:
    """The member's claims, the latest changed first."""
    rows = session.scalars(
        select(Claim)
        .where(Claim.member_id == _member(session, user).member_id)
        .order_by(Claim.updated_at.desc(), Claim.claim_id)
    )
    return [_view(session, row) for row in rows]


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str, session: SessionDep, user: MemberUser) -> MemberClaim:
    return _view(session, _own_claim(session, claim_id, user))


@router.get("/claims/{claim_id}/eob")
def get_eob(claim_id: str, session: SessionDep, user: MemberUser) -> PatientEob:
    """The patient EOB of the member's decided claim (D-EOB-1), the same one the provider and the
    plan's staff see; 409 for a claim the plan has not decided."""
    return claim_eob(session, _own_claim(session, claim_id, user))


@router.get("/benefits")
def get_benefits(
    session: SessionDep, user: MemberUser, today: Annotated[date, Depends(get_today)]
) -> MemberBenefits:
    """The member's deductible and out-of-pocket maximum for each network the plan covers (met
    as stored, the remaining amount from the calculator) and the visits used and left of each
    visit-limited benefit, for the current benefit year (1 January to 31 December, D7)."""
    member = _member(session, user)
    plan = lookups.get_plan(session, member.plan_id)
    year_start = lookups.benefit_year_start(today)
    limits = {Network.IN_NETWORK.value: (plan.inn_deductible_cents, plan.inn_oop_max_cents)}
    oon = (plan.oon_deductible_cents, plan.oon_oop_max_cents)
    if plan.oon_covered and oon[0] is not None and oon[1] is not None:
        limits[Network.OUT_OF_NETWORK.value] = (oon[0], oon[1])
    met = {}
    for network in limits:
        stored = lookups.get_accumulator(session, member.member_id, year_start, network)
        if stored is not None:
            met[network] = (stored.deductible_met_cents, stored.oop_met_cents)
    benefits = lookups.get_benefits(session, plan.plan_id)
    return member_benefits(
        member_id=member.member_id,
        plan_id=plan.plan_id,
        plan_name=plan.name,
        plan_type=plan.plan_type,
        year_start=year_start,
        as_of=today,
        limits=limits,
        met=met,
        visit_limits={
            category: benefit.visit_limit
            for category, benefit in benefits.items()
            if benefit.covered and benefit.visit_limit is not None
        },
        visits_used=lookups.get_visits_used(session, member.member_id, year_start),
    )


@router.get("/profile")
def get_profile(session: SessionDep, user: MemberUser) -> MemberProfile:
    member = _member(session, user)
    plan = lookups.get_plan(session, member.plan_id)
    return member_profile(
        member_id=member.member_id,
        first_name=member.first_name,
        last_name=member.last_name,
        plan_id=plan.plan_id,
        plan_name=plan.name,
        plan_type=plan.plan_type,
        coverage_start=member.coverage_start,
        coverage_end=member.coverage_end,
    )
