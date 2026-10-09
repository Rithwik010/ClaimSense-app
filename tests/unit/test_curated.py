"""Curated data (data/curated/) is internally consistent (INSTRUCTIONS.md §9.2)."""

from dataclasses import replace

from app.db.curated import CodeRole, em_codes, load_curated, parse_policy, validate_curated


def test_curated_files_are_consistent() -> None:
    assert validate_curated(load_curated()) == []


def test_counts() -> None:
    data = load_curated()
    assert len(data.plans) == 5
    assert len(data.scope) == 60
    assert 15 <= len(data.policies) <= 25
    assert all(policy.criteria for policy in data.policies.values())


def test_every_criterion_cites_a_source() -> None:
    for criterion in load_curated().criteria().values():
        assert criterion.source.startswith("LCD L"), criterion.criterion_id


def test_policy_parser() -> None:
    text = (
        "---\npolicy_id: POL-IMG-004\ntitle: Lumbar spine MRI\nprocedure_codes: ['72148']\n"
        "plan_ids: ['ALL']\neffective_date: 2025-01-01\nsources: ['LCD X']\n"
        "billing_article: A1\nsplit: TRAIN\n---\n\n## POL-IMG-004.c1\nFirst line\ncontinues.\n\n"
        "Source: LCD X, section.\n\n## POL-IMG-004.c2\nSecond.\n\nSource: LCD X.\n"
    )
    policy = parse_policy(text)
    assert [c.criterion_id for c in policy.criteria] == ["POL-IMG-004.c1", "POL-IMG-004.c2"]
    assert policy.criteria[0].text == "First line continues."
    assert policy.criteria[0].source == "LCD X, section."


def test_auth_agrees_across_candidate_categories() -> None:
    data = load_curated()
    assert data.auth_required("PLN-PPO-GOLD", "62323")
    assert not data.auth_required("PLN-PPO-GOLD", "45378")
    assert data.auth_required("PLN-HMO", "97110")
    assert not data.auth_required("PLN-PPO-GOLD", "97110")


# --- Rules v2 data (D-RULE-3, D-RULE-4) ----------------------------------------------------------


def test_r15_follows_the_articles_where_the_v1_group_sets_differ() -> None:
    support = load_curated().diagnosis_support

    assert support["66982"].alternatives == ((1, 2),)  # v1 (generator, V1a)
    assert support["66982"].rule_alternatives == ((1,),)  # A56544: group 2 "if applicable"
    assert support["45385"].rule_alternatives == ((1,), (2, 3))
    assert support["45385"].rule_first_group == 2  # A56456: the 2A code is the primary
    assert support["11720"].rule_alternatives == ((1,), (2,), (3,), (4,))
    assert support["11720"].rule_group_modifiers == ((2, frozenset({"Q7", "Q8", "Q9"})),)
    unchanged = [c for c in support if c not in {"66982", "45378", "45380", "45385"} | {"11720"}]
    assert all(
        support[c].rule_alternatives == support[c].alternatives for c in unchanged if c != "11721"
    )


def test_the_rule_code_roles_and_diagnosis_sets() -> None:
    data = load_curated()
    roles = data.code_roles

    assert len(roles) == 46
    assert roles["64484"] == CodeRole(
        "64484", "ESI_TRANSFORAMINAL_ADDON", "LUMBAR_SACRAL", "64483", None, roles["64484"].source
    )
    assert {c for c, r in roles.items() if r.role == "TESTING_TIME"} == {"96130", "96131", "96136"}
    assert [roles[c].minutes_per_unit for c in ("96130", "96131", "96136")] == [60, 60, 30]
    assert data.diagnosis_sets["PARASOMNIA"] == {
        "G4750", "G4751", "G4752", "G4753", "G4754", "G4759",
    }  # fmt: skip
    assert data.diagnosis_sets["FACET_SYNOVIAL_CYST"] == {"M7130", "M7138"}
    assert all(role.source for role in roles.values())


def test_rule_data_problems_are_found() -> None:
    data = load_curated()
    roles = dict(data.code_roles)
    roles["64484"] = replace(roles["64484"], primary_code="64490")  # a facet code, not an ESI
    roles["95806"] = replace(roles["95806"], minutes_per_unit=60)
    roles["62321"] = replace(roles["62321"], spinal_region=None)
    support = dict(data.diagnosis_support)
    support["45385"] = replace(support["45385"], rule_first_group=5)

    problems = validate_curated(replace(data, code_roles=roles, diagnosis_support=support))

    assert problems == [
        "45385: rule_first_group is in no rule_groups alternative",
        "62321: spinal region does not fit role ESI_INTERLAMINAR",
        "64484: primary code 64490 has the wrong role",
        "95806: minutes per unit do not fit role HOME_SLEEP_TEST",
    ]


def test_every_rules_v2_reason_code_has_a_carc_mapping() -> None:
    """D-RULE-3: the CARC and RARC the team approved for each new internal reason code."""
    from app.rules.lcd_edits import REASON_RULES

    mapped = load_curated().reason_codes
    assert set(REASON_RULES) <= set(mapped)
    assert {code: (mapped[code].carc, mapped[code].rarc) for code in sorted(REASON_RULES)} == {
        "DN_DX_NOT_SUPPORTED": ("11", "N115"),
        "DN_ESI_LEVELS": ("151", "N115"),
        "DN_FACET_LEVELS": ("50", "N115"),
        "DN_HOME_TEST_PARASOMNIA": ("50", "N115"),
        "DN_MULTIPLE_BLOCKS": ("50", "N115"),
    }


# --- R11's modifiers (D-RULE-8) -------------------------------------------------------------------


def test_the_ncci_ptp_associated_modifiers_and_their_placement() -> None:
    data = load_curated()
    modifiers = data.ptp_modifiers

    assert len(modifiers) == 44  # NCCI Policy Manual 2026, Chapter I section E, page I-14
    assert {m for m, x in modifiers.items() if x.group == "GLOBAL_SURGERY"} == {
        "24", "25", "57", "58", "78", "79",
    }  # fmt: skip
    assert modifiers["25"].paired_global_days == {"000", "010", "XXX"}  # page I-16
    assert modifiers["57"].paired_global_days == {"090"}  # page I-13
    assert {modifiers[m].placement for m in ("59", "XE", "XP", "XS", "XU")} == {"NOT_EM"}
    assert {x.placement for x in modifiers.values() if x.group == "ANATOMIC"} == {"DIFFERENT_SITES"}
    assert data.bypass_modifiers <= set(modifiers)  # the frozen v1 list stays for the generator
    assert em_codes(data) == {f"9920{n}" for n in (2, 3, 4, 5)} | {f"9921{n}" for n in range(1, 6)}
