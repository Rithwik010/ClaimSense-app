"""Application settings, read from the environment or `.env` (INSTRUCTIONS.md §8.12)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
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
    # Coverage policy set of the pipeline (D-POL-2): v2 uses the exact lookup (D-RAG-2); v1 is
    # kept to reproduce model v1.
    policy_set: Literal["v1", "v2"] = "v2"
    # Policy set v1 only: top 5 within the covering policy (P3.3); v2 has no cap (D-RAG-1).
    rag_top_k: int = Field(default=5, ge=1)
    rag_min_score: float = Field(
        default=0.0, ge=-1.0, le=1.0
    )  # cosine; not needed with the code filter
    extraction_confidence_min: float = Field(default=0.85, ge=0.0, le=1.0)
    review_high_dollar_cents: int = Field(default=100_000, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
