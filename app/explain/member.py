"""The member's own views (D-MEM-2, D-MEM-3): what a patient sees of their claims, their benefits
this benefit year and their profile.

Built deterministically from the claim's status and decision record, the stored accumulators and
visit usage, and the plan's terms, never by the model (H15). A member sees a claim's outcome only
once it is final (as a provider does, D-AUTH-1; a rule outcome is final at once): until then
"Your claim is being processed" and nothing else of it. Each view below lists every field it has:
no clinical notes, model output, criteria, rule IDs, internal reason codes, reviewer notes or IDs,
field confidences or anything of another member (the tests check the JSON). A decided claim's
explanation of benefits is the patient EOB of D-EOB-1 (app/explain/eob.py), unchanged.

Amounts are the calculator's (H1): a claim's totals as its record stores them (none without a
calculation); the benefits are the plan's terms and the stored accumulators and visit usage, as
the calculator receives them, shown as they are. What is left of each deductible, maximum and visit
limit, and the share used, are the calculator's too (app/calculator/progress.py, D-MEM-3 as
amended): nothing here adds or subtracts.

A member may appeal a denied claim once (D-APL-1); while the appeal is open the claim shows as
being looked at again, and its outcome once the second reviewer finalizes it. A claim the checks
closed as a copy of one the plan already has says so, not "returned to your provider".
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.calculator.engine import Accumulators, NetworkTerms
from app.calculator.progress import remaining, used_bps
from app.domain.contracts import ClaimStatus, DecisionRecord, Network
from app.explain.eob import EOB_STATUSES, YearToDate
from app.explain.fields import line_index, line_numbers, lookup
from app.explain.reasons import claim_outcome

# A claim is final for its member as for its provider: a rule outcome at once, a model
# recommendation once a reviewer finalizes it.
NOT_FINAL = frozenset({ClaimStatus.RECEIVED, ClaimStatus.AWAITING_REVIEW})
PROCESSING = "PROCESSING"  # the member's one label for every claim not final yet
NOTHING_MET = Accumulators(deductible_met_cents=0, oop_met_cents=0)  # no stored row yet
HEADINGS = {
    PROCESSING: "Your claim is being processed",
    "APPROVED": "Your claim was approved",
    "PARTLY_APPROVED": "Your claim was partly approved",
    "PENDED": "Your claim is on hold",
    "DENIED": "Your claim was denied",
    "REJECTED": "Your claim was returned to your provider",
}
MESSAGES = {
    PROCESSING: "Your plan has the claim. What it pays shows here once the claim is decided.",
    "APPROVED": "Your plan paid its share of each service. The explanation of benefits shows what "
    "it paid and what you may owe the provider.",
    "PARTLY_APPROVED": "Your plan paid for some of the services and not for others. The "
    "explanation of benefits shows each service and why.",
    "PENDED": "Your plan needs more information from your provider before it can pay. The "
    "explanation of benefits shows which services are waiting.",
    "DENIED": "Your plan did not pay for the services on this claim. The explanation of benefits "
    "shows why.",
    "REJECTED": "Your plan could not process the claim as it was sent, so it went back to your "
    "provider to correct and send again. It has no explanation of benefits.",
}
DUPLICATE = "DUPLICATE"  # REJECTED only as a copy of a claim the plan already has
DUPLICATE_CODE = "RJ_DUPLICATE"
HEADINGS[DUPLICATE] = "This claim was a copy"
MESSAGES[DUPLICATE] = (
    "Your plan already had this claim from your provider, so this copy was closed. The first "
    "claim shows what your plan decided. You do not need to do anything."
)
APPEALED_HEADING = "Your appeal is being reviewed"
APPEALED_MESSAGE = (
    "A reviewer who did not decide the claim the first time is looking at it again. The outcome "
    "shows here once they decide."
)
ON_HOLD_BY_RULES = (  # a claim the rules put on hold: not decided, so no EOB (D-EOB-1)
    "Your plan needs something from your provider before it can decide the claim. Nothing has "
    "been paid yet."
)


@dataclass(frozen=True)
class MemberAppeal:
    """The member's view of an appeal on their claim: when it was filed and, once decided, whether
    the decision stood. Who filed it says only whether it was this member."""

    status: str  # OPEN or DECIDED
    outcome: str | None  # UPHELD (the decision stood) or CHANGED, once decided
    filed_on: str  # YYYY-MM-DD
    decided_on: str | None
    filed_by_you: bool


@dataclass(frozen=True)
class MemberClaim:
    """One of the member's claims. Until it is final: what it is (its ID, dates and provider) and
    "being processed"; once final, its outcome, the record's totals when it was calculated, and
    whether it has an explanation of benefits."""

    claim_id: str
    received: str  # YYYY-MM-DD, the day the plan received it
    service_date: str | None  # YYYY-MM-DD, the claim's first date of service
    provider_name: str | None  # the billing provider, when the plan knows them
    final: bool
    outcome: str  # PROCESSING until final; then the label key every dashboard shows (D-UI-6)
    heading: str
    message: str
    eob: bool  # GET /v1/member/claims/{claim_id}/eob has its explanation of benefits
    billed_cents: int | None  # final claims with a calculation only, as the record stores them
    plan_pays_cents: int | None
    patient_pays_cents: int | None
    services: list[str]  # each service line's plain procedure name, in line order
    appeal: MemberAppeal | None  # the claim's appeal, when it has one
    can_appeal: bool  # POST /v1/member/claims/{claim_id}/appeal accepts it now


def service_date(claim: Mapping[str, Any]) -> str | None:
    """The claim's first date of service as filed (YYYY-MM-DD), or None."""
    days = [
        day
        for line_no in line_numbers(claim)
        if isinstance(
            day := lookup(claim, f"service_lines.{line_index(claim, line_no)}.date_of_service"),
            str,
        )
    ]
    return min(days) if days else None


