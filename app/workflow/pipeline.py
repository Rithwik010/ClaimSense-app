"""Claim processing (INSTRUCTIONS.md §5). Synchronous (DECISIONS.md 2026-09-21).

Intake -> the v1 rules engine (R01-R13, duplicates, H5; RULES_VERSION, P2.5) on the database
reference -> context -> model -> output validation -> calculator (§8.6, P2.4) -> decision record
-> audit events.

- Intake stores a claim that fails the contract when every error is one R01, R02 or R03 reports
  (A-R8), with the errors in INTAKE_COMPLETED; the rules then reject it. A claim without a claim
  ID, member ID or received date, or with another validation error, is refused (`IntakeRefused`).
- A rule failure is final: REJECTED, DENIED_BY_RULE or PENDED_BY_RULE with its reason codes, an
  AUTO_OUTCOME event and every rule result (with its fields_used) in the decision record. Only a
  passing claim reaches context and the model; Group C line denials and flags pass through.
- Reference data the rules need but the database lacks (an ICD-10-CM fiscal year not loaded)
  leaves the claim RECEIVED with nothing written (`ReferenceDataUnavailable`, retry once loaded).
- A calculation that fails (CalculationError: an approved line whose code has no fee, or
  out-of-network care on a plan with no out-of-network terms) is audited as CALCULATION_FAILED and
  the claim waits for FULL review without amounts.
- Anything else the pipeline cannot do raises `PipelineError`; the claim stays RECEIVED.
"""

import time
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.calculator import CALCULATOR_VERSION
from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CalculationError,
    CalculationResult,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    calculate,
)
from app.context.assemble import ContextError, assemble_context
from app.core.logging import get_logger
from app.core.settings import Settings
from app.db import lookups
from app.db.curated import load_curated
from app.db.models import Claim, DecisionRecordRow, Member
from app.db.rules_reference import reference_for_claim
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
    ReviewTier,
    RuleOutcomeValue,
    RulesOutcome,
    SourceFormat,
    Timestamps,
    Versions,
)
from app.ml.client import DecisionModel
from app.ml.prompt import PROMPT_VERSION, PromptLookups, render_user_message, system_prompt
from app.ml.validate import ValidationResult, validate_output
from app.rag.knowledge import curated_knowledge_version
from app.rag.retrieve import Retriever
from app.review.tiers import review_tier
from app.rules import RULES_VERSION
from app.rules.engine import evaluate
from app.rules.integrity import InvalidClaimData, contract_failures
from app.rules.reference import MissingReference
from app.workflow.decisions import derive_claim_decision, final_line_decisions
from app.workflow.states import InvalidTransition, check_transition

log = get_logger(__name__)

RULE_STATUS = {
    RuleOutcomeValue.REJECT: ClaimStatus.REJECTED,
    RuleOutcomeValue.DENY: ClaimStatus.DENIED_BY_RULE,
    RuleOutcomeValue.PEND: ClaimStatus.PENDED_BY_RULE,
}


class PipelineError(ValueError):
    """The pipeline cannot process this claim; it stays RECEIVED."""


class IntakeRefused(ValueError):
    """The claim cannot be filed: no claim ID, member ID or received date, or a validation error
    that rules R01 to R03 do not report (A-R8)."""


class ReferenceDataUnavailable(RuntimeError):
    """The rules need reference data the database does not hold yet; the claim stays RECEIVED
    and can run once it is loaded."""


class ClaimNotFound(LookupError):
    pass


class DuplicateClaim(ValueError):
    pass


def low_confidence_fields(intake: IntakeResult, threshold: float) -> list[str]:
    return sorted(path for path, value in intake.field_confidences.items() if value < threshold)


