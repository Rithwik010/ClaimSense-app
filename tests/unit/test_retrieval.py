"""Knowledge base and retrieval (P3.3) on in-memory Qdrant with a deterministic fake embedder.
The real embedding model is evaluated against the golden queries in test_rag_golden.py."""

import dataclasses
import hashlib
import math
import re
from datetime import date

import pytest
from qdrant_client import QdrantClient

from app.db.curated import load_curated
from app.domain.contracts import IntakeClaim
from app.rag.knowledge import COVERAGE_COLLECTION, build_coverage_collection, criterion_chunks
from app.rag.retrieve import CriteriaRetriever, RetrievalUnavailable, line_query
from tests.unit.test_contracts import claim_data, line

DAY = date(2026, 11, 2)


class FakeEmbedder:
    """Bag of words hashed into 64 dimensions: texts sharing words are similar."""

    name = "fake-bow-64"
    dim = 64

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for word in re.findall(r"[a-z]+", text.lower()):
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts):  # noqa: ANN001, ANN201
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def retriever(curated=None, top_k: int = 3, min_score: float = 0.0) -> CriteriaRetriever:  # noqa: ANN001
    client = QdrantClient(":memory:")
    build_coverage_collection(client, FakeEmbedder(), curated)
    return CriteriaRetriever(client, FakeEmbedder(), top_k=top_k, min_score=min_score)


def test_one_point_per_criterion_with_the_payload_metadata() -> None:
    curated = load_curated()
    client = QdrantClient(":memory:")

    count, version = build_coverage_collection(client, FakeEmbedder(), curated)
    _, again = build_coverage_collection(client, FakeEmbedder(), curated)  # rebuild replaces

    assert count == len(curated.criteria()) == client.count(COVERAGE_COLLECTION).count
    assert version == again
    payload = criterion_chunks(curated)[0].payload
    for key in ("collection", "policy_id", "criterion_id", "plan_ids", "effective_date", "source"):
        assert key in payload
    assert "license" in payload


def test_the_criterion_that_matches_the_query_ranks_first() -> None:
    curated = load_curated()
    target = curated.policies["POL-IMG-002"].criteria[2]  # plantar fasciitis

    found = retriever(curated).retrieve(f"Ultrasound. {target.text}", "PLN-PPO-GOLD", DAY)

    assert len(found) == 3
    assert found[0].criterion_id == target.criterion_id
    assert found[0].policy_title == "Ultrasound of the arms and legs (non-vascular)"
    assert found[0].source == target.source


def test_filters_run_before_the_similarity_search() -> None:
    curated = load_curated()
    hmo_only = dataclasses.replace(curated.policies["POL-IMG-002"], plan_ids=("PLN-HMO",))
    curated = dataclasses.replace(curated, policies={**curated.policies, "POL-IMG-002": hmo_only})
    query = curated.policies["POL-IMG-002"].criteria[2].text
    search = retriever(curated)

    gold = {c.policy_id for c in search.retrieve(query, "PLN-PPO-GOLD", DAY)}
    hmo = {c.policy_id for c in search.retrieve(query, "PLN-HMO", DAY)}
    before_policies = search.retrieve(query, "PLN-HMO", date(2025, 12, 31))

    assert "POL-IMG-002" not in gold and "POL-IMG-002" in hmo
    assert before_policies == []  # every policy starts 2026-01-01


def test_top_k_minimum_score_and_excluded_policies() -> None:
    query = load_curated().policies["POL-IMG-002"].criteria[2].text

    assert len(retriever(top_k=5).retrieve(query, "PLN-EPO", DAY)) == 5
    assert retriever(min_score=0.99).retrieve("unrelated words only", "PLN-EPO", DAY) == []
    kept = retriever().retrieve(query, "PLN-EPO", DAY, exclude_policies={"POL-IMG-002"})
    assert kept and "POL-IMG-002" not in {c.policy_id for c in kept}


def test_same_query_same_result() -> None:
    search = retriever()
    query = "Nerve conduction study for numbness in the hand"

    assert search.retrieve(query, "PLN-HMO", DAY) == search.retrieve(query, "PLN-HMO", DAY)


def test_missing_collection_is_retrieval_unavailable() -> None:
    search = CriteriaRetriever(QdrantClient(":memory:"), FakeEmbedder(), top_k=3, min_score=0.0)

    with pytest.raises(RetrievalUnavailable):
        search.retrieve("anything", "PLN-HMO", DAY)


def test_line_query_has_procedure_diagnoses_and_notes() -> None:
    claim = IntakeClaim.model_validate(
        claim_data(
            diagnoses=["M5416", "M5417"],
            service_lines=[line(procedure_code="62323", diagnosis_pointers=["B", "A"])],
            clinical_notes=" Pain for 8 weeks. ",
        )
    )

    query = line_query(
        claim,
        1,
        {"62323": "Epidural injection, lower back"},
        {"M5416": "Radiculopathy, lumbar region"},
    )

    assert query == "Epidural injection, lower back. M5417; Radiculopathy, lumbar region. " + (
        "Pain for 8 weeks."
    )
