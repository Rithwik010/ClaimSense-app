"""The member's own pages (D-MEM-1, D-MEM-2, D-MEM-3). A member is a patient: they see the claims
in which they are the patient (claim.member_id is their member ID), each decided claim's
explanation of benefits (the patient EOB of D-EOB-1), their benefits this benefit year and their
profile.

Members only (403 for every other role; the claims, review, plan and metrics endpoints are 403 for
a member). Another member's claim is 404, the same answer as a claim that does not exist. Nothing
here files, processes, corrects or reviews a claim; the one thing a member can ask is an appeal of
a denied claim (D-APL-1), decided by a reviewer other than the one who denied it. A claim shows its
outcome once it is final, and until then only "Your claim is being processed". Built from the
decision record, the stored accumulators and visit usage and the plan (app/explain/member.py);
amounts are the calculator's or stored ones, shown as they are (H1). The plan summary is the
plan's generated summary of benefits and coverage (P3.2).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.claims import claim_eob
from app.api.deps import MemberUser, SettingsDep, get_session, get_today, member_only
from app.auth.users import AuthUser
from app.calculator.engine import Accumulators, NetworkTerms
from app.db import lookups
from app.db.models import Claim, Member, Provider
from app.domain.contracts import ClaimStatus, Network
from app.explain.eob import PatientEob
from app.explain.member import (
    NOT_FINAL,
    MemberAppeal,
    MemberBenefits,
    MemberClaim,
    MemberProfile,
    member_benefits,
    member_claim,
    member_profile,
    service_names,
)
from app.explain.sbc import PlanSummary, parse_sbc
from app.workflow.followup import (
    REASON_MAX,
    FollowUpRefused,
    claim_appeals,
    file_appeal,
    follow_ups,
)
from app.workflow.pipeline import ClaimNotFound, latest_record
from app.workflow.states import InvalidTransition

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


def _appeal(session: Session, row: Claim, user: AuthUser) -> MemberAppeal | None:
    """The claim's latest appeal as its member sees it (never the reason someone else gave, nor
    who decided it)."""
    appeals = claim_appeals(session, row.claim_id, user.username, staff=False)
    if not appeals:
        return None
    latest = appeals[0]
    return MemberAppeal(
        status=latest.status,
        outcome=latest.outcome,
        filed_on=latest.filed_at.date().isoformat(),
        decided_on=latest.decided_at.date().isoformat() if latest.decided_at else None,
        filed_by_you=latest.filed_by == user.username,
    )


def _view(session: Session, row: Claim, user: AuthUser) -> MemberClaim:
    claim_status = ClaimStatus(row.status)
    record = None
    if claim_status not in NOT_FINAL:  # nothing of a recommendation in review is read
        try:
            record = latest_record(session, row.claim_id)
        except ValidationError:  # stored under an older contract: shown by its status only
            record = None
    npi = row.intake.get("billing_npi")
    provider = session.get(Provider, npi) if isinstance(npi, str) else None
    codes = [
        line.get("procedure_code")
        for line in row.intake.get("service_lines") or []
        if isinstance(line, dict) and isinstance(line.get("procedure_code"), str)
    ]
    return member_claim(
        claim_status,
        record,
        row.intake,
        claim_id=row.claim_id,
        received=row.received_date,
        provider_name=provider.name if provider else None,
        services=service_names(row.intake, lookups.procedure_descriptions(session, codes)),
        appeal=_appeal(session, row, user),
        can_appeal=record is not None and follow_ups(session, row, record).appeal,
    )


@router.get("/claims")
def list_claims(session: SessionDep, user: MemberUser) -> list[MemberClaim]:
    """The member's claims, the latest changed first."""
    rows = session.scalars(
        select(Claim)
        .where(Claim.member_id == _member(session, user).member_id)
        .order_by(Claim.updated_at.desc(), Claim.claim_id)
    )
    return [_view(session, row, user) for row in rows]


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str, session: SessionDep, user: MemberUser) -> MemberClaim:
    return _view(session, _own_claim(session, claim_id, user), user)


class AppealRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=REASON_MAX)]


@router.post("/claims/{claim_id}/appeal", status_code=status.HTTP_201_CREATED)
def appeal_claim(
    claim_id: str, body: AppealRequest, session: SessionDep, user: MemberUser
) -> MemberClaim:
    """The member asks for a denied claim to be decided again by another reviewer (D-APL-1), as the
    provider can: 409 when the claim is not denied; 422 when it was appealed already or the reason
    is not 10 to 2000 characters."""
    row = _own_claim(session, claim_id, user)
    try:
        file_appeal(session, row.claim_id, user.username, "member", body.reason)
    except FollowUpRefused as exc:
        session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except (InvalidTransition, ClaimNotFound) as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.refresh(row)
    return _view(session, row, user)


@router.get("/claims/{claim_id}/eob")
def get_eob(claim_id: str, session: SessionDep, user: MemberUser) -> PatientEob:
    """The patient EOB of the member's decided claim (D-EOB-1), the same one the provider and the
    plan's staff see; 409 for a claim the plan has not decided."""
    return claim_eob(session, _own_claim(session, claim_id, user))


@router.get("/benefits")
def get_benefits(
    session: SessionDep, user: MemberUser, today: Annotated[date, Depends(get_today)]
) -> MemberBenefits:
    """The member's current benefit year (1 January to 31 December, D7): for each network the
    plan covers, its deductible and out-of-pocket maximum and what is met of each as stored, and
    the visits used of each visit-limited benefit. Read as the pipeline reads them for the
    calculator (the plan's terms, lookups.get_accumulator, lookups.get_visits_used); nothing is
    added or subtracted (D-MEM-3)."""
    member = _member(session, user)
    plan = lookups.get_plan(session, member.plan_id)
    year_start = lookups.benefit_year_start(today)
    terms = {
        Network.IN_NETWORK.value: NetworkTerms(
            plan.inn_deductible_cents, plan.inn_coinsurance_bps, plan.inn_oop_max_cents
        )
    }
    oon = (plan.oon_deductible_cents, plan.oon_coinsurance_bps, plan.oon_oop_max_cents)
    if plan.oon_covered and oon[0] is not None and oon[1] is not None and oon[2] is not None:
        terms[Network.OUT_OF_NETWORK.value] = NetworkTerms(oon[0], oon[1], oon[2])
    stored = {}
    for network in terms:
        row = lookups.get_accumulator(session, member.member_id, year_start, network)
        if row is not None:
            stored[network] = Accumulators(row.deductible_met_cents, row.oop_met_cents)
    benefits = lookups.get_benefits(session, plan.plan_id)
    return member_benefits(
        member_id=member.member_id,
        plan_id=plan.plan_id,
        plan_name=plan.name,
        plan_type=plan.plan_type,
        year_start=year_start,
        as_of=today,
        terms=terms,
        stored=stored,
        visit_limits={
            category: benefit.visit_limit
            for category, benefit in benefits.items()
            if benefit.covered and benefit.visit_limit is not None
        },
        visits_used=lookups.get_visits_used(session, member.member_id, year_start),
    )


@router.get("/plan-summary")
def get_plan_summary(session: SessionDep, settings: SettingsDep, user: MemberUser) -> PlanSummary:
    """The member's plan's summary of benefits and coverage (P3.2), as generated from the plan's
    terms; 404 when the plan has none."""
    plan_id = _member(session, user).plan_id
    path = settings.sbc_dir / f"{plan_id}.md"
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no summary for plan {plan_id}")
    return parse_sbc(plan_id, path.read_text(encoding="utf-8"))


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
