"""The embedding model files for CI (D-RAG-2): fetch them into the cache directory when missing and
check the ONNX model's SHA-256, so the retrieval tests run on exactly the model the knowledge base
was built with, and fail (CLAIMSENSE_REQUIRE_EMBEDDING=1) instead of skipping when it is missing.

    uv run python -m scripts.verify.embedding_model check   # exit 1 unless the pinned file is there
    uv run python -m scripts.verify.embedding_model fetch   # download if needed (fastembed), check
"""

import argparse
import hashlib
from pathlib import Path

from app.core.settings import get_settings
from app.rag.embedding import FastEmbedder

# fastembed's files for BAAI/bge-small-en-v1.5 (Hugging Face qdrant/bge-small-en-v1.5-onnx-q,
# snapshot 52398278842ec682c6f32300af41344b1c0b0bb2), as cached for model v1's knowledge base.
MODEL_FILE = "model_optimized.onnx"
MODEL_SHA256 = "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431"


def model_paths(cache_dir: Path) -> list[Path]:
    return sorted(cache_dir.rglob(MODEL_FILE))


def check(cache_dir: Path) -> str:
    """'' when a cached model file has the pinned SHA-256, else the problem."""
    paths = model_paths(cache_dir)
    if not paths:
        return f"no {MODEL_FILE} under {cache_dir}"
    digests = {hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if digests != {MODEL_SHA256}:
        return f"{MODEL_FILE} SHA-256 {sorted(digests)} != pinned {MODEL_SHA256}"
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("check", "fetch"))
    step = parser.parse_args().step
    settings = get_settings()
    cache_dir = settings.embedding_cache_dir
    if step == "fetch" and check(cache_dir):
        FastEmbedder(settings.embedding_model, cache_dir).embed_query("warm up")
    problem = check(cache_dir)
    if problem:
        raise SystemExit(problem)
    print(f"{settings.embedding_model}: {MODEL_FILE} SHA-256 matches ({MODEL_SHA256[:12]})")


if __name__ == "__main__":
    main()
