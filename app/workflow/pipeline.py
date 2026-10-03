"""Claim processing (INSTRUCTIONS.md §5). Synchronous (DECISIONS.md 2026-09-21).

Walking skeleton (P1.5): JSON intake -> rule R05 -> context -> model -> output validation ->
calculator (in-network COPAY lines) -> decision record -> audit events. Rule failures are final
(AUTO_OUTCOME); a rules-passed claim waits for review. Claims the skeleton cannot handle yet raise
`PipelineError` and stay RECEIVED, with nothing written but the intake.
"""

import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CalculationResult,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    UnsupportedCalculation,
    calculate,
)
from app.context.assemble import ContextError, assemble_context
from app.core.logging import get_logger
from app.core.settings import Settings
from app.db import lookups
from app.db.curated import load_curated
from app.db.models import Claim, DecisionRecordRow, Member
from app.domain.contracts import (
    ClaimStatus,
    ContextPackage,
    CostShareRule,
    DecisionRecord,
    FinalLineDecision,
    IntakeClaim,
    IntakeResult,
    LineDecision,
    Network,
    RuleOutcomeValue,
    RulesOutcome,
    SourceFormat,
    Timestamps,
    Versions,
)
from app.ml.client import DecisionModel
from app.ml.prompt import PROMPT_VERSION, PromptLookups, render_user_message, system_prompt
from app.ml.validate import ValidationResult, validate_output
from app.rag.retrieve import Retriever
from app.review.tiers import review_tier
from app.rules import SKELETON_RULES_VERSION
from app.rules.engine import evaluate_eligibility_only
from app.rules.reference import MemberRef
from app.workflow.decisions import derive_claim_decision, final_line_decisions
from app.workflow.states import InvalidTransition, check_transition

log = get_logger(__name__)

RULE_STATUS = {
    RuleOutcomeValue.REJECT: ClaimStatus.REJECTED,
    RuleOutcomeValue.DENY: ClaimStatus.DENIED_BY_RULE,
    RuleOutcomeValue.PEND: ClaimStatus.PENDED_BY_RULE,
}


class PipelineError(ValueError):
    """The walking skeleton cannot process this claim yet; it stays RECEIVED."""


class ClaimNotFound(LookupError):
    pass


class DuplicateClaim(ValueError):
    pass


def low_confidence_fields(intake: IntakeResult, threshold: float) -> list[str]:
    return sorted(path for path, value in intake.field_confidences.items() if value < threshold)


def intake_claim(session: Session, intake: IntakeResult, threshold: float) -> None:
    """Store a received claim (status RECEIVED) and write INTAKE_COMPLETED."""
    claim = intake.claim
    if session.get(Claim, claim.claim_id) is not None:
        raise DuplicateClaim(f"claim {claim.claim_id} already exists")
    session.add(
        Claim(
            claim_id=claim.claim_id,
            member_id=claim.member_id,
            received_date=claim.received_date,
            source_format=intake.source_format.value,
            status=ClaimStatus.RECEIVED.value,
            intake=claim.model_dump(mode="json"),
            field_confidences=dict(intake.field_confidences),
        )
    )
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateClaim(f"claim {claim.claim_id} already exists") from exc
    record_event(
        session,
        claim.claim_id,
        EventType.INTAKE_COMPLETED,
        {
            "source_format": intake.source_format.value,
            "service_lines": len(claim.service_lines),
            "low_confidence_fields": low_confidence_fields(intake, threshold),
        },
    )
    session.commit()


def load_intake(row: Claim) -> IntakeResult:
    return IntakeResult(
        claim=IntakeClaim.model_validate(row.intake),
        field_confidences=row.field_confidences,
        source_format=SourceFormat(row.source_format),
    )


def latest_record(session: Session, claim_id: str) -> DecisionRecord | None:
    row = session.scalars(
        select(DecisionRecordRow)
        .where(DecisionRecordRow.claim_id == claim_id)
        .order_by(DecisionRecordRow.version.desc())
        .limit(1)
    ).first()
    return DecisionRecord.model_validate(row.record) if row else None


def _save(session: Session, row: Claim, record: DecisionRecord) -> None:
    check_transition(ClaimStatus(row.status), record.status)
    row.status = record.status.value
    version = session.scalar(
        select(func.coalesce(func.max(DecisionRecordRow.version), 0)).where(
            DecisionRecordRow.claim_id == row.claim_id
        )
    )
    session.add(
        DecisionRecordRow(
            claim_id=row.claim_id, version=version + 1, record=record.model_dump(mode="json")
        )
    )
    session.commit()


