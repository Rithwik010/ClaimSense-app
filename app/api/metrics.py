"""Admin pages (D-AUTH-1, admin only). Evaluation results for the metrics page (P5.5): models v1, v2
and E4B on the v2 test set (training/evaluate/compare_v2.py), model v3 against v2 on four sets
(scripts/verify/results_v3.py: each with the machine it was measured on) and the OCR field
accuracy on held-out scans (scripts/verify/ocr_accuracy.py), each with its target, read from the
reports those scripts write under data/generated/eval/ (a report not yet written is left out); the
P6.1 results
file; the overview counts of the claims on file (demo data); and the versions the decision
records name, with the ones the API is set to use."""

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_session, require
from app.auth import Role
from app.calculator import CALCULATOR_VERSION
from app.core.settings import Settings, get_settings
from app.db.models import AuditEvent, Claim, DecisionRecordRow
from app.domain.contracts import ReviewTier
from app.rules import RULES_VERSION
from app.workflow.review import review_queue

# Admin only (D-AUTH-1).
router = APIRouter(
    prefix="/v1/metrics", tags=["metrics"], dependencies=[Depends(require(Role.ADMIN))]
)
EVAL = Path(__file__).resolve().parents[2] / "data" / "generated" / "eval"
MODEL_REPORTS = (
    EVAL / "v2" / "v2data-model-v1.json",
    EVAL / "v2" / "v2data-model-v2.json",
    EVAL / "v2" / "v2data-model-e4b.json",  # the E4B side experiment, once evaluated
)
OCR_REPORT = EVAL / "ocr" / "heldout_summary.json"
ERRORS_REPORT = EVAL / "v2" / "v2-errors.json"  # scripts/verify/v2_errors.py
V3_REPORT = EVAL / "v3study" / "results-v3.json"  # scripts/verify/results_v3.py
MACRO_F1_TARGET = 0.90  # P4.4
OCR_TARGET = 0.90  # P5.1


class ClassScores(BaseModel):
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    support: int | None = None


class ModelRow(BaseModel):
    model: str
    prompt: str
    records: int
    valid_output: float
    line_accuracy: float
    macro_f1: float
    criterion_accuracy: float
    deny_precision: float
    median_ms_per_claim: int
    p95_ms_per_claim: int
    per_class: dict[str, ClassScores]  # APPROVE, PEND, DENY


class OcrRow(BaseModel):
    claims: int
    fields: int
    field_accuracy: float
    blank_read_as_blank: float


class ErrorDirection(BaseModel):
    gold: str
    predicted: str
    lines: int


class ErrorPolicy(BaseModel):
    policy_id: str
    lines: int
    wrong: int


class V2Errors(BaseModel):
    """Where model v2 goes wrong on the v2 test set (scripts/verify/v2_errors.py)."""

    lines: int
    wrong_lines: int
    directions: list[ErrorDirection]
    policies: list[ErrorPolicy]  # the five with the most wrong lines
    quick_claims: int
    quick_claims_with_wrong_line: int


class V3Scores(BaseModel):
    macro_f1: float
    valid_output: float
    line_accuracy: float
    deny_precision: float
    wrong_approvals: int


class V3Set(BaseModel):
    """Model v3 against v2 on one set, both measured on the same machine (D-V3-34)."""

    title: str
    notes: str
    claims: int
    machine: str
    v2: V3Scores
    v3: V3Scores
    macro_f1_difference_ci95: list[float] | None = None


class Evaluation(BaseModel):
    models: list[ModelRow]
    macro_f1_target: float
    ocr: OcrRow | None
    ocr_target: float
    v2_errors: V2Errors | None = None
    v3_sets: list[V3Set] = []


def _model_row(report: dict[str, Any]) -> ModelRow:
    metrics = report["metrics"]
    return ModelRow(
        model=report["model"],
        prompt=report["prompt"],
        records=metrics["records"],
        valid_output=metrics["valid_output_rate"],
        line_accuracy=metrics["decisions"]["accuracy"],
        macro_f1=metrics["decisions"]["macro_f1"],
        criterion_accuracy=metrics["criterion_status_accuracy"],
        deny_precision=metrics["decisions"]["per_class"]["DENY"]["precision"],
        median_ms_per_claim=metrics["latency_ms"]["p50"],
        p95_ms_per_claim=metrics["latency_ms"]["p95"],
        per_class={
            name: ClassScores.model_validate(scores)
            for name, scores in metrics["decisions"]["per_class"].items()
        },
    )


