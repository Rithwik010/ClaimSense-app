"""Evaluation results for the UI's metrics page (P5.5): model v1 and model v2 on the v2 test set
(training/evaluate/compare_v2.py) and the OCR field accuracy on held-out scans
(scripts/verify/ocr_accuracy.py), each with its target. Read from the reports those scripts write
under data/generated/eval/; a report not yet written is left out."""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import require
from app.auth import Role

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
MACRO_F1_TARGET = 0.90  # P4.4
OCR_TARGET = 0.90  # P5.1


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


class Evaluation(BaseModel):
    models: list[ModelRow]
    macro_f1_target: float
    ocr: OcrRow | None
    ocr_target: float
    v2_errors: V2Errors | None = None


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
    return Evaluation(
        models=models,
        macro_f1_target=MACRO_F1_TARGET,
        ocr=ocr,
        ocr_target=OCR_TARGET,
        v2_errors=errors,
    )


RESULTS = EVAL / "results.json"  # scripts/verify/results_report.py (P6.1)


@router.get("/results")
def results() -> dict[str, Any]:
    """The P6.1 results (rules, calculator, extraction, models, latency per stage) as the results
    script last wrote them; 404 until it has run."""
    if not RESULTS.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no results yet: run make results")
    return json.loads(RESULTS.read_text())
