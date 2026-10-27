"""The largest prompt a claim can get (D-DOC-3), counted when it is filed or corrected: a claim
whose prompt could not fit the model's context with its answer (`PROMPT_BUDGET`) is refused then,
as a form of too many pages is, and never reaches the model to be cut.

The prompt is rendered by the pipeline's own code (`system_prompt`, `render_user_message`) for the
claim as filed, so its notes, diagnoses and service lines are counted exactly, with the tokenizer
the model reads them with (`app/ml/tokens.py`). Everything decided after intake takes its worst
case, and the largest count over every plan and both networks is the claim's:

- the rules: the claim passes with the out-of-network flag, every line passes (a denied line
  shows less) with every flag the rules can give a line;
- each line's benefits: a fact for every candidate category of its code, from the plan's benefits,
  a visit limit shown with 999 visits used;
- each line's criteria: every criterion of every policy shown on its code and in effect on its
  date of service, for any plan, in policy-file order (the v2 exact lookup returns those of the
  claim's plan; v1's top k are among them).

decision_v3 shows consecutive lines with the same criteria once. Here they are the same only when
the line's code and its policies in effect are the same, and then the retrieved criteria are the
same too, so the count is never below the prompt's.
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

from app.db.curated import CuratedData
from app.domain.contracts import (
    BenefitFact,
    ContextPackage,
    CostShareRule,
    IntakeClaim,
    LineContext,
    LineRuleOutcome,
    Network,
    RetrievedCriterion,
    RuleOutcomeValue,
    RulesOutcome,
)
from app.ml.prompt import PromptLookups, render_user_message, system_prompt
from app.ml.tokens import prompt_tokens
from app.rules.lcd_edits import EXTENDED_TESTING, FACET_TWO_REGIONS, NCS_WITHOUT_EMG
from app.rules.line_edits import BYPASS_FLAG
from app.rules.requirements import OON_FLAG

LINE_FLAGS = [BYPASS_FLAG, NCS_WITHOUT_EMG, FACET_TWO_REGIONS, EXTENDED_TESTING]
VISITS_USED = 999  # shown with a visit limit: more digits than any year's visits


def worst_rules(claim: IntakeClaim) -> RulesOutcome:
    return RulesOutcome(
        claim_outcome=RuleOutcomeValue.PASS,
        rule_results=[],
        line_outcomes=[
            LineRuleOutcome(line_no=line.line_no, outcome="PASS", flags=list(LINE_FLAGS))
            for line in claim.service_lines
        ],
        flags=[OON_FLAG],
    )


def criteria_shown(curated: CuratedData, code: str, day: date) -> list[RetrievedCriterion]:
    """Every criterion of every policy shown on `code` and in effect on `day`, for any plan."""
    v2 = curated.policy_set == "v2"
    return [
        RetrievedCriterion(
            criterion_id=criterion.criterion_id,
            policy_id=policy.policy_id,
            policy_title=policy.title,
            text=criterion.text,
            source=criterion.source,
            effective_date=policy.effective_date,
            criterion_type=criterion.criterion_type if v2 else None,
            group=criterion.group if v2 else None,
        )
        for policy in curated.policies.values()
        if policy.effective_date <= day
        for criterion in policy.criteria
        if code in (policy.criterion_codes(criterion) if v2 else policy.procedure_codes)
    ]


def worst_contexts(claim: IntakeClaim, curated: CuratedData) -> Iterator[ContextPackage]:
    """The worst-case context of the claim for each plan and network."""
    for plan in curated.plans.values():
        lines = []
        for line in claim.service_lines:
            scope = curated.scope.get(line.procedure_code)
            facts = []
            for category in scope.candidate_categories if scope else ():
                benefit = curated.benefits.get((plan.plan_id, category))
                if benefit is None:
                    continue
                facts.append(
                    BenefitFact(
                        benefit_category=category,
                        covered=benefit.covered,
                        auth_required=benefit.auth_required,
                        visit_limit=benefit.visit_limit,
                        visits_used=VISITS_USED if benefit.visit_limit else 0,
                        cost_share_rule=CostShareRule(benefit.cost_share_rule),
                    )
                )
            lines.append(
                LineContext(
                    line_no=line.line_no,
                    procedure_code=line.procedure_code,
                    candidate_benefits=facts,
                    criteria=criteria_shown(curated, line.procedure_code, line.date_of_service),
                    rule_flags=list(LINE_FLAGS),
                )
            )
        for network in Network:
            yield ContextPackage(
                claim_id=claim.claim_id,
                plan_id=plan.plan_id,
                plan_type=plan.plan_type,
                network=network,
                excluded_codes=sorted(curated.excluded_codes(plan.plan_id)),
                lines=lines,
            )


def largest_prompt_tokens(
    claim: IntakeClaim,
    lookups: PromptLookups,
    curated: CuratedData,
    version: str,
    tokenizer: Path,
) -> int:
    """The most tokens the claim's whole prompt can have (system and user message, chat format)."""
    system = system_prompt(version)
    rules = worst_rules(claim)
    return max(
        prompt_tokens(
            system, render_user_message(claim, rules, context, lookups, version), tokenizer
        )
        for context in worst_contexts(claim, curated)
    )