def _rules_payload(rules: RulesOutcome) -> dict:
    return {
        "claim_outcome": rules.claim_outcome.value,
        "failures": [
            {"rule_id": r.rule_id, "outcome": r.outcome.value, "reason_code": r.reason_code}
            for r in rules.rule_results
            if not r.passed
        ],
        "line_outcomes": [o.model_dump(mode="json") for o in rules.line_outcomes],
    }


def _context_payload(context: ContextPackage) -> dict:
    return {
        "plan_id": context.plan_id,
        "network": context.network.value,
        "lines": [
            {
                "line_no": line.line_no,
                "candidate_categories": [f.benefit_category for f in line.candidate_benefits],
                "criterion_ids": [c.criterion_id for c in line.criteria],
            }
            for line in context.lines
        ],
    }


def _model_payload(result: ValidationResult, duration_ms: float) -> dict:
    if not result.valid:
        return {"errors": list(result.errors), "duration_ms": duration_ms}
    assert result.output is not None
    return {
        "complexity": result.output.complexity.value,
        "lines": [
            {
                "line_no": line.line_no,
                "decision": line.decision.value,
                "benefit_category": line.benefit_category,
                "reasons": list(line.reasons),
                "criteria": [
                    {"criterion_id": c.criterion_id, "status": c.status.value}
                    for c in line.criteria
                ],
            }
            for line in result.output.lines
        ],
        "duration_ms": duration_ms,
    }


def _calculate(
    session: Session,
    claim: IntakeClaim,
    member: Member,
    network: Network,
    decisions: list[FinalLineDecision],
) -> CalculationResult:
    plan = lookups.get_plan(session, member.plan_id)
    if network is Network.IN_NETWORK:
        terms = NetworkTerms(
            plan.inn_deductible_cents, plan.inn_coinsurance_bps, plan.inn_oop_max_cents
        )
    elif (
        plan.oon_deductible_cents is None
        or plan.oon_coinsurance_bps is None
        or plan.oon_oop_max_cents is None
    ):
        raise PipelineError("the plan does not cover out-of-network care (rule R08 is in P2.3)")
    else:
        terms = NetworkTerms(
            plan.oon_deductible_cents, plan.oon_coinsurance_bps, plan.oon_oop_max_cents
        )
    by_line = {decision.line_no: decision for decision in decisions}
    lines, fees = [], {}
    for line in claim.service_lines:
        decision = by_line[line.line_no]
        lines.append(
            CalcLine(
                line_no=line.line_no,
                procedure_code=line.procedure_code,
                units=line.units,
                billed_cents=line.charge_cents,
                decision=decision.decision,
                benefit_category=decision.benefit_category,
            )
        )
        if decision.decision is LineDecision.APPROVE and line.procedure_code not in fees:
            fee = lookups.get_fee(session, line.procedure_code, line.date_of_service)
            if fee is None:
                raise PipelineError(f"no fee schedule entry for {line.procedure_code}")
            fees[line.procedure_code] = FeeEntry(fee.inn_allowed_cents, fee.oon_allowed_cents)
    first_day = min(line.date_of_service for line in claim.service_lines)
    stored = lookups.get_accumulator(
        session, member.member_id, lookups.benefit_year_start(first_day), network.value
    )
    accumulators = (
        Accumulators(stored.deductible_met_cents, stored.oop_met_cents)
        if stored
        else Accumulators(0, 0)
    )
    benefits = {
        category: CostShareTerms(CostShareRule(b.cost_share_rule), b.copay_cents)
        for category, b in lookups.get_benefits(session, member.plan_id).items()
    }
    try:
        return calculate(lines, network, terms, benefits, fees, accumulators, claim.other_coverage)
    except UnsupportedCalculation as exc:
        raise PipelineError(str(exc)) from exc


def prompt_lookups(session: Session, claim: IntakeClaim) -> PromptLookups:
    first_day = min(line.date_of_service for line in claim.service_lines)
    codes = sorted({line.procedure_code for line in claim.service_lines})
    return PromptLookups(
        icd10_descriptions=lookups.icd10_descriptions(
            session, list(claim.diagnoses), lookups.icd10_fiscal_year(first_day)
        ),
        procedure_descriptions=lookups.procedure_descriptions(session, codes),
        policy_codes={
            policy_id: list(policy.procedure_codes)
            for policy_id, policy in load_curated().policies.items()
        },
    )