def service_names(claim: Mapping[str, Any], names: Mapping[str, str]) -> list[str]:
    """Each service line's procedure as the member reads it: its plain name from the code tables
    in data/raw, or the code itself when the tables have no name for it."""
    services = []
    for line_no in line_numbers(claim):
        code = lookup(claim, f"service_lines.{line_index(claim, line_no)}.procedure_code")
        if isinstance(code, str) and code:
            services.append(names.get(code) or f"Service {code}")
    return services


def _duplicate_only(record: DecisionRecord | None) -> bool:
    failed = [r for r in (record.rules_outcome.rule_results if record else []) if not r.passed]
    return bool(failed) and all(r.reason_code == DUPLICATE_CODE for r in failed)


def member_claim(
    status: ClaimStatus,
    record: DecisionRecord | None,
    claim: Mapping[str, Any],
    *,
    claim_id: str,
    received: date,
    provider_name: str | None,
    services: list[str] | None = None,
    appeal: MemberAppeal | None = None,
    can_appeal: bool = False,
) -> MemberClaim:
    """The member's view of one claim. `record` is read only for a final claim: a claim in review
    shows nothing of its recommendation."""
    first_day = service_date(claim)
    if status in NOT_FINAL:
        appealed = appeal is not None and appeal.status == "OPEN"
        return MemberClaim(
            claim_id=claim_id,
            received=received.isoformat(),
            service_date=first_day,
            provider_name=provider_name,
            final=False,
            outcome=PROCESSING,
            heading=APPEALED_HEADING if appealed else HEADINGS[PROCESSING],
            message=APPEALED_MESSAGE if appealed else MESSAGES[PROCESSING],
            eob=False,
            billed_cents=None,
            plan_pays_cents=None,
            patient_pays_cents=None,
            services=list(services or []),
            appeal=appeal,
            can_appeal=False,
        )
    outcome = claim_outcome(status, record)
    if outcome == "REJECTED" and _duplicate_only(record):
        outcome = DUPLICATE
    eob = status in EOB_STATUSES and record is not None
    totals = record.amounts.totals if record is not None and record.amounts is not None else None
    return MemberClaim(
        claim_id=claim_id,
        received=received.isoformat(),
        service_date=first_day,
        provider_name=provider_name,
        final=True,
        outcome=outcome,
        heading=HEADINGS[outcome],
        message=MESSAGES[outcome] if eob or outcome != "PENDED" else ON_HOLD_BY_RULES,
        eob=eob,
        billed_cents=totals.billed_cents if totals else None,
        plan_pays_cents=totals.plan_pays_cents if totals else None,
        patient_pays_cents=totals.member_pays_cents if totals else None,
        services=list(services or []),
        appeal=appeal,
        can_appeal=can_appeal,
    )


# --- Benefits this benefit year ------------------------------------------------------------------


@dataclass(frozen=True)
class VisitBenefit:
    """A visit-limited benefit: the plan's visits per benefit year and the visits used as stored
    at finalization (D-REV-8); the visits left and the share used are the calculator's."""

    benefit_category: str  # e.g. REHAB_THERAPY
    visit_limit: int
    visits_used: int
    visits_left: int
    used_bps: int  # 0 to 10000


