"""Plan configuration (INSTRUCTIONS.md §8.10): the plan's terms, its benefits and its excluded
procedure codes, as seeded from data/curated/ (fictional values, DECISIONS.md)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session, require
from app.auth import Role
from app.db.models import Benefit, Plan, PlanExclusion

# Reviewers and admins (D-AUTH-1).
router = APIRouter(
    prefix="/v1/plans",
    tags=["plans"],
    dependencies=[Depends(require(Role.REVIEWER, Role.ADMIN))],
)
SessionDep = Annotated[Session, Depends(get_session)]


class BenefitView(BaseModel):
    benefit_category: str
    covered: bool
    auth_required: bool
    visit_limit: int | None
    cost_share_rule: str
    copay_cents: int | None


class PlanView(BaseModel):
    plan_id: str
    name: str
    plan_type: str
    effective_date: date
    filing_window_inn_days: int
    filing_window_oon_days: int
    oon_covered: bool
    inn_deductible_cents: int
    inn_coinsurance_bps: int
    inn_oop_max_cents: int
    oon_deductible_cents: int | None
    oon_coinsurance_bps: int | None
    oon_oop_max_cents: int | None
    benefits: list[BenefitView]
    excluded_codes: list[str]


@router.get("/{plan_id}")
def get_plan(plan_id: str, session: SessionDep) -> PlanView:
    plan = session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"plan {plan_id} not found")
    benefits = session.scalars(
        select(Benefit).where(Benefit.plan_id == plan_id).order_by(Benefit.benefit_category)
    )
    excluded = session.scalars(
        select(PlanExclusion.procedure_code)
        .where(PlanExclusion.plan_id == plan_id)
        .order_by(PlanExclusion.procedure_code)
    )
    fields = {name: getattr(plan, name) for name in PlanView.model_fields if hasattr(plan, name)}
    return PlanView(
        **fields,
        benefits=[BenefitView.model_validate(b, from_attributes=True) for b in benefits],
        excluded_codes=list(excluded),
    )