def _filing_fields(data: Mapping[str, Any]) -> tuple[str, str, date]:
    """Claim ID, member ID and received date: what filing a claim needs (P2.5 decision 3)."""
    claim_id, member_id, received = (
        data.get("claim_id"),
        data.get("member_id"),
        data.get("received_date"),
    )
    if not isinstance(claim_id, str) or not claim_id.strip() or len(claim_id) > 48:
        raise IntakeRefused("a claim needs a claim_id (1 to 48 characters)")
    if not isinstance(member_id, str) or not member_id.strip() or len(member_id) > 32:
        raise IntakeRefused("a claim needs a member_id (1 to 32 characters)")
    try:
        received_date = date.fromisoformat(received)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise IntakeRefused("a claim needs a received_date (YYYY-MM-DD)") from None
    return claim_id, member_id, received_date


def intake_claim_data(
    session: Session,
    data: Mapping[str, Any],
    field_confidences: Mapping[str, float],
    source_format: SourceFormat,
    threshold: float,
) -> tuple[IntakeResult | None, list[str]]:
    """Store a received claim (status RECEIVED) and write INTAKE_COMPLETED. Returns the validated
    claim, or None for a claim that fails the contract, and its contract errors. Such a claim is
    stored as received when every error is one R01, R02 or R03 reports (A-R8), so the rules
    reject it; otherwise it is refused."""
    claim_id, member_id, received_date = _filing_fields(data)
    if any(not 0.0 <= value <= 1.0 for value in field_confidences.values()):
        raise IntakeRefused("field confidences must be between 0 and 1")
    try:
        claim, failures = contract_failures(data)
    except InvalidClaimData as exc:
        raise IntakeRefused(str(exc)) from exc
    errors = [f"{failure.rule_id}: {failure.detail}" for failure in failures]
    if session.get(Claim, claim_id) is not None:
        raise DuplicateClaim(f"claim {claim_id} already exists")
    session.add(
        Claim(
            claim_id=claim_id,
            member_id=member_id,
            received_date=received_date,
            source_format=source_format.value,
            status=ClaimStatus.RECEIVED.value,
            intake=claim.model_dump(mode="json") if claim else dict(data),
            field_confidences=dict(field_confidences),
        )
    )
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateClaim(f"claim {claim_id} already exists") from exc
    lines = data.get("service_lines")
    record_event(
        session,
        claim_id,
        EventType.INTAKE_COMPLETED,
        {
            "source_format": source_format.value,
            "service_lines": len(lines) if isinstance(lines, list) else 0,
            "low_confidence_fields": sorted(
                path for path, value in field_confidences.items() if value < threshold
            ),
            "contract_errors": errors,
        },
    )
    session.commit()
    result = (
        IntakeResult(
            claim=claim, field_confidences=dict(field_confidences), source_format=source_format
        )
        if claim
        else None
    )
    return result, errors


def intake_claim(session: Session, intake: IntakeResult, threshold: float) -> None:
    """Store a claim that passed the contract (status RECEIVED) and write INTAKE_COMPLETED."""
    intake_claim_data(
        session,
        intake.claim.model_dump(mode="json"),
        intake.field_confidences,
        intake.source_format,
        threshold,
    )