@dataclass(frozen=True)
class NetworkProgress(YearToDate):
    """A network's year to date (as on an EOB) and how far through each limit the member is: what
    is left and the share met in basis points, the calculator's (app/calculator/progress.py)."""

    deductible_left_cents: int = 0
    deductible_met_bps: int = 0
    oop_left_cents: int = 0
    oop_met_bps: int = 0


@dataclass(frozen=True)
class MemberBenefits:
    """The member's benefit year so far: for each network the plan covers, the deductible and
    out-of-pocket maximum (the plan's terms) and what is met of each (the stored accumulators),
    the same shape as an EOB's year to date, with what is left of each; and each visit-limited
    benefit's visits. Formatted from what the calculator starts the member's next claim from; what
    is left and the shares are the calculator's (D-MEM-5)."""

    member_id: str
    plan_id: str
    plan_name: str
    plan_type: str
    benefit_year_start: str  # YYYY-MM-DD: deductibles and maximums reset every 1 January (D7)
    benefit_year_end: str
    as_of: str  # YYYY-MM-DD: the day they were read
    networks: list[NetworkProgress]  # in network, then out of network when the plan covers it
    visits: list[VisitBenefit]  # each visit-limited benefit the plan covers


def member_benefits(
    *,
    member_id: str,
    plan_id: str,
    plan_name: str,
    plan_type: str,
    year_start: date,
    as_of: date,
    terms: Mapping[str, NetworkTerms],
    stored: Mapping[str, Accumulators],
    visit_limits: Mapping[str, int],
    visits_used: Mapping[str, int],
) -> MemberBenefits:
    """`terms`: the plan's terms for each network it covers, as the pipeline gives them to the
    calculator; `stored`: the stored accumulators of this benefit year by network (a network
    without a stored row has met nothing, Accumulators(0, 0), as for the calculator);
    `visit_limits`: the plan's visit-limited benefits; `visits_used`: as stored."""
    networks = []
    for network in sorted(terms, key=lambda n: n != Network.IN_NETWORK.value):
        met = stored.get(network, NOTHING_MET)
        plan = terms[network]
        networks.append(
            NetworkProgress(
                network=network,
                period_start=year_start.isoformat(),
                deductible_met_cents=met.deductible_met_cents,
                deductible_cents=plan.deductible_cents,
                oop_met_cents=met.oop_met_cents,
                oop_max_cents=plan.oop_max_cents,
                deductible_left_cents=remaining(plan.deductible_cents, met.deductible_met_cents),
                deductible_met_bps=used_bps(plan.deductible_cents, met.deductible_met_cents),
                oop_left_cents=remaining(plan.oop_max_cents, met.oop_met_cents),
                oop_met_bps=used_bps(plan.oop_max_cents, met.oop_met_cents),
            )
        )
    return MemberBenefits(
        member_id=member_id,
        plan_id=plan_id,
        plan_name=plan_name,
        plan_type=plan_type,
        benefit_year_start=year_start.isoformat(),
        benefit_year_end=date(year_start.year, 12, 31).isoformat(),
        as_of=as_of.isoformat(),
        networks=networks,
        visits=[
            VisitBenefit(
                category,
                limit,
                visits_used.get(category, 0),
                remaining(limit, visits_used.get(category, 0)),
                used_bps(limit, visits_used.get(category, 0)),
            )
            for category, limit in sorted(visit_limits.items())
        ],
    )


# --- Profile -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MemberProfile:
    """Who the member is to the plan: name, member ID, plan and coverage dates. Nothing else of
    the member's record (no date of birth or address)."""

    member_id: str
    name: str
    plan_id: str
    plan_name: str
    plan_type: str
    coverage_start: str  # YYYY-MM-DD
    coverage_end: str | None  # None: coverage has no end date


def member_profile(
    *,
    member_id: str,
    first_name: str,
    last_name: str,
    plan_id: str,
    plan_name: str,
    plan_type: str,
    coverage_start: date,
    coverage_end: date | None,
) -> MemberProfile:
    return MemberProfile(
        member_id=member_id,
        name=f"{first_name} {last_name}".strip(),
        plan_id=plan_id,
        plan_name=plan_name,
        plan_type=plan_type,
        coverage_start=coverage_start.isoformat(),
        coverage_end=coverage_end.isoformat() if coverage_end else None,
    )
