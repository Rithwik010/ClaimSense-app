"""Application settings, read from the environment or `.env` (INSTRUCTIONS.md §8.12)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://claimsense:claimsense@localhost:5432/claimsense"
    qdrant_url: str = "http://localhost:6333"
    ollama_url: str = "http://localhost:11434"
    model_name: str = "gemma4:e2b"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: Path = (
        Path(__file__).resolve().parents[2] / "data/generated/models/fastembed"
    )
    # The base model's tokenizer, local only, for counting a prompt before the model is called
    # (D-DOC-3; scripts/setup/fetch_tokenizer.py puts it here at setup).
    prompt_tokenizer: Path = (
        Path(__file__).resolve().parents[2]
        / "data/generated/models/gemma-4-E2B-it-d36bdd38/tokenizer.json"
    )
    # Coverage policy set of the pipeline (D-POL-2): v2 uses the exact lookup (D-RAG-2); v1 is
    # kept to reproduce model v1.
    policy_set: Literal["v1", "v2"] = "v2"
    # The prompt the model was trained on: decision_v2 for model v1, decision_v3 for model v2.
    prompt_version: Literal["decision_v2", "decision_v3"] = "decision_v3"
    # Policy set v1 only: top 5 within the covering policy (P3.3); v2 has no cap (D-RAG-1).
    rag_top_k: int = Field(default=5, ge=1)
    rag_min_score: float = Field(
        default=0.0, ge=-1.0, le=1.0
    )  # cosine; not needed with the code filter
    extraction_confidence_min: float = Field(default=0.85, ge=0.0, le=1.0)
    review_high_dollar_cents: int = Field(default=100_000, ge=0)
    # Logins (D-AUTH-1): signs the session tokens; `make demo-users` writes one to .env.
    secret_key: SecretStr | None = None
    # The production build of the web app, served by the API on the same origin (D-AUTH-1).
    web_dist: Path = Path(__file__).resolve().parents[2] / "frontend-web/dist"
    # /docs and /openapi.json are off: only login and /health are public (D-AUTH-1).
    api_docs: bool = False

    @field_validator("secret_key", mode="before")
    @classmethod
    def _unset_when_empty(cls, value: object) -> object:
        """An empty SECRET_KEY= (as in .env.example) is no key, never an empty signing key."""
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
