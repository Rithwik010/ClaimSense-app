"""Curated data (data/curated/) is internally consistent (INSTRUCTIONS.md §9.2)."""

from app.db.curated import load_curated, parse_policy, validate_curated


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
