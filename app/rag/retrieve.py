"""Coverage-criteria retrieval (INSTRUCTIONS.md §8.4).

For one claim line: filter by plan ID (or ALL) and effective date <= date of service, then take the
top-k criteria by similarity that reach a minimum score. The pipeline and the dataset generator use
this same code, so the model is trained on the criteria it will be shown in live use.
"""

from collections.abc import Collection, Mapping
from datetime import date
from typing import Protocol

from qdrant_client import QdrantClient, models

from app.domain.contracts import IntakeClaim, RetrievedCriterion
from app.rag.embedding import Embedder
from app.rag.knowledge import COVERAGE_COLLECTION, day_number

QUERY_FORMAT = "procedure+diagnoses+notes-v1"


class Retriever(Protocol):
    def retrieve(
        self, query: str, plan_id: str, day: date, exclude_policies: Collection[str] = ()
    ) -> list[RetrievedCriterion]: ...


class RetrievalUnavailable(RuntimeError):
    """Qdrant or the embedding model cannot be used; the claim can be processed later."""


def line_query(
    claim: IntakeClaim,
    line_no: int,
    procedure_descriptions: Mapping[str, str],
    icd10_descriptions: Mapping[str, str],
) -> str:
    """The text searched for one line: what was done, why, and the clinical notes."""
    line = claim.service_lines[line_no - 1]
    diagnoses = [claim.diagnoses[ord(p) - ord("A")] for p in line.diagnosis_pointers]
    parts = [
        procedure_descriptions.get(line.procedure_code, line.procedure_code),
        "; ".join(icd10_descriptions.get(code, code) for code in diagnoses),
        claim.clinical_notes.strip(),
    ]
    return ". ".join(part for part in parts if part)


class CriteriaRetriever:
    def __init__(
        self,
        client: QdrantClient,
        embedder: Embedder,
        top_k: int,
        min_score: float,
        collection: str = COVERAGE_COLLECTION,
    ) -> None:
        self.client = client
        self.embedder = embedder
        self.top_k = top_k
        self.min_score = min_score
        self.collection = collection

    @property
    def settings_label(self) -> str:
        return f"{QUERY_FORMAT}; top {self.top_k}; min score {self.min_score}; {self.embedder.name}"

    def retrieve(
        self,
        query: str,
        plan_id: str,
        day: date,
        exclude_policies: Collection[str] = (),
    ) -> list[RetrievedCriterion]:
        """`exclude_policies` is for the dataset generator only: training splits never see the
        test-only policies, not even as distractors."""
        must_not = (
            [
                models.FieldCondition(
                    key="policy_id", match=models.MatchAny(any=sorted(exclude_policies))
                )
            ]
            if exclude_policies
            else None
        )
        query_filter = models.Filter(
            must=[
                models.FieldCondition(key="plan_ids", match=models.MatchAny(any=[plan_id, "ALL"])),
                models.FieldCondition(key="effective_day", range=models.Range(lte=day_number(day))),
            ],
            must_not=must_not,
        )
        try:
            vector = self.embedder.embed_query(query)
            points = self.client.query_points(
                self.collection,
                query=vector,
                query_filter=query_filter,
                limit=self.top_k,
                score_threshold=self.min_score,
                search_params=models.SearchParams(exact=True),
                with_payload=True,
            ).points
        except RetrievalUnavailable:
            raise
        except Exception as exc:  # connection errors, missing collection, missing model files
            raise RetrievalUnavailable(f"retrieval unavailable ({type(exc).__name__})") from exc
        ranked = sorted(points, key=lambda p: (-p.score, p.payload["criterion_id"]))
        return [
            RetrievedCriterion(
                criterion_id=p.payload["criterion_id"],
                policy_id=p.payload["policy_id"],
                policy_title=p.payload["policy_title"],
                text=p.payload["text"],
                source=p.payload["source"],
                effective_date=date.fromisoformat(p.payload["effective_date"]),
            )
            for p in ranked
        ]
