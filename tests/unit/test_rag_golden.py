"""P3.3 acceptance: retrieval with the real embedding model reaches recall@3 >= 0.85 on the golden
queries, and returns nothing for the "no relevant policy" queries. Skipped until the model files are
cached (`data/generated/models/fastembed`); in-memory Qdrant, so no server is needed."""

import pytest
from qdrant_client import QdrantClient

from app.core.settings import get_settings
from app.rag.embedding import FastEmbedder, model_files_present
from app.rag.knowledge import build_coverage_collection
from app.rag.retrieve import CriteriaRetriever
from training.evaluate.rag import load_queries

SETTINGS = get_settings()

pytestmark = pytest.mark.skipif(
    not model_files_present(SETTINGS.embedding_cache_dir), reason="embedding model not cached"
)


def test_golden_queries_meet_the_recall_target() -> None:
    from training.evaluate.rag import evaluate

    embedder = FastEmbedder(SETTINGS.embedding_model, SETTINGS.embedding_cache_dir)
    client = QdrantClient(":memory:")
    build_coverage_collection(client, embedder)
    retriever = CriteriaRetriever(
        client, embedder, top_k=SETTINGS.rag_top_k, min_score=SETTINGS.rag_min_score
    )

    report = evaluate(retriever, load_queries())

    assert report["passed"], report
