"""Group B (R05 to R10) and the D8 precedence on synthetic claims (§8.3, A-R1, A-R2, A-R5). The
golden cases are in test_rules_golden.py."""

from dataclasses import replace
from datetime import date

import pytest

from app.domain.contracts import IntakeClaim, RuleOutcomeValue, RuleResult
from app.rules.engine import claim_outcome
from app.rules.reference import AuthorizationRef, ProviderRef, RulesReference
from app.rules.requirements import check_group_b
from tests.unit.rules_support import PCP, PLAN, SPECIALIST, claim_data, line, reference

UNKNOWN = "1999999992"  # valid check digit, not on file


def run(ref: RulesReference | None = None, **overrides: object) -> tuple[list[RuleResult], list]:
    ref = ref or reference()
    claim = IntakeClaim.model_validate(claim_data(**overrides))
    return check_group_b(claim, ref.members[claim.member_id], ref)


def failures(results: list[RuleResult]) -> list[tuple[str, str, str | None]]:
    return [(r.rule_id, r.outcome.value, r.reason_code) for r in results if not r.passed]


def test_a_clean_claim_passes_r05_to_r10_with_no_flags() -> None:
    results, flags = run()

    assert all(r.passed for r in results) and flags == []


def test_rules_are_reported_in_rule_order() -> None:
    results, _ = run()

    assert [r.rule_id for r in results] == ["R05", "R06", "R07", "R08", "R09", "R10"]


def test_unknown_provider_rejects_and_skips_the_rules_that_need_it() -> None:
    results, flags = run(billing_npi=UNKNOWN, service_lines=[line(rendering_npi=UNKNOWN)])

    assert failures(results) == [("R06", "REJECT", "RJ_PROVIDER_NOT_FOUND")]
    assert [r.rule_id for r in results] == ["R05", "R06"]
    assert flags == []


def test_pending_enrollment_pends() -> None:
    ref = reference(providers={PCP: ProviderRef(PCP, "PRIMARY_CARE", "PENDING")})

    results, _ = run(ref)

    assert failures(results) == [("R06", "PEND", "PD_PROVIDER_ENROLLMENT")]


@pytest.mark.parametrize(
    ("received", "in_network", "late"),
    [
        ("2027-01-03", True, False),  # 90 days: the last day of the in-network window
        ("2027-01-04", True, True),  # 91 days
        ("2027-04-03", False, False),  # 180 days: the out-of-network window
        ("2027-04-04", False, True),
    ],
)
def test_timely_filing_uses_the_window_for_the_network(
    received: str, in_network: bool, late: bool
) -> None:
    ref = reference(networks={(PCP, "PLN-A"): in_network})

    results, _ = run(ref, received_date=received)

    r07 = next(r for r in results if r.rule_id == "R07")
    assert r07.passed is not late
    assert r07.fields_used == [
        "received_date",
        "service_lines.0.date_of_service",
        "billing_npi",
        "member_id",
    ]


def test_timely_filing_counts_from_the_last_date_of_service() -> None:
    lines = [line(date_of_service="2026-10-01"), line(line_no=2, date_of_service="2026-11-15")]

    results, _ = run(service_lines=lines, received_date="2027-01-10")

    assert next(r for r in results if r.rule_id == "R07").passed


def test_no_network_row_is_out_of_network_and_a_covering_plan_flags_oon() -> None:
    results, flags = run(reference(networks={}))

    assert failures(results) == []
    assert flags == ["OON"]


def test_out_of_network_on_a_plan_without_oon_cover_is_denied_with_no_flag() -> None:
    ref = reference(networks={}, plans={"PLN-A": replace(PLAN, oon_covered=False)})

    results, flags = run(ref)

    assert failures(results) == [("R08", "DENY", "DN_OUT_OF_NETWORK")]
    assert flags == []


def test_late_filing_keeps_the_oon_flag_of_a_passing_r08() -> None:
    results, flags = run(reference(networks={}), received_date="2027-06-01")

    assert failures(results) == [("R07", "DENY", "DN_LATE_FILING")]
    assert flags == ["OON"]


def test_referral_needed_for_the_rendering_provider_type() -> None:
    lines = [line(rendering_npi=SPECIALIST, procedure_code="99214")]

    without, _ = run(service_lines=lines)
    with_referral, _ = run(service_lines=lines, referring_npi=PCP)

    assert failures(without) == [("R09", "DENY", "DN_MISSING_REFERRAL")]
    assert failures(with_referral) == []


def _auth(**overrides: object) -> AuthorizationRef:
    base = AuthorizationRef(
        "AUTH-1", "MBR-000123", SPECIALIST, "62323", date(2026, 10, 1), date(2026, 10, 5)
    )
    return replace(base, **overrides)


@pytest.mark.parametrize(
    ("auths", "ok"),
    [
        ((), False),
        ((_auth(),), True),  # the date of service is the authorization's last day
        ((_auth(end_date=date(2026, 10, 4)),), False),
        ((_auth(procedure_code="64483"),), False),
        ((_auth(provider_npi=PCP),), False),
        ((_auth(member_id="MBR-OTHER"),), False),
    ],
)
def test_prior_authorization_must_match_member_provider_code_and_date(
    auths: tuple[AuthorizationRef, ...], ok: bool
) -> None:
    lines = [line(rendering_npi=SPECIALIST, procedure_code="62323")]

    results, _ = run(reference(authorizations=auths), service_lines=lines, referring_npi=PCP)

    assert failures(results) == ([] if ok else [("R10", "DENY", "DN_NO_AUTH")])


def test_lines_with_an_unknown_rendering_provider_are_skipped_by_r09_and_r10() -> None:
    lines = [line(), line(line_no=2, rendering_npi=UNKNOWN, procedure_code="62323")]

    results, _ = run(service_lines=lines)

    assert failures(results) == [("R06", "REJECT", "RJ_PROVIDER_NOT_FOUND")]


def _failed(outcome: RuleOutcomeValue) -> RuleResult:
    return RuleResult(rule_id="R06", passed=False, outcome=outcome, detail="", fields_used=[])


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        ([RuleOutcomeValue.PEND, RuleOutcomeValue.DENY], RuleOutcomeValue.DENY),
        ([RuleOutcomeValue.DENY, RuleOutcomeValue.REJECT], RuleOutcomeValue.REJECT),
        ([RuleOutcomeValue.PEND], RuleOutcomeValue.PEND),
        ([], RuleOutcomeValue.PASS),
    ],
)
def test_d8_precedence_reject_over_deny_over_pend(
    outcomes: list[RuleOutcomeValue], expected: RuleOutcomeValue
) -> None:
    assert claim_outcome([_failed(o) for o in outcomes]) is expected
