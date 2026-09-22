"""Knowledge-base ingestion (INSTRUCTIONS.md §9.3): the `coverage_policies` collection, one point
per criterion, with the payload metadata the retrieval filters use.

Only `coverage_policies` feeds the model prompt. The explanation collections (`plan_documents`,
`code_reference`, `carc_rarc`) are added with the explanations (P5.4).

    uv run python -m app.rag.knowledge      # (re)build the collection in Qdrant
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date

from qdrant_client import QdrantClient, models

from app.db.curated import CuratedData, load_curated
from app.rag.embedding import Embedder

COVERAGE_COLLECTION = "coverage_policies"
CHUNK_FORMAT = "policy-title+criterion-v1"
LICENSE = "Criteria written by the team from CMS LCDs (public domain); no AMA CPT text"


@dataclass(frozen=True)
class Chunk:
    point_id: str
    text: str  # what is embedded
    payload: dict


def day_number(day: date) -> int:
    """Dates as YYYYMMDD integers, for Qdrant range filters."""
    return day.year * 10000 + day.month * 100 + day.day


def criterion_chunks(curated: CuratedData) -> list[Chunk]:
    chunks = []
    for policy in curated.policies.values():
        for criterion in policy.criteria:
            chunks.append(
                Chunk(
                    point_id=str(uuid.uuid5(uuid.NAMESPACE_URL, criterion.criterion_id)),
                    text=f"{policy.title}. {criterion.text}",
                    payload={
                        "collection": COVERAGE_COLLECTION,
                        "policy_id": policy.policy_id,
                        "policy_title": policy.title,
                        "criterion_id": criterion.criterion_id,
                        "text": criterion.text,
                        "plan_ids": list(policy.plan_ids),
                        "effective_date": policy.effective_date.isoformat(),
                        "effective_day": day_number(policy.effective_date),
                        "procedure_codes": list(policy.procedure_codes),
                        "source": criterion.source,
                        "license": LICENSE,
                    },
                )
            )
    return chunks


def knowledge_version(chunks: list[Chunk], embedder_name: str) -> str:
    """Changes whenever a criterion text, the chunk format or the embedding model changes."""
    digest = hashlib.sha256(f"{CHUNK_FORMAT}|{embedder_name}".encode())
    for chunk in sorted(chunks, key=lambda c: c.point_id):
        digest.update(f"|{chunk.point_id}|{chunk.text}|{chunk.payload['source']}".encode())
    return digest.hexdigest()[:12]


def build_coverage_collection(
    client: QdrantClient, embedder: Embedder, curated: CuratedData | None = None
) -> tuple[int, str]:
    """Recreate the collection from the curated policies. Returns (points, knowledge version)."""
    chunks = criterion_chunks(curated or load_curated())
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    if client.collection_exists(COVERAGE_COLLECTION):
        client.delete_collection(COVERAGE_COLLECTION)
    client.create_collection(
        COVERAGE_COLLECTION,
        vectors_config=models.VectorParams(size=embedder.dim, distance=models.Distance.COSINE),
    )
    for field, schema in (
        ("plan_ids", models.PayloadSchemaType.KEYWORD),
        ("policy_id", models.PayloadSchemaType.KEYWORD),
        ("procedure_codes", models.PayloadSchemaType.KEYWORD),
        ("effective_day", models.PayloadSchemaType.INTEGER),
    ):
        client.create_payload_index(COVERAGE_COLLECTION, field, field_schema=schema)
    client.upsert(
        COVERAGE_COLLECTION,
        points=[
            models.PointStruct(id=chunk.point_id, vector=vector, payload=chunk.payload)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
        wait=True,
    )
    return len(chunks), knowledge_version(chunks, embedder.name)


def main() -> None:
    from app.core.settings import get_settings
    from app.rag.embedding import FastEmbedder

    settings = get_settings()
    embedder = FastEmbedder(settings.embedding_model, settings.embedding_cache_dir)
    count, version = build_coverage_collection(QdrantClient(url=settings.qdrant_url), embedder)
    print(f"{COVERAGE_COLLECTION}: {count} criteria, knowledge version {version}")


if __name__ == "__main__":
    main()
