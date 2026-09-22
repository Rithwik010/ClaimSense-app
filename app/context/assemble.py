"""Context assembly (INSTRUCTIONS.md §8.4): what the model sees besides the claim.

Plan facts come from the database. Candidate benefit categories per procedure code come from
`data/curated/procedure_scope.csv`; office visits are narrowed to one category by the rendering
provider's primary-care flag (DECISIONS.md, data-generation choice 2), as in the training data.

Walking skeleton (P1.5): no coverage criteria yet. Retrieval arrives in P3.3 and is wired in here in
P5.2; until then every line has an empty criteria list and the prompt says "No criteria retrieved."
"""

from sqlalchemy.orm import Session

from app.db.curated import load_curated
from app.db.lookups import (
    benefit_year_start,
    get_benefits,
    get_excluded_codes,
    get_plan,
    get_provider,
    get_visits_used,
)
from app.domain.contracts import (
    BenefitFact,
    ContextPackage,
    CostShareRule,
    IntakeClaim,
    LineContext,
    Network,
    RulesOutcome,
)

OFFICE_VISIT_PCP = "OFFICE_VISIT_PCP"
OFFICE_VISIT_SPECIALIST = "OFFICE_VISIT_SPECIALIST"


class ContextError(ValueError):
    """The context for a claim cannot be assembled (a code outside the scope, missing data)."""


def assemble_context(
    session: Session, claim: IntakeClaim, rules: RulesOutcome, plan_id: str, network: Network
) -> ContextPackage:
    curated = load_curated()
    plan = get_plan(session, plan_id)
    benefits = get_benefits(session, plan_id)
    first_day = min(line.date_of_service for line in claim.service_lines)
    visits = get_visits_used(session, claim.member_id, benefit_year_start(first_day))
    service_lines = {line.line_no: line for line in claim.service_lines}
    lines = []
    for outcome in rules.line_outcomes:
        if outcome.outcome != "PASS":
            continue
        line = service_lines[outcome.line_no]
        scope = curated.scope.get(line.procedure_code)
        if scope is None:
            raise ContextError(f"procedure code {line.procedure_code} is outside the scope")
        categories = list(scope.candidate_categories)
        if set(categories) == {OFFICE_VISIT_PCP, OFFICE_VISIT_SPECIALIST}:
            provider = get_provider(session, line.rendering_npi)
            if provider is None:
                raise ContextError(f"rendering provider {line.rendering_npi} is not loaded")
            primary_care = curated.provider_types.get(provider.provider_type, False)
            categories = [OFFICE_VISIT_PCP if primary_care else OFFICE_VISIT_SPECIALIST]
        facts = []
        for category in categories:
            benefit = benefits[category]
            facts.append(
                BenefitFact(
                    benefit_category=category,
                    covered=benefit.covered,
                    auth_required=benefit.auth_required,
                    visit_limit=benefit.visit_limit,
                    visits_used=visits.get(category, 0) if benefit.visit_limit else 0,
                    cost_share_rule=CostShareRule(benefit.cost_share_rule),
                )
            )
        lines.append(
            LineContext(
                line_no=line.line_no,
                procedure_code=line.procedure_code,
                candidate_benefits=facts,
                criteria=[],
                rule_flags=list(outcome.flags),
            )
        )
    return ContextPackage(
        claim_id=claim.claim_id,
        plan_id=plan_id,
        plan_type=plan.plan_type,
        network=network,
        excluded_codes=get_excluded_codes(session, plan_id),
        lines=lines,
    )
