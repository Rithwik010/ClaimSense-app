"""Policy sets (D-POL-2) and the v2 exact lookup (D-RAG-2) on in-memory Qdrant: exact against the
v2 policy files for every covered code, plan and date; equal to the golden snapshot of each code's
criteria; the two sets isolated; v1 unchanged (knowledge version 36cfc77305a5)."""

import json
from datetime import date
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from app.db.curated import CURATED_DIR, load_curated, parse_policy, validate_curated
from app.rag.knowledge import (
    COVERAGE_COLLECTION,
    COVERAGE_COLLECTIONS,
    build_coverage_collection,
    criterion_chunks,
    curated_knowledge_version,
    knowledge_version,
)
from app.rag.retrieve import CriteriaRetriever, ExactCriteriaRetriever, RetrievalUnavailable
from scripts.verify.rag_v2_snapshot import SNAPSHOT, render
from tests.unit.test_retrieval import FakeEmbedder

DAYS = (date(2025, 12, 31), date(2026, 1, 1), date(2026, 10, 1), date(2026, 12, 31))
V1_KNOWLEDGE = "36cfc77305a5"  # model v1 (PROGRESS_LOG, D-POL-2)


@pytest.fixture(scope="module")
def client() -> QdrantClient:
    client = QdrantClient(":memory:")
    for policy_set in ("v1", "v2"):
        build_coverage_collection(client, FakeEmbedder(), load_curated(policy_set))
    return client


def expected_ids(code: str, plan_id: str, day: date) -> list[str]:
    """Straight from the v2 files: every criterion shown on the code, in file order."""
    return [
        criterion.criterion_id
        for policy in load_curated("v2").policies.values()
        if ("ALL" in policy.plan_ids or plan_id in policy.plan_ids) and policy.effective_date <= day
        for criterion in policy.criteria
        if code in policy.criterion_codes(criterion)
    ]


def test_both_policy_sets_load_and_validate() -> None:
    v1, v2 = load_curated("v1"), load_curated("v2")

    assert validate_curated(v1) == [] and validate_curated(v2) == []
    assert (v1.policy_set, v2.policy_set) == ("v1", "v2")
    assert set(v1.policies) == set(v2.policies)
    assert all(c.criterion_type is None for p in v1.policies.values() for c in p.criteria)
    assert all(c.criterion_type for p in v2.policies.values() for c in p.criteria)
    assert load_curated() is v1  # the default stays v1 for model v1's tools


def test_v1_is_unchanged() -> None:
    chunks = criterion_chunks(load_curated("v1"))

    assert knowledge_version(chunks, "BAAI/bge-small-en-v1.5") == V1_KNOWLEDGE
    assert curated_knowledge_version("v1", "BAAI/bge-small-en-v1.5") == V1_KNOWLEDGE
    assert COVERAGE_COLLECTION == COVERAGE_COLLECTIONS["v1"] == "coverage_policies_v1"
    for path in sorted((CURATED_DIR / "coverage_policies" / "v1").glob("POL-*.md")):
        assert "\nType:" not in path.read_text(encoding="utf-8"), path.name


def test_v2_fields_are_parsed_and_kept_out_of_the_text() -> None:
    policy = parse_policy(
        "---\npolicy_id: POL-X-001\ntitle: T\nprocedure_codes: ['1', '2']\nplan_ids: ['ALL']\n"
        "effective_date: 2026-01-01\nsources: ['s']\nbilling_article: A1\nsplit: TRAIN\n"
        "policy_set: v2\nreplaces: {'POL-X-001.c1': ['POL-X-001.c2']}\n---\n\n"
        "## POL-X-001.c2\nFirst line.\nSecond line.\n\nType: conditional\nApplies to: 2\n"
        "Group: indication\nSource: LCD L1 cov-001.\n"
    )
    criterion = policy.criteria[0]

    assert criterion.text == "First line. Second line."
    assert (criterion.criterion_type, criterion.applies_to, criterion.group) == (
        "conditional",
        ("2",),
        "indication",
    )
    assert criterion.source == "LCD L1 cov-001."
    assert policy.criterion_codes(criterion) == ("2",)
    assert policy.replaces == {"POL-X-001.c1": ("POL-X-001.c2",)}


def test_exact_lookup_matches_the_policy_files_for_every_code_plan_and_date(client) -> None:  # noqa: ANN001
    curated = load_curated("v2")
    search = ExactCriteriaRetriever(client)
    codes = sorted({code for p in curated.policies.values() for code in p.procedure_codes})

    for code in codes + ["99213", "00000"]:
        for plan_id in curated.plans:
            for day in DAYS:
                got = search.retrieve("ignored", plan_id, day, code)
                assert [c.criterion_id for c in got] == expected_ids(code, plan_id, day), (
                    code,
                    plan_id,
                    day,
                )


def test_exact_lookup_equals_the_golden_snapshot(client) -> None:  # noqa: ANN001
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["codes"]
    search = ExactCriteriaRetriever(client)

    assert SNAPSHOT.read_text(encoding="utf-8") == render(), "run scripts.verify.rag_v2_snapshot"
    for code, criteria in snapshot.items():
        got = search.retrieve("", "PLN-HMO", date(2026, 11, 2), code)
        found = [
            {"criterion_id": c.criterion_id, "criterion_type": c.criterion_type, "group": c.group}
            for c in got
        ]
        assert found == criteria, code


