"""The coverage policy library (D-POL-9): the policy set the pipeline uses, as providers, reviewers
and admins read it. Each policy's codes with their plain names, and each criterion in its own words
with its type, the codes it applies to, its group and its source. Read only; the criteria are the
curated policies' text, each citing its source in data/raw (CLAUDE.md)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import SessionDep, SettingsDep, WorkUser
from app.db import lookups
from app.db.curated import CoveragePolicy, load_curated

router = APIRouter(prefix="/v1/policies", tags=["policies"])


class PolicyCode(BaseModel):
    code: str
    name: str | None


class PolicySummary(BaseModel):
    policy_id: str
    title: str
    codes: list[PolicyCode]
    criteria: int
    billing_article: str
    effective_date: str


class PolicyCriterion(BaseModel):
    criterion_id: str
    text: str
    criterion_type: str | None
    applies_to: list[str]
    group: str | None
    source: str


class PolicyDetail(PolicySummary):
    sources: list[str]
    items: list[PolicyCriterion]


def _codes(session: SessionDep, policy: CoveragePolicy) -> list[PolicyCode]:
    names = lookups.procedure_descriptions(session, list(policy.procedure_codes))
    return [PolicyCode(code=c, name=names.get(c)) for c in policy.procedure_codes]


def _summary(session: SessionDep, policy: CoveragePolicy) -> PolicySummary:
    return PolicySummary(
        policy_id=policy.policy_id,
        title=policy.title,
        codes=_codes(session, policy),
        criteria=len(policy.criteria),
        billing_article=policy.billing_article,
        effective_date=policy.effective_date.isoformat(),
    )


@router.get("")
def policies(session: SessionDep, settings: SettingsDep, _user: WorkUser) -> list[PolicySummary]:
    data = load_curated(settings.policy_set)
    return [_summary(session, p) for p in sorted(data.policies.values(), key=lambda p: p.title)]


@router.get("/{policy_id}")
def policy(
    policy_id: str, session: SessionDep, settings: SettingsDep, _user: WorkUser
) -> PolicyDetail:
    found = load_curated(settings.policy_set).policies.get(policy_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no policy {policy_id}")
    return PolicyDetail(
        **_summary(session, found).model_dump(),
        sources=list(found.sources),
        items=[
            PolicyCriterion(
                criterion_id=c.criterion_id,
                text=c.text,
                criterion_type=c.criterion_type,
                applies_to=list(c.applies_to),
                group=c.group,
                source=c.source,
            )
            for c in found.criteria
        ],
    )
