"""Text embeddings for the knowledge base (fastembed, local ONNX model; no external API)."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def model_files_present(cache_dir: Path) -> bool:
    """True when a complete ONNX model file is cached (a download may have stopped halfway)."""
    return any(path.stat().st_size > 1_000_000 for path in cache_dir.rglob("*.onnx"))


class EmbeddingUnavailable(RuntimeError):
    """The embedding model files are not available locally."""


class FastEmbedder:
    """`fastembed` with the model files cached under `cache_dir`. Loaded on first use."""

    def __init__(self, name: str, cache_dir: Path, dim: int = EMBEDDING_DIM) -> None:
        self.name = name
        self.dim = dim
        self._cache_dir = cache_dir
        self._model = None

    def _load(self):  # noqa: ANN202
        if self._model is None:
            from fastembed import TextEmbedding

            try:
                self._model = TextEmbedding(self.name, cache_dir=str(self._cache_dir))
            except Exception as exc:  # fastembed raises several error types for missing files
                raise EmbeddingUnavailable(
                    f"embedding model {self.name} not available in {self._cache_dir} "
                    f"({type(exc).__name__})"
                ) from exc
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._load().embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._load().query_embed([text]))).tolist()