def load_intake(row: Claim) -> IntakeResult | None:
    """The stored claim as an IntakeResult, or None when it failed the contract at intake."""
    try:
        claim = IntakeClaim.model_validate(row.intake)
    except ValueError:
        return None
    return IntakeResult(
        claim=claim,
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


def _context_payload(context: ContextPackage, settings: Settings) -> dict:
    """The context event names the policy set and its knowledge version (D-POL-2)."""
    return {
        "plan_id": context.plan_id,
        "network": context.network.value,
        "policy_set": settings.policy_set,
        "knowledge_version": curated_knowledge_version(
            settings.policy_set, settings.embedding_model
        ),
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
        # Not a pipeline stop: the claim goes to FULL review like any CalculationError.
        raise CalculationError(f"plan {plan.plan_id} has no out-of-network terms")
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
            if fee is not None:  # a missing fee is the calculator's CalculationError
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
    return calculate(lines, network, terms, benefits, fees, accumulators, claim.other_coverage)


def prompt_lookups(session: Session, claim: IntakeClaim, policy_set: str) -> PromptLookups:
    first_day = min(line.date_of_service for line in claim.service_lines)
    codes = sorted({line.procedure_code for line in claim.service_lines})
    return PromptLookups(
        icd10_descriptions=lookups.icd10_descriptions(
            session, list(claim.diagnoses), lookups.icd10_fiscal_year(first_day)
        ),
        procedure_descriptions=lookups.procedure_descriptions(session, codes),
        policy_codes={
            policy_id: list(policy.procedure_codes)
            for policy_id, policy in load_curated(policy_set).policies.items()
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
    try:
        rules = evaluate(
            row.intake,
            row.field_confidences,
            reference_for_claim(session, row.intake),
            confidence_min=settings.extraction_confidence_min,
        )
    except MissingReference as exc:
        log.warning("reference_data_unavailable", claim_id=claim_id, missing=str(exc))
        raise ReferenceDataUnavailable(f"reference data not loaded: {exc}") from exc
    except InvalidClaimData as exc:  # intake refuses such claims; one stored before P2.5 may not
        raise PipelineError(f"claim {claim_id} cannot be checked: {exc}") from exc
    versions = Versions(rules_version=RULES_VERSION)
    record_event(session, claim_id, EventType.RULES_EVALUATED, _rules_payload(rules), versions)
    timestamps = Timestamps(received=row.received_date, processed=datetime.now(UTC))

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

    intake = load_intake(row)  # the claim passed Group A, so it passes the contract
    member = lookups.get_member(session, row.member_id)  # and R04 found the member
    if intake is None or member is None:
        raise PipelineError(f"claim {claim_id} passed the rules without a valid claim and member")
    claim = intake.claim
    network = (
        Network.IN_NETWORK
        if lookups.is_in_network(session, claim.billing_npi, member.plan_id)
        else Network.OUT_OF_NETWORK
    )
    claim_lookups = prompt_lookups(session, claim, settings.policy_set)
    try:
        context = assemble_context(
            session, claim, rules, member.plan_id, network, claim_lookups, retriever
        )
    except ContextError as exc:
        raise PipelineError(str(exc)) from exc
    record_event(
        session,
        claim_id,
        EventType.CONTEXT_ASSEMBLED,
        _context_payload(context, settings),
        versions,
    )

    user_message = render_user_message(claim, rules, context, claim_lookups)
    model_started = time.perf_counter()
    text = model.complete(system_prompt(), user_message)
    model_ms = round((time.perf_counter() - model_started) * 1000, 1)
    result = validate_output(text, rules, context)
    versions = Versions(
        rules_version=RULES_VERSION,
        model_name=model.name,
        prompt_version=PROMPT_VERSION,
        policy_versions={  # <policy set>@<effective date> (D-POL-2)
            c.policy_id: f"{settings.policy_set}@{c.effective_date.isoformat()}"
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
    output_errors = list(result.errors)
    try:
        calculation: CalculationResult | None = _calculate(
            session, claim, member, network, decisions
        )
    except CalculationError as exc:
        calculation = None
        output_errors.append(f"CALCULATION_FAILED: {exc}")
        record_event(
            session,
            claim_id,
            EventType.CALCULATION_FAILED,
            {"error": str(exc), "calculator_version": CALCULATOR_VERSION},
            versions,
        )
    else:
        record_event(
            session,
            claim_id,
            EventType.CALCULATED,
            {
                "network": network.value,
                "totals": calculation.amounts.totals.model_dump(),
                "calculator_version": CALCULATOR_VERSION,
            },
            versions,
        )
    tier = (
        ReviewTier.FULL
        if calculation is None
        else review_tier(
            result,
            calculation.amounts.totals.allowed_cents,
            low_confidence_fields(intake, settings.extraction_confidence_min),
            settings.review_high_dollar_cents,
        )
    )
    record = DecisionRecord(
        claim_id=claim_id,
        status=ClaimStatus.AWAITING_REVIEW,
        rules_outcome=rules,
        context_refs=context,
        slm_output=result.output,
        output_errors=output_errors,
        line_decisions=decisions,
        claim_decision=derive_claim_decision(decisions),
        amounts=calculation.amounts if calculation else None,
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
