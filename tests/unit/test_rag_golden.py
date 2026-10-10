"""P3.3 acceptance: retrieval with the real embedding model reaches recall@3 >= 0.85 on the golden
queries and returns nothing for the "no relevant policy" queries; at the live top-k (5) it finds
every expected criterion. Skipped until the model files are cached; in-memory Qdrant."""

import os

import pytest
from qdrant_client import QdrantClient

from app.core.settings import get_settings
from app.rag.embedding import FastEmbedder, model_files_present
from app.rag.knowledge import build_coverage_collection
from app.rag.retrieve import CriteriaRetriever
from training.evaluate.rag import load_queries

SETTINGS = get_settings()

# CI caches the model and sets CLAIMSENSE_REQUIRE_EMBEDDING=1: a missing model fails (D-RAG-2).
pytestmark = pytest.mark.skipif(
    not model_files_present(SETTINGS.embedding_cache_dir)
    and os.environ.get("CLAIMSENSE_REQUIRE_EMBEDDING") != "1",
    reason="embedding model not cached",
)


def test_golden_queries_meet_the_recall_target() -> None:
    from training.evaluate.rag import evaluate

    embedder = FastEmbedder(SETTINGS.embedding_model, SETTINGS.embedding_cache_dir)
    client = QdrantClient(":memory:")
    build_coverage_collection(client, embedder)

    at_3 = evaluate(CriteriaRetriever(client, embedder, 3, SETTINGS.rag_min_score), load_queries())
    live = evaluate(
        CriteriaRetriever(client, embedder, SETTINGS.rag_top_k, SETTINGS.rag_min_score),
        load_queries(),
    )

    assert at_3["passed"], at_3
    assert live["recall_at_k"] == 1.0 and live["empty_failures"] == [], live
