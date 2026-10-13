"""D-UI-6 on the nine demo claims (tests/fixtures/demo_records.json, written by
scripts/demo/snapshot_records.py after `make e2e-api`): the provider's explanation holds no rule
IDs or internal codes and its billing adds up to the cent (billed minus the reductions to the
allowed amount is the allowed amount; the allowed amount is what the plan, the patient and another
plan pay); the summary names the outcome the API showed."""

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from app.domain.contracts import ClaimStatus, DecisionRecord
from app.explain.provider import provider_explanation
from app.explain.reasons import REASONED_OUTCOMES, claim_outcome
from app.explain.summary import claim_summary

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "demo_records.json"
CLAIMS: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))
HIDDEN = re.compile(
    r"\bR(?:0[1-9]|1[0-9]|20)\b|\bDUP\b|\b(?:RJ|DN|PD|RV)_[A-Z0-9_]+\b"
    r"|\bMODEL_OUTPUT_INVALID\b|\bPOL-[A-Z]+-[0-9]{3}\.c[0-9]+\b"
)
TO_ALLOWED = ("allowed_amount", "out_of_network", "not_paid")
FINAL = {s for s in ClaimStatus if s not in (ClaimStatus.RECEIVED, ClaimStatus.AWAITING_REVIEW)}


def test_the_snapshot_holds_the_nine_demo_claims_on_every_path() -> None:
    assert [c["claim_id"] for c in CLAIMS] == [f"CLM-DEMO-{n:02d}" for n in range(1, 10)]
    outcomes = {c["outcome"] for c in CLAIMS}
    assert {"APPROVED", "PARTLY_APPROVED", "DENIED", "REJECTED", "IN_REVIEW"} <= outcomes


@pytest.mark.parametrize("claim", CLAIMS, ids=[c["claim_id"] for c in CLAIMS])
def test_the_provider_view_and_its_billing(claim: dict[str, Any]) -> None:
    status = ClaimStatus(claim["status"])
    record = DecisionRecord.model_validate(claim["record"])
    outcome = claim_outcome(status, record)
    assert outcome == claim["outcome"]
    summary = claim_summary(
        status, record, claim["received"], claim["field_confidences"], 0.85, 100_000
    )
    assert summary.outcome == outcome
    if status not in FINAL:
        return

    view = provider_explanation(
        outcome,
        record,
        claim["received"],
        claim["field_confidences"],
        0.85,
        claim["coinsurance_bps"],
    )

    assert HIDDEN.findall(json.dumps(asdict(view))) == []
    assert bool(view.why) == (outcome in REASONED_OUTCOMES)
    if view.billing is None:
        assert outcome not in ("APPROVED", "PARTLY_APPROVED") or record.amounts is None
        return
    for line in view.billing.lines:
        cut = sum(r.amount_cents or 0 for r in line.reductions if r.kind in TO_ALLOWED)
        assert line.billed_cents - cut == line.allowed_cents, line
        assert (
            line.plan_pays_cents + line.patient_pays_cents + line.other_plan_paid_cents
            == line.allowed_cents
        ), line
        assert all(r.amount_cents != 0 for r in line.reductions)
    t = view.billing.totals
    cut = sum(
        r.amount_cents or 0
        for line in view.billing.lines
        for r in line.reductions
        if r.kind in TO_ALLOWED
    )
    assert t.billed_cents - cut == t.allowed_cents
    assert t.plan_pays_cents + t.patient_pays_cents + t.other_plan_paid_cents == t.allowed_cents
