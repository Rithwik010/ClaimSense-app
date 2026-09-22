"""Settings defaults and environment overrides (INSTRUCTIONS.md §8.12)."""

import pytest
from pydantic import ValidationError

from app.core.settings import Settings

ENV_NAMES = [
    "DATABASE_URL",
    "QDRANT_URL",
    "OLLAMA_URL",
    "MODEL_NAME",
    "EMBEDDING_MODEL",
    "RAG_TOP_K",
    "EXTRACTION_CONFIDENCE_MIN",
    "REVIEW_HIGH_DOLLAR_CENTS",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_spec() -> None:
    settings = Settings(_env_file=None)

    assert (
        settings.database_url
        == "postgresql+psycopg://claimsense:claimsense@localhost:5432/claimsense"
    )
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.model_name == "gemma4:e2b"
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.rag_top_k == 5  # the covering policy's criteria (P3.3)
    assert settings.extraction_confidence_min == 0.85
    assert settings.review_high_dollar_cents == 100_000


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_NAME", "claimsense-decision:v1")
    monkeypatch.setenv("RAG_TOP_K", "5")
    monkeypatch.setenv("REVIEW_HIGH_DOLLAR_CENTS", "250000")

    settings = Settings(_env_file=None)

    assert settings.model_name == "claimsense-decision:v1"
    assert settings.rag_top_k == 5
    assert settings.review_high_dollar_cents == 250_000


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("RAG_TOP_K", "0"),
        ("EXTRACTION_CONFIDENCE_MIN", "1.5"),
        ("REVIEW_HIGH_DOLLAR_CENTS", "-1"),
    ],
)
def test_out_of_range_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
