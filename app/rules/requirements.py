"""Group B (hard requirements): R05 to R10 (§8.3). Every rule is evaluated; the claim outcome is
the most severe failure, REJECT over DENY over PEND (D8).

A-R2: R06 checks the billing NPI and every rendering NPI. R07 and R08 need the billing provider
and are not evaluated when it is not found; R09 and R10 skip lines whose rendering provider is not
found (A-R5), and are not evaluated when no line is left. R06 reports the unknown provider.
"""

from app.domain.contracts import IntakeClaim, RuleOutcomeValue, RuleResult
from app.rules.eligibility import check_eligibility
from app.rules.reference import MemberRef, PlanRef, RulesReference
from app.rules.results import failed, line_fields, passed

OON_FLAG = "OON"
PENDING = "PENDING"


def check_providers(claim: IntakeClaim, reference: RulesReference) -> RuleResult:
    """R06: every billing and rendering provider is on file (else REJECT) and enrolled (else
    PEND)."""
    npis = list(
        dict.fromkeys([claim.billing_npi, *(ln.rendering_npi for ln in claim.service_lines)])
    )
    unknown = [npi for npi in npis if npi not in reference.providers]
    pending = [
        npi
        for npi in npis
        if npi in reference.providers and reference.providers[npi].enrollment_status == PENDING
    ]
    fields = ["billing_npi", *line_fields(len(claim.service_lines), "rendering_npi")]
    if unknown:
        return failed(
            "R06",
            RuleOutcomeValue.REJECT,
            "RJ_PROVIDER_NOT_FOUND",
            f"Provider not found: {', '.join(unknown)}.",
            fields,
        )
    if pending:
        return failed(
            "R06",
            RuleOutcomeValue.PEND,
            "PD_PROVIDER_ENROLLMENT",
            f"Provider enrollment pending: {', '.join(pending)}.",
            fields,
        )
    return passed("R06", "Every billing and rendering provider is enrolled.", fields)


def check_timely_filing(claim: IntakeClaim, plan: PlanRef, in_network: bool) -> RuleResult:
    """R07: received date minus the last date of service is within the plan's window for the
    billing provider's network status."""
    last = max(line.date_of_service for line in claim.service_lines)
    days = (claim.received_date - last).days
    window = plan.filing_window_inn_days if in_network else plan.filing_window_oon_days
    network = "in-network" if in_network else "out-of-network"
    detail = (
        f"Received {days} days after the last date of service {last.isoformat()}; "
        f"{plan.plan_id} {network} window {window} days."
    )
    fields = [
        "received_date",
        *line_fields(len(claim.service_lines), "date_of_service"),
        "billing_npi",
        "member_id",
    ]
    if days > window:
        return failed("R07", RuleOutcomeValue.DENY, "DN_LATE_FILING", detail, fields)
    return passed("R07", detail, fields)


def check_network(claim: IntakeClaim, plan: PlanRef, in_network: bool) -> RuleResult:
    """R08: an out-of-network billing provider is denied unless the plan covers out-of-network
    care (then the claim carries the flag OON)."""
    fields = ["billing_npi", "member_id"]
    if in_network:
        return passed("R08", f"{claim.billing_npi} is in network for {plan.plan_id}.", fields)
    if plan.oon_covered:
        return passed(
            "R08",
            f"{claim.billing_npi} is out of network; {plan.plan_id} covers out-of-network care.",
            fields,
        )
    return failed(
        "R08",
        RuleOutcomeValue.DENY,
        "DN_OUT_OF_NETWORK",
        f"{claim.billing_npi} is out of network; "
        f"{plan.plan_id} does not cover out-of-network care.",
        fields,
    )


def check_referral(
    claim: IntakeClaim, plan: PlanRef, reference: RulesReference
) -> RuleResult | None:
    """R09: a rendering provider type that needs a referral on the plan, and no referring NPI."""
    known = [ln for ln in claim.service_lines if ln.rendering_npi in reference.providers]
    if not known:
        return None
    needing = [
        ln
        for ln in known
        if reference.providers[ln.rendering_npi].provider_type in plan.referral_provider_types
    ]
    fields = [
        "referring_npi",
        *line_fields(len(claim.service_lines), "rendering_npi"),
        "member_id",
    ]
    if needing and claim.referring_npi is None:
        types = sorted({reference.providers[ln.rendering_npi].provider_type for ln in needing})
        return failed(
            "R09",
            RuleOutcomeValue.DENY,
            "DN_MISSING_REFERRAL",
            f"{plan.plan_id} needs a referral for {', '.join(types)}; no referring provider.",
            fields,
        )
    if needing:
        return passed("R09", f"Referring provider {claim.referring_npi} is on the claim.", fields)
    return passed("R09", f"No line needs a referral on {plan.plan_id}.", fields)


def check_prior_auth(
    claim: IntakeClaim, plan: PlanRef, reference: RulesReference
) -> RuleResult | None:
    """R10: every line whose code needs authorization on the plan has an authorization for the
    member, the line's rendering provider and code, covering its date of service (inclusive)."""
    known = [ln for ln in claim.service_lines if ln.rendering_npi in reference.providers]
    if not known:
        return None
    missing = [
        ln
        for ln in known
        if ln.procedure_code in plan.auth_required_codes
        and not any(
            auth.matches(claim.member_id, ln.rendering_npi, ln.procedure_code, ln.date_of_service)
            for auth in reference.authorizations
        )
    ]
    fields = [
        "member_id",
        *line_fields(
            len(claim.service_lines), "procedure_code", "rendering_npi", "date_of_service"
        ),
    ]
    if missing:
        lines = ", ".join(f"line {ln.line_no} ({ln.procedure_code})" for ln in missing)
        return failed(
            "R10",
            RuleOutcomeValue.DENY,
            "DN_NO_AUTH",
            f"No matching prior authorization for {lines}.",
            fields,
        )
    return passed("R10", "Every line that needs prior authorization has one.", fields)


def check_group_b(
    claim: IntakeClaim, member: MemberRef, reference: RulesReference
) -> tuple[list[RuleResult], list[str]]:
    """R05 to R10 in order, and the claim flags (OON when R08 passes out of network)."""
    plan = reference.plans[member.plan_id]
    results = [check_eligibility(claim, member), check_providers(claim, reference)]
    flags = []
    if claim.billing_npi in reference.providers:
        in_network = reference.in_network(claim.billing_npi, plan.plan_id)
        network = check_network(claim, plan, in_network)
        results += [check_timely_filing(claim, plan, in_network), network]
        if network.passed and not in_network:
            flags.append(OON_FLAG)
    results += [
        result
        for result in (
            check_referral(claim, plan, reference),
            check_prior_auth(claim, plan, reference),
        )
        if result is not None
    ]
    return results, flags
