"""Hand-built decision records and claims for the D-UI-6 unit tests (the provider's explanation and
billing, the claim summary and the reason table): one per path, with amounts as the calculator
would store them."""

from datetime import UTC, date, datetime
from typing import Any

from app.domain.contracts import (
    AmountTotals,
    ClaimStatus,
    ContextPackage,
    CostBreakdown,
    CriterionResult,
    CriterionStatus,
    DecisionRecord,
    FinalLineDecision,
    LineAmounts,
    LineContext,
    LineDecision,
    LineOverride,
    LineRuleOutcome,
    Network,
    RetrievedCriterion,
    ReviewAction,
    ReviewTier,
    RuleResult,
    RulesOutcome,
    SLMLine,
    SLMOutput,
    Timestamps,
    Versions,
)

APPROVE, DENY, PEND = LineDecision.APPROVE, LineDecision.DENY, LineDecision.PEND
CODES = {APPROVE: [], DENY: ["DN_NOT_MEDICALLY_NECESSARY"], PEND: ["PD_MISSING_DOCUMENTATION"]}
NOTE = "Low back pain for eight weeks despite physical therapy; numbness in the left leg."
CRITERION_TEXT = "Pain lasting at least four weeks despite conservative care is documented."
EXCLUSION_TEXT = "The service is excluded for pain without a nerve finding."


def claim(lines: int = 2) -> dict[str, Any]:
    """A claim as stored at intake, with `lines` service lines."""
    return {
        "claim_id": "CLM-UI-0001",
        "member_id": "MBR-000123",
        "patient": {
            "first_name": "Ana",
            "last_name": "Lopez",
            "date_of_birth": "1970-03-04",
            "sex": "F",
            "address": {"line1": "1 Main St", "city": "Town", "state": "OR", "zip_code": "97001"},
        },
        "subscriber_is_patient": True,
        "billing_npi": "1234567893",
        "billing_tin": "123456789",
        "referring_npi": None,
        "prior_auth_number": None,
        "diagnoses": ["M5450", "M5416"],
        "service_lines": [
            {
                "line_no": n,
                "date_of_service": "2026-10-05",
                "place_of_service": "11",
                "procedure_code": code,
                "modifiers": [],
                "diagnosis_pointers": ["A", "B"],
                "units": 1,
                "charge_cents": 30000,
                "rendering_npi": "1234567893",
            }
            for n, code in list(enumerate(("64483", "99214"), start=1))[:lines]
        ],
        "clinical_notes": NOTE,
        "received_date": "2026-10-09",
        "frequency_code": "1",
        "other_coverage": None,
    }


def final(
    line_no: int,
    decision: LineDecision,
    source: str = "MODEL",
    codes: list[str] | None = None,
) -> FinalLineDecision:
    return FinalLineDecision(
        line_no=line_no,
        decision=decision,
        benefit_category="PAIN_MANAGEMENT" if decision is APPROVE else None,
        source=source,  # type: ignore[arg-type]
        reason_codes=CODES[decision] if codes is None and source == "MODEL" else (codes or []),
    )


def amounts(
    line_no: int,
    billed: int,
    allowed: int = 0,
    deductible: int = 0,
    copay: int = 0,
    coinsurance: int = 0,
    primary: int = 0,
    network: Network = Network.IN_NETWORK,
) -> LineAmounts:
    """A line's amounts as the calculator stores them (A1 to A9): a line with allowed 0 is billed
    only."""
    share = deductible + copay + coinsurance
    plan = max(0, min(allowed - share, allowed - primary)) if allowed else 0
    member = max(0, allowed - primary - plan) if allowed else 0
    gap = billed - allowed if allowed else 0
    return LineAmounts(
        line_no=line_no,
        billed_cents=billed,
        allowed_cents=allowed,
        contractual_adjustment_cents=gap if network is Network.IN_NETWORK else 0,
        deductible_cents=deductible,
        copay_cents=copay,
        coinsurance_cents=coinsurance,
        cob_primary_paid_cents=primary,
        plan_pays_cents=plan,
        member_pays_cents=member,
        balance_bill_exposure_cents=gap if network is Network.OUT_OF_NETWORK else 0,
    )


def breakdown(*lines: LineAmounts) -> CostBreakdown:
    names = [n for n in LineAmounts.model_fields if n.endswith("_cents")]
    totals = {n: sum(getattr(line, n) for line in lines) for n in names}
    return CostBreakdown(lines=list(lines), totals=AmountTotals(**totals))


