"""Retrieval evaluation against the golden queries (P3.3 target: recall@3 >= 0.85).

For each query with expected criterion IDs: the share of them found in the top-k. Queries with no
expected IDs pass when nothing is returned after the filters and the minimum score. The searched
text is the procedure description followed by the query, the same shape as a claim line's query.

    uv run python -m training.evaluate.rag [--min-score 0.6]
"""

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from app.rag.retrieve import CriteriaRetriever

GOLDEN = Path(__file__).resolve().parents[2] / "tests" / "golden" / "rag" / "queries.json"
TARGET_RECALL = 0.85


def load_queries() -> list[dict[str, Any]]:
    return json.loads(GOLDEN.read_text())["queries"]


def evaluate(retriever: CriteriaRetriever, queries: list[dict[str, Any]]) -> dict[str, Any]:
    descriptions = load_curated().descriptions
    rows = []
    for query in queries:
        text = (
            f"{descriptions.get(query['procedure_code'], query['procedure_code'])}. "
            + (query["query"])
        )
        found = retriever.retrieve(
            text, query["plan_id"], date.fromisoformat(query["date_of_service"])
        )
        ids = [c.criterion_id for c in found]
        expected = query["expected_criterion_ids"]
        rows.append(
            {
                "query_id": query["query_id"],
                "expected": expected,
                "found": ids,
                "recall": (len(set(expected) & set(ids)) / len(expected)) if expected else None,
                "empty_ok": (not ids) if not expected else None,
            }
        )
    with_ids = [r["recall"] for r in rows if r["recall"] is not None]
    empty = [r["empty_ok"] for r in rows if r["empty_ok"] is not None]
    recall = sum(with_ids) / len(with_ids)
    return {
        "retriever": retriever.settings_label,
        "recall_at_k": round(recall, 4),
        "queries_with_ids": len(with_ids),
        "empty_queries_passed": f"{sum(empty)}/{len(empty)}",
        "passed": recall >= TARGET_RECALL and all(empty),
        "misses": [r for r in rows if (r["recall"] or 0) < 1 and r["recall"] is not None],
        "empty_failures": [r for r in rows if r["empty_ok"] is False],
    }


def main() -> None:
    from qdrant_client import QdrantClient

    from app.core.settings import get_settings
    from app.rag.embedding import FastEmbedder

    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-score", type=float, default=settings.rag_min_score)
    args = parser.parse_args()
    retriever = CriteriaRetriever(
        QdrantClient(url=settings.qdrant_url),
        FastEmbedder(settings.embedding_model, settings.embedding_cache_dir),
        top_k=settings.rag_top_k,
        min_score=args.min_score,
    )
    report = evaluate(retriever, load_queries())
    print(json.dumps({k: v for k, v in report.items() if k not in ("misses",)}, indent=2))
    for miss in report["misses"]:
        print(f"miss {miss['query_id']}: expected {miss['expected']} found {miss['found']}")


if __name__ == "__main__":
    main()