@router.get("/evaluation")
def evaluation() -> Evaluation:
    models = [_model_row(json.loads(p.read_text())) for p in MODEL_REPORTS if p.exists()]
    ocr = None
    if OCR_REPORT.exists():
        summary = json.loads(OCR_REPORT.read_text())
        ocr = OcrRow(
            claims=summary["claims"],
            fields=summary["fields_written"],
            field_accuracy=summary["field_accuracy"],
            blank_read_as_blank=summary["blank_read_as_blank"],
        )
    errors = None
    if ERRORS_REPORT.exists():
        found = json.loads(ERRORS_REPORT.read_text())
        quick = found["tiers"].get("QUICK", {"claims": 0, "with_wrong_line": 0})
        errors = V2Errors(
            lines=found["lines"],
            wrong_lines=found["wrong_lines"],
            directions=[
                ErrorDirection(gold=k.split("->")[0], predicted=k.split("->")[1], lines=v)
                for k, v in found["direction"].items()
            ],
            policies=[
                ErrorPolicy(policy_id=p, lines=v["lines"], wrong=v["wrong"])
                for p, v in list(found["by_policy"].items())[:5]
            ],
            quick_claims=quick["claims"],
            quick_claims_with_wrong_line=quick["with_wrong_line"],
        )
    v3_sets = []
    if V3_REPORT.exists():
        v3_sets = [V3Set.model_validate(s) for s in json.loads(V3_REPORT.read_text())["sets"]]
    return Evaluation(
        models=models,
        macro_f1_target=MACRO_F1_TARGET,
        ocr=ocr,
        ocr_target=OCR_TARGET,
        v2_errors=errors,
        v3_sets=v3_sets,
    )


RESULTS = EVAL / "results.json"  # scripts/verify/results_report.py (P6.1)


@router.get("/results")
def results() -> dict[str, Any]:
    """The P6.1 results (rules, calculator, extraction, models, latency per stage) as the results
    script last wrote them; 404 until it has run."""
    if not RESULTS.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no results yet: run make results")
    return json.loads(RESULTS.read_text())


class Overview(BaseModel):
    """Counts over the claims on file: demo data, not results (D-AUTH-1 admin home)."""

    claims: int
    by_status: dict[str, int]  # every ClaimStatus on file
    final_outcomes: dict[str, int]  # FINAL_* and the rule outcomes
    queue_by_tier: dict[str, int]  # QUICK, STANDARD, FULL
    decided_by_rules: int  # REJECTED, DENIED_BY_RULE, PENDED_BY_RULE
    reviewed_accepted: int
    reviewed_overridden: int


RULE_STATUSES = ("REJECTED", "DENIED_BY_RULE", "PENDED_BY_RULE")


@router.get("/overview")
def overview(session: Annotated[Session, Depends(get_session)]) -> Overview:
    by_status = dict(
        session.execute(select(Claim.status, func.count()).group_by(Claim.status)).tuples().all()
    )
    queue = {tier.value: 0 for tier in ReviewTier}
    for item in review_queue(session):
        queue[item.review_tier.value] += 1
    reviews = dict(
        session.execute(
            select(AuditEvent.event_type, func.count())
            .where(AuditEvent.event_type.in_(("REVIEW_ACCEPTED", "REVIEW_OVERRIDDEN")))
            .group_by(AuditEvent.event_type)
        )
        .tuples()
        .all()
    )
    return Overview(
        claims=sum(by_status.values()),
        by_status=by_status,
        final_outcomes={
            s: n for s, n in by_status.items() if s.startswith("FINAL_") or s in RULE_STATUSES
        },
        queue_by_tier=queue,
        decided_by_rules=sum(by_status.get(s, 0) for s in RULE_STATUSES),
        reviewed_accepted=reviews.get("REVIEW_ACCEPTED", 0),
        reviewed_overridden=reviews.get("REVIEW_OVERRIDDEN", 0),
    )


class VersionSet(BaseModel):
    rules_version: str
    model_name: str | None
    prompt_version: str | None
    policy_versions: list[str]  # <policy set>@<effective date> values (D-POL-2)
    records: int
    latest: datetime


class SystemVersions(BaseModel):
    """What the decision records say was used, and what the API is set to use now."""

    configured: dict[str, str]
    in_records: list[VersionSet]  # one per distinct set, the most recent first


@router.get("/system")
def system(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SystemVersions:
    sets: dict[tuple, dict[str, Any]] = {}
    for record, created in session.execute(
        select(DecisionRecordRow.record, DecisionRecordRow.created_at)
    ).tuples():
        versions = record.get("versions") or {}
        policies = sorted(set((versions.get("policy_versions") or {}).values()))
        key = (
            versions.get("rules_version"),
            versions.get("model_name"),
            versions.get("prompt_version"),
            tuple(policies),
        )
        found = sets.setdefault(key, {"records": 0, "latest": created})
        found["records"] += 1
        found["latest"] = max(found["latest"], created)
    return SystemVersions(
        configured={
            "model": settings.model_name,
            "prompt": settings.prompt_version,
            "policy_set": settings.policy_set,
            "rules": RULES_VERSION,
            "calculator": CALCULATOR_VERSION,
        },
        in_records=sorted(
            (
                VersionSet(
                    rules_version=key[0] or "",
                    model_name=key[1],
                    prompt_version=key[2],
                    policy_versions=list(key[3]),
                    records=found["records"],
                    latest=found["latest"],
                )
                for key, found in sets.items()
            ),
            key=lambda v: v.latest,
            reverse=True,
        ),
    )