def test_exact_lookup_returns_the_criterion_fields(client) -> None:  # noqa: ANN001
    got = ExactCriteriaRetriever(client).retrieve("", "PLN-EPO", date(2026, 11, 2), "11720")
    criteria = {c.criterion_id: c for c in load_curated("v2").criteria().values()}

    assert [c.criterion_id for c in got] == [f"POL-FOOT-001.c{n}" for n in (1, 2, 4, 5, 6)]
    for found in got:
        source = criteria[found.criterion_id]
        assert (found.text, found.source) == (source.text, source.source)
        assert (found.criterion_type, found.group) == (source.criterion_type, source.group)
    assert got[-1].criterion_type == "exclusion" and got[-1].group is None


def test_applies_to_limits_a_criterion_to_its_codes(client) -> None:  # noqa: ANN001
    search = ExactCriteriaRetriever(client)
    day = date(2026, 11, 2)

    holter = {c.criterion_id for c in search.retrieve("", "PLN-HMO", day, "93224")}
    extended = {c.criterion_id for c in search.retrieve("", "PLN-HMO", day, "93241")}

    assert "POL-CAR-002.c4" in holter and "POL-CAR-002.c4" not in extended
    assert extended == {"POL-CAR-002.c5"}


def test_excluded_policies_and_no_cap(client) -> None:  # noqa: ANN001
    search = ExactCriteriaRetriever(client)
    day = date(2026, 11, 2)

    esi = search.retrieve("", "PLN-HMO", day, "64483")
    kept = search.retrieve("", "PLN-HMO", day, "64483", exclude_policies={"POL-PAIN-001"})

    assert len(esi) > 5  # no top-k cap (D-RAG-1)
    assert kept == []


def test_the_sets_are_isolated(client) -> None:  # noqa: ANN001
    day = date(2026, 11, 2)
    v1_ids = set(load_curated("v1").criteria())
    v2_ids = set(load_curated("v2").criteria())
    v1 = CriteriaRetriever(client, FakeEmbedder(), top_k=50, min_score=-1.0)
    v2 = ExactCriteriaRetriever(client)

    for code in ("11720", "93241", "64483", "45380", "95806"):
        assert {c.criterion_id for c in v1.retrieve("x", "PLN-HMO", day, code)} <= v1_ids
        found = v2.retrieve("x", "PLN-HMO", day, code)
        assert {c.criterion_id for c in found} <= v2_ids
        assert all(c.criterion_type for c in found)
    assert v2_ids - v1_ids  # the v1 collection never returns a new v2 criterion


def test_a_missing_collection_or_code_fails_loudly() -> None:
    search = ExactCriteriaRetriever(QdrantClient(":memory:"))

    with pytest.raises(RetrievalUnavailable):
        search.retrieve("", "PLN-HMO", date(2026, 11, 2), "11720")
    with pytest.raises(ValueError, match="procedure code"):
        search.retrieve("", "PLN-HMO", date(2026, 11, 2))


def test_a_count_mismatch_is_retrieval_unavailable(client, monkeypatch) -> None:  # noqa: ANN001
    search = ExactCriteriaRetriever(client)
    real_count = client.count

    def one_more(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        result = real_count(*args, **kwargs)
        return type(result)(count=result.count + 1)

    monkeypatch.setattr(client, "count", one_more)

    with pytest.raises(RetrievalUnavailable, match="exact lookup returned"):
        search.retrieve("", "PLN-HMO", date(2026, 11, 2), "11720")


def test_the_v2_knowledge_version_follows_the_lookup_fields() -> None:
    import dataclasses

    curated = load_curated("v2")
    base = curated_knowledge_version("v2", "any-embedder")
    policy = curated.policies["POL-FOOT-001"]
    retyped = dataclasses.replace(
        policy,
        criteria=(dataclasses.replace(policy.criteria[0], group=None), *policy.criteria[1:]),
    )
    changed = dataclasses.replace(curated, policies={**curated.policies, policy.policy_id: retyped})
    from app.rag.knowledge import knowledge_version_v2

    assert base == curated_knowledge_version("v2", "another-embedder")  # no vectors used
    assert knowledge_version_v2(criterion_chunks(curated)) == base
    assert knowledge_version_v2(criterion_chunks(changed)) != base


def test_v1_criteria_dump_without_the_v2_fields() -> None:
    from app.domain.contracts import RetrievedCriterion

    v1 = RetrievedCriterion(
        criterion_id="POL-IMG-002.c1",
        policy_id="POL-IMG-002",
        policy_title="T",
        text="x",
        source="s",
        effective_date=date(2026, 1, 1),
    )
    v2 = v1.model_copy(update={"criterion_type": "exclusion"})

    assert "criterion_type" not in v1.model_dump() and "group" not in v1.model_dump(mode="json")
    assert v2.model_dump()["criterion_type"] == "exclusion" and "group" not in v2.model_dump()
    assert RetrievedCriterion.model_validate(v2.model_dump(mode="json")) == v2


def test_the_files_are_where_the_sets_say() -> None:
    root = Path(CURATED_DIR) / "coverage_policies"

    assert sorted(p.name for p in (root / "v1").glob("POL-*.md")) == sorted(
        p.name for p in (root / "v2").glob("POL-*.md")
    )
    assert not list(root.glob("POL-*.md"))  # v1 moved byte-identical into v1/ (D-POL-2)
