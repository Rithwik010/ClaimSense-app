"""Request dependencies. Tests override `get_engine` and `get_decision_model`."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.db.session import get_engine
from app.ml.client import DecisionModel, OllamaDecisionModel


def get_session(engine: Annotated[Engine, Depends(get_engine)]) -> Iterator[Session]:
    """One session per request; anything not committed is rolled back when it closes."""
    with Session(engine) as session:
        yield session


def get_decision_model(settings: Annotated[Settings, Depends(get_settings)]) -> DecisionModel:
    return OllamaDecisionModel(settings.ollama_url, settings.model_name)
