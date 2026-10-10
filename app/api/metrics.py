"""Evaluation results for the UI's metrics page (P5.5): model v1 and model v2 on the v2 test set
(training/evaluate/compare_v2.py) and the OCR field accuracy on held-out scans
(scripts/verify/ocr_accuracy.py), each with its target. Read from the reports those scripts write
under data/generated/eval/; a report not yet written is left out."""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1/metrics", tags=["metrics"])
EVAL = Path(__file__).resolve().parents[2] / "data" / "generated" / "eval"
MODEL_REPORTS = (EVAL / "v2" / "v2data-model-v1.json", EVAL / "v2" / "v2data-model-v2.json")
OCR_REPORT = EVAL / "ocr" / "heldout_summary.json"
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


class Evaluation(BaseModel):
    models: list[ModelRow]
    macro_f1_target: float
    ocr: OcrRow | None
    ocr_target: float


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
    return Evaluation(
        models=models, macro_f1_target=MACRO_F1_TARGET, ocr=ocr, ocr_target=OCR_TARGET
    )
