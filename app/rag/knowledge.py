"""Knowledge-base ingestion (INSTRUCTIONS.md §9.3): one coverage policy collection per policy set
(D-POL-2), `coverage_policies_v1` and `coverage_policies_v2`, one point per criterion, with the
payload metadata the retrieval filters use. A v2 point also holds the criterion's type, group, own
codes and policy-file order (D-POL-3, D-RAG-2).

Only the collection of the pipeline's policy set feeds the model prompt. The explanation collections
(`plan_documents`, `code_reference`, `carc_rarc`) are added with the explanations (P5.4).

    uv run python -m app.rag.knowledge      # (re)build both collections in Qdrant
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from qdrant_client import QdrantClient, models

from app.db.curated import POLICY_SETS, CuratedData, load_curated
from app.rag.embedding import Embedder

COVERAGE_COLLECTIONS = {policy_set: f"coverage_policies_{policy_set}" for policy_set in POLICY_SETS}
COVERAGE_COLLECTION = COVERAGE_COLLECTIONS["v1"]  # semantic search, model v1 (D-RAG-2)
CHUNK_FORMAT = "policy-title+criterion-v1"
CHUNK_FORMAT_V2 = "criterion+type+group+codes+order-v2; exact lookup"
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
    """One chunk per criterion of the curated policy set, in policy-file order."""
    collection = COVERAGE_COLLECTIONS[curated.policy_set]
    chunks = []
    for policy in curated.policies.values():
        for criterion in policy.criteria:
            payload = {
                "collection": collection,
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
            }
            if curated.policy_set == "v2":
                payload |= {
                    "criterion_type": criterion.criterion_type,
                    "group": criterion.group,
                    "criterion_codes": list(policy.criterion_codes(criterion)),
                    "order": len(chunks),
                }
            chunks.append(
                Chunk(
                    point_id=str(uuid.uuid5(uuid.NAMESPACE_URL, criterion.criterion_id)),
                    text=f"{policy.title}. {criterion.text}",
                    payload=payload,
                )
            )
    return chunks


def knowledge_version(chunks: list[Chunk], embedder_name: str) -> str:
    """Policy set v1: changes whenever a criterion text, the chunk format or the embedding model
    changes (36cfc77305a5 for model v1)."""
    digest = hashlib.sha256(f"{CHUNK_FORMAT}|{embedder_name}".encode())
    for chunk in sorted(chunks, key=lambda c: c.point_id):
        digest.update(f"|{chunk.point_id}|{chunk.text}|{chunk.payload['source']}".encode())
    return digest.hexdigest()[:12]


def knowledge_version_v2(chunks: list[Chunk]) -> str:
    """Policy set v2: changes whenever anything the exact lookup returns or filters on changes
    (text, source, type, group, codes, plans, date, order). The embedding model is not part of it:
    the lookup uses no vectors."""
    digest = hashlib.sha256(CHUNK_FORMAT_V2.encode())
    keys = ("text", "source", "criterion_type", "group", "criterion_codes", "plan_ids")
    for chunk in chunks:
        values = [chunk.payload[k] for k in keys]
        values += [chunk.payload["effective_date"], chunk.payload["order"]]
        digest.update(f"|{chunk.point_id}|{values}".encode())
    return digest.hexdigest()[:12]


@lru_cache
def curated_knowledge_version(policy_set: str, embedder_name: str) -> str:
    """The knowledge version of a policy set's curated files (what its collection is built from)."""
    chunks = criterion_chunks(load_curated(policy_set))
    return (
        knowledge_version_v2(chunks)
        if policy_set == "v2"
        else knowledge_version(chunks, embedder_name)
    )


def build_coverage_collection(
    client: QdrantClient, embedder: Embedder, curated: CuratedData | None = None
) -> tuple[int, str]:
    """Recreate the curated policy set's collection (v1 by default). Returns (points, knowledge
    version)."""
    curated = curated or load_curated()
    collection = COVERAGE_COLLECTIONS[curated.policy_set]
    chunks = criterion_chunks(curated)
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection,
        vectors_config=models.VectorParams(size=embedder.dim, distance=models.Distance.COSINE),
    )
    fields = [
        ("plan_ids", models.PayloadSchemaType.KEYWORD),
        ("policy_id", models.PayloadSchemaType.KEYWORD),
        ("procedure_codes", models.PayloadSchemaType.KEYWORD),
        ("effective_day", models.PayloadSchemaType.INTEGER),
    ]
    if curated.policy_set == "v2":
        fields.append(("criterion_codes", models.PayloadSchemaType.KEYWORD))
    for field, schema in fields:
        client.create_payload_index(collection, field, field_schema=schema)
    client.upsert(
        collection,
        points=[
            models.PointStruct(id=chunk.point_id, vector=vector, payload=chunk.payload)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
        wait=True,
    )
    version = (
        knowledge_version_v2(chunks)
        if curated.policy_set == "v2"
        else knowledge_version(chunks, embedder.name)
    )
    return len(chunks), version


def main() -> None:
    from app.core.settings import get_settings
    from app.rag.embedding import FastEmbedder

    settings = get_settings()
    embedder = FastEmbedder(settings.embedding_model, settings.embedding_cache_dir)
    client = QdrantClient(url=settings.qdrant_url)
    for policy_set in POLICY_SETS:
        count, version = build_coverage_collection(client, embedder, load_curated(policy_set))
        print(f"{COVERAGE_COLLECTIONS[policy_set]}: {count} criteria, knowledge version {version}")


if __name__ == "__main__":
    main()
