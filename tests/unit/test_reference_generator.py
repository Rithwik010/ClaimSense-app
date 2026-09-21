"""Reference-data generator (P2.2): deterministic, valid NPIs, consistent keys, distribution."""

from datetime import date

import pytest

from app.db.curated import load_curated
from app.domain.contracts import npi_is_valid
from training.generate.reference import ReferenceData, generate_reference


@pytest.fixture(scope="module")
def generated() -> tuple[ReferenceData, dict]:
    return generate_reference(seed=7)


def test_same_seed_gives_identical_output(generated: tuple[ReferenceData, dict]) -> None:
    again, _ = generate_reference(seed=7)
    assert again.tables() == generated[0].tables()


def test_different_seed_gives_different_output(generated: tuple[ReferenceData, dict]) -> None:
    other, _ = generate_reference(seed=8)
    assert other.members != generated[0].members


def test_counts(generated: tuple[ReferenceData, dict]) -> None:
    data, _ = generated
    assert len(data.members) == 500
    assert len(data.providers) == 100
    assert len(data.authorizations) == 150
    assert len(data.other_coverage) == 50


def test_npis_valid_and_unique(generated: tuple[ReferenceData, dict]) -> None:
    npis = [p["npi"] for p in generated[0].providers]
    assert all(npi_is_valid(npi) for npi in npis)
    assert len(set(npis)) == len(npis)
    assert all(len(p["tin"]) == 9 and p["tin"].isdigit() for p in generated[0].providers)


def test_foreign_keys_resolve(generated: tuple[ReferenceData, dict]) -> None:
    data, _ = generated
    curated = load_curated()
    members = {m["member_id"] for m in data.members}
    npis = {p["npi"] for p in data.providers}
    assert {m["plan_id"] for m in data.members} <= set(curated.plans)
    assert {a["member_id"] for a in data.authorizations} <= members
    assert {a["provider_npi"] for a in data.authorizations} <= npis
    assert {o["member_id"] for o in data.other_coverage} <= members
    assert {n["npi"] for n in data.provider_networks} == npis
    assert {p["provider_type"] for p in data.providers} <= set(curated.provider_types)


def test_scenario_variety_is_present(generated: tuple[ReferenceData, dict]) -> None:
    data, report = generated
    assert report["members_by_coverage"]["TERMINATED_IN_WINDOW"] > 0
    assert report["members_by_coverage"]["STARTS_IN_WINDOW"] > 0
    assert report["providers_by_enrollment"]["PENDING"] == 8
    assert report["authorizations_by_kind"]["EXPIRED"] > 0
    assert report["authorizations_by_kind"]["WRONG_CODE"] > 0
    assert any(not n["in_network"] for n in data.provider_networks)


def test_every_plan_has_enrolled_in_network_providers_of_every_type(
    generated: tuple[ReferenceData, dict],
) -> None:
    data, _ = generated
    enrolled = {p["npi"]: p for p in data.providers if p["enrollment_status"] == "ENROLLED"}
    for plan_id in load_curated().plans:
        types = [
            enrolled[n["npi"]]["provider_type"]
            for n in data.provider_networks
            if n["plan_id"] == plan_id and n["in_network"] and n["npi"] in enrolled
        ]
        for provider_type in {p["provider_type"] for p in data.providers}:
            assert types.count(provider_type) >= 2, (plan_id, provider_type)


def test_accumulators_stay_within_plan_limits(generated: tuple[ReferenceData, dict]) -> None:
    data, _ = generated
    curated = load_curated()
    plan_of = {m["member_id"]: curated.plans[m["plan_id"]] for m in data.members}
    for row in data.accumulators:
        plan = plan_of[row["member_id"]]
        terms = plan.in_network if row["network"] == "IN_NETWORK" else plan.out_of_network
        assert terms is not None
        assert 0 <= row["deductible_met_cents"] <= terms.deductible_cents
        assert row["deductible_met_cents"] <= row["oop_met_cents"] <= terms.oop_max_cents
        assert row["period_start"] == date(2026, 1, 1)


def test_visit_usage_stays_below_limit(generated: tuple[ReferenceData, dict]) -> None:
    data, _ = generated
    curated = load_curated()
    plan_of = {m["member_id"]: m["plan_id"] for m in data.members}
    for row in data.visit_usage:
        limit = curated.benefit(plan_of[row["member_id"]], row["benefit_category"]).visit_limit
        assert limit is not None and row["visits_used"] < limit


def test_authorizations_only_for_codes_that_need_them(
    generated: tuple[ReferenceData, dict],
) -> None:
    data, _ = generated
    curated = load_curated()
    plan_of = {m["member_id"]: m["plan_id"] for m in data.members}
    for auth in data.authorizations:
        plan_id = plan_of[auth["member_id"]]
        assert curated.auth_required(plan_id, auth["procedure_code"])
        assert auth["end_date"] >= auth["start_date"]
