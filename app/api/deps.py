"""Request dependencies. Tests override `get_engine`, `get_decision_model` and `get_retriever`."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.db.session import get_engine
from app.ml.client import DecisionModel, OllamaDecisionModel
from app.rag.retrieve import CriteriaRetriever, Retriever


def get_session(engine: Annotated[Engine, Depends(get_engine)]) -> Iterator[Session]:
    """One session per request; anything not committed is rolled back when it closes."""
    with Session(engine) as session:
        yield session


def get_decision_model(settings: Annotated[Settings, Depends(get_settings)]) -> DecisionModel:
    return OllamaDecisionModel(settings.ollama_url, settings.model_name)


@lru_cache
def get_retriever() -> Retriever:
    """One retriever per process: the embedding model loads on the first query."""
    from qdrant_client import QdrantClient

    from app.rag.embedding import FastEmbedder

    settings = get_settings()
    return CriteriaRetriever(
        QdrantClient(url=settings.qdrant_url),
        FastEmbedder(settings.embedding_model, settings.embedding_cache_dir),
        top_k=settings.rag_top_k,
        min_score=settings.rag_min_score,
    )
