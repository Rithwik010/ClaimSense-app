"""Request dependencies. Tests override `get_engine`, `get_decision_model` and `get_retriever`."""

from collections.abc import Callable, Iterator
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.db.session import get_engine
from app.ml.client import DecisionModel, OllamaDecisionModel
from app.rag.retrieve import CriteriaRetriever, ExactCriteriaRetriever, Retriever


def get_session(engine: Annotated[Engine, Depends(get_engine)]) -> Iterator[Session]:
    """One session per request; anything not committed is rolled back when it closes."""
    with Session(engine) as session:
        yield session


def get_decision_model(settings: Annotated[Settings, Depends(get_settings)]) -> DecisionModel:
    return OllamaDecisionModel(settings.ollama_url, settings.model_name)


@lru_cache
def get_retriever() -> Retriever:
    """One retriever per process, for the pipeline's policy set (D-POL-2): the v2 exact lookup, or
    v1's similarity ranking (its embedding model loads on the first query)."""
    from qdrant_client import QdrantClient

    from app.rag.embedding import FastEmbedder

    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    if settings.policy_set == "v2":
        return ExactCriteriaRetriever(client)
    return CriteriaRetriever(
        client,
        FastEmbedder(settings.embedding_model, settings.embedding_cache_dir),
        top_k=settings.rag_top_k,
        min_score=settings.rag_min_score,
    )


class Role(StrEnum):
    """The roles of the prototype's role header (§8.10); not authentication."""

    PROVIDER = "provider"
    REVIEWER = "reviewer"
    ADMIN = "admin"


def require_role(*allowed: Role) -> Callable[..., Role]:
    """A dependency admitting only the given roles, from the X-Role header (403 otherwise)."""
    names = ", ".join(role.value for role in allowed)

    def check(x_role: Annotated[str | None, Header()] = None) -> Role:
        if x_role not in {role.value for role in allowed}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"needs the X-Role header: {names}")
        return Role(x_role)

    return check


ReviewerRole = Annotated[Role, Depends(require_role(Role.REVIEWER, Role.ADMIN))]