def process_claim(
    session: Session,
    claim_id: str,
    model: DecisionModel,
    settings: Settings,
    retriever: Retriever | None,
) -> DecisionRecord:
    started = time.perf_counter()
    row = session.get(Claim, claim_id, with_for_update=True)
    if row is None:
        raise ClaimNotFound(f"claim {claim_id} not found")
    if row.status != ClaimStatus.RECEIVED.value:
        raise InvalidTransition(f"claim {claim_id} is {row.status}; only RECEIVED claims run")
    intake = load_intake(row)
    claim = intake.claim
    member = lookups.get_member(session, claim.member_id)
    if member is None:
        raise PipelineError(f"member {claim.member_id} not found (rule R04 is in P2.3)")

    rules = evaluate_eligibility_only(
        intake,
        MemberRef(member.member_id, member.plan_id, member.coverage_start, member.coverage_end),
    )
    versions = Versions(rules_version=SKELETON_RULES_VERSION)
    record_event(session, claim_id, EventType.RULES_EVALUATED, _rules_payload(rules), versions)
    timestamps = Timestamps(received=claim.received_date, processed=datetime.now(UTC))

    if rules.claim_outcome is not RuleOutcomeValue.PASS:
        status = RULE_STATUS[rules.claim_outcome]
        record = DecisionRecord(
            claim_id=claim_id,
            status=status,
            rules_outcome=rules,
            versions=versions,
            timestamps=timestamps,
        )
        reasons = [r.reason_code for r in rules.rule_results if not r.passed]
        record_event(
            session,
            claim_id,
            EventType.AUTO_OUTCOME,
            {"status": status.value, "reason_codes": reasons},
            versions,
        )
        _save(session, row, record)
        log.info("claim_processed", claim_id=claim_id, status=status.value)
        return record

    if lookups.get_provider(session, claim.billing_npi) is None:
        raise PipelineError(f"billing provider {claim.billing_npi} not found (rule R06 is in P2.3)")
    network = (
        Network.IN_NETWORK
        if lookups.is_in_network(session, claim.billing_npi, member.plan_id)
        else Network.OUT_OF_NETWORK
    )
    claim_lookups = prompt_lookups(session, claim)
    try:
        context = assemble_context(
            session, claim, rules, member.plan_id, network, claim_lookups, retriever
        )
    except ContextError as exc:
        raise PipelineError(str(exc)) from exc
    record_event(
        session, claim_id, EventType.CONTEXT_ASSEMBLED, _context_payload(context), versions
    )

    user_message = render_user_message(claim, rules, context, claim_lookups)
    model_started = time.perf_counter()
    text = model.complete(system_prompt(), user_message)
    model_ms = round((time.perf_counter() - model_started) * 1000, 1)
    result = validate_output(text, rules, context)
    versions = Versions(
        rules_version=SKELETON_RULES_VERSION,
        model_name=model.name,
        prompt_version=PROMPT_VERSION,
        policy_versions={
            c.policy_id: c.effective_date.isoformat()
            for line in context.lines
            for c in line.criteria
        },
    )
    record_event(
        session,
        claim_id,
        EventType.SLM_RECOMMENDED if result.valid else EventType.OUTPUT_INVALID,
        _model_payload(result, model_ms),
        versions,
    )

    decisions = final_line_decisions(rules, result)
    calculation = _calculate(session, claim, member, network, decisions)
    record_event(
        session,
        claim_id,
        EventType.CALCULATED,
        {"network": network.value, "totals": calculation.amounts.totals.model_dump()},
        versions,
    )
    tier = review_tier(
        result,
        calculation.amounts.totals.allowed_cents,
        low_confidence_fields(intake, settings.extraction_confidence_min),
        settings.review_high_dollar_cents,
    )
    record = DecisionRecord(
        claim_id=claim_id,
        status=ClaimStatus.AWAITING_REVIEW,
        rules_outcome=rules,
        context_refs=context,
        slm_output=result.output,
        output_errors=list(result.errors),
        line_decisions=decisions,
        claim_decision=derive_claim_decision(decisions),
        amounts=calculation.amounts,
        review_tier=tier,
        versions=versions,
        timestamps=timestamps,
    )
    _save(session, row, record)
    log.info(
        "claim_processed",
        claim_id=claim_id,
        status=record.status.value,
        review_tier=tier.value,
        output_valid=result.valid,
        model=model.name,
        model_ms=model_ms,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return record