def _criteria(statuses: dict[int, list[CriterionStatus]]) -> list[RetrievedCriterion]:
    found = []
    for i in range(max((len(s) for s in statuses.values()), default=0)):
        exclusion = i == 1
        found.append(
            RetrievedCriterion(
                criterion_id=f"POL-PAIN-001.c{i + 1}",
                policy_id="POL-PAIN-001",
                policy_title="Epidural steroid injections",
                text=EXCLUSION_TEXT if exclusion else CRITERION_TEXT,
                source="L39240",
                effective_date=date(2026, 1, 1),
                criterion_type="exclusion" if exclusion else "requirement",
            )
        )
    return found


def model_record(
    status: ClaimStatus,
    decisions: list[FinalLineDecision],
    breakdown_: CostBreakdown | None = None,
    statuses: dict[int, list[CriterionStatus]] | None = None,
    review: ReviewAction | None = None,
    tier: ReviewTier = ReviewTier.STANDARD,
    rule_results: list[RuleResult] | None = None,
    line_flags: dict[int, list[str]] | None = None,
    output_errors: list[str] | None = None,
    network: Network = Network.IN_NETWORK,
) -> DecisionRecord:
    """A claim that reached the model: its criteria (by line, the statuses the model gave each),
    the final line decisions and the amounts."""
    statuses = statuses or {d.line_no: [CriterionStatus.MET] for d in decisions}
    criteria = _criteria(statuses)
    return DecisionRecord(
        claim_id="CLM-UI-0001",
        status=status,
        rules_outcome=RulesOutcome(
            claim_outcome="PASS",
            rule_results=rule_results
            or [RuleResult(rule_id="R01", passed=True, outcome="PASS", detail="", fields_used=[])],
            line_outcomes=[
                LineRuleOutcome(
                    line_no=d.line_no,
                    outcome="DENY" if d.source == "RULE" else "PASS",
                    reason_codes=d.reason_codes if d.source == "RULE" else [],
                    flags=(line_flags or {}).get(d.line_no, []),
                )
                for d in decisions
            ],
        ),
        context_refs=ContextPackage(
            claim_id="CLM-UI-0001",
            plan_id="PLN-PPO-GOLD",
            plan_type="PPO",
            network=network,
            excluded_codes=[],
            lines=[
                LineContext(
                    line_no=d.line_no,
                    procedure_code="64483",
                    candidate_benefits=[],
                    criteria=criteria[: len(statuses.get(d.line_no, []))],
                )
                for d in decisions
            ],
        ),
        slm_output=SLMOutput(
            lines=[
                SLMLine(
                    line_no=d.line_no,
                    decision=d.decision if d.source != "REVIEWER" else APPROVE,
                    benefit_category="PAIN_MANAGEMENT",
                    criteria=[
                        CriterionResult(
                            criterion_id=f"POL-PAIN-001.c{i + 1}",
                            status=s,
                            evidence=NOTE[:30]
                            if s in (CriterionStatus.MET, CriterionStatus.NOT_MET)
                            else "Not documented in the notes.",
                        )
                        for i, s in enumerate(statuses.get(d.line_no, []))
                    ],
                    reasons=[],
                    missing_information=[],
                )
                for d in decisions
                if d.source != "RULE"
            ],
            complexity="LOW",
        ),
        output_errors=output_errors or [],
        line_decisions=decisions,
        claim_decision=None,
        amounts=breakdown_,
        review_tier=tier,
        review=review,
        versions=Versions(rules_version="2.1.0", model_name="stub", prompt_version="decision_v3"),
        timestamps=Timestamps(received=date(2026, 10, 9)),
    )


def rule_record(
    status: ClaimStatus,
    rule_id: str,
    code: str,
    fields_used: list[str],
    line_no: int | None = None,
) -> DecisionRecord:
    """A claim the rules decided: one failed rule."""
    outcome = {"REJECTED": "REJECT", "DENIED_BY_RULE": "DENY", "PENDED_BY_RULE": "PEND"}
    return DecisionRecord(
        claim_id="CLM-UI-0001",
        status=status,
        rules_outcome=RulesOutcome(
            claim_outcome=outcome[status.value],
            rule_results=[
                RuleResult(rule_id="R01", passed=True, outcome="PASS", detail="", fields_used=[]),
                RuleResult(
                    rule_id=rule_id,
                    passed=False,
                    outcome=outcome[status.value],
                    reason_code=code,
                    detail="",
                    fields_used=fields_used,
                    line_no=line_no,
                ),
            ],
            line_outcomes=[],
        ),
        versions=Versions(rules_version="2.1.0"),
        timestamps=Timestamps(received=date(2026, 10, 9)),
    )


def review(*overrides: LineOverride) -> ReviewAction:
    return ReviewAction(
        claim_id="CLM-UI-0001",
        reviewer_id="reviewer-7",
        action="OVERRIDE" if overrides else "ACCEPT",
        line_overrides=list(overrides),
        timestamp=datetime(2026, 10, 10, 9, 0, tzinfo=UTC),
    )
