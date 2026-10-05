"""P2.5: every golden end-to-end claim (tests/golden/e2e/cases.json) through the pipeline as it
now runs: the full v1 rules engine on the database (P2.1, P2.5) and the full calculator (P2.4),
with the model stubbed by the case's answer. Expected values are the golden ones; never change one
to make a test pass (H12).

JSON claims go through POST /v1/claims/intake; scanned and digital-PDF claims through
`intake_claim_data` with their field confidences (file upload is P5.1). The cases record no
retrieval, so the stub retriever returns, for a line's procedure code, the curated criteria the
case's answer cites for that line (P5.6 rebuilds the cases for real retrieval). Each case runs on a
fresh database with its reference additions and claims on file.
"""

import json
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.db.curated import load_curated
from app.domain.contracts import DecisionRecord, RetrievedCriterion, SourceFormat
from app.workflow.pipeline import intake_claim_data
from tests.e2e.support import E2E_CASES, StubModel, StubRetriever

CASES = sorted(E2E_CASES.values(), key=lambda case: case["case_id"])


class CaseRetriever(StubRetriever):
    """For a line's procedure code, the curated criteria the case's answer cites for that line."""

    def __init__(self, case: dict[str, Any]) -> None:
        super().__init__()
        curated = load_curated()
        criteria = curated.criteria()
        codes = {
            line["line_no"]: line.get("procedure_code")
            for line in case["given"]["claim"]["service_lines"]
        }
        self.by_code: dict[str, list[RetrievedCriterion]] = {}
        for line in (case["given"].get("model_answer") or {}).get("lines", []):
            found = self.by_code.setdefault(codes.get(line["line_no"]), [])
            for cited in line.get("criteria", []):
                criterion_id = cited["criterion_id"]
                policy = curated.policies.get(criterion_id.split(".")[0])
                if criterion_id in criteria and policy is not None:
                    found.append(
                        RetrievedCriterion(
                            criterion_id=criterion_id,
                            policy_id=policy.policy_id,
                            policy_title=policy.title,
                            text=criteria[criterion_id].text,
                            source=criteria[criterion_id].source,
                            effective_date=policy.effective_date,
                        )
                    )

    def retrieve(self, query, plan_id, day, procedure_code=None, exclude_policies=()):  # noqa: ANN001, ANN201
        self.queries.append(query)
        return list(self.by_code.get(procedure_code, []))


def _failures(record: DecisionRecord) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": r.rule_id,
            "outcome": r.outcome.value,
            "reason_code": r.reason_code,
            "line_no": r.line_no,
        }
        for r in record.rules_outcome.rule_results
        if not r.passed
    ]


def differences(record: DecisionRecord, expected: dict[str, Any]) -> list[str]:
    """Every expected value the record does not match."""
    found = []

    def check(name: str, got: Any, want: Any) -> None:
        if got != want:
            found.append(f"{name}: got {got!r}, expected {want!r}")

    check("status", record.status.value, expected["status_after_processing"])
    rules = expected["rules"]
    check("rules claim_outcome", record.rules_outcome.claim_outcome.value, rules["claim_outcome"])
    if "failures" in rules:
        check("rules failures", _failures(record), rules["failures"])
    if "line_outcomes" in rules:
        check(
            "rules line_outcomes",
            [o.model_dump(mode="json") for o in record.rules_outcome.line_outcomes],
            rules["line_outcomes"],
        )
    if "flags" in rules:
        check("rules flags", record.rules_outcome.flags, rules["flags"])
    recommendation = expected["recommendation"]
    if recommendation is None:
        check("recommendation", record.line_decisions, [])
        return found
    check("output_valid", record.output_errors == [], recommendation["output_valid"])
    check(
        "line_decisions",
        [
            d.model_dump(mode="json", include={"line_no", "decision", "source", "reason_codes"})
            for d in record.line_decisions
        ],
        recommendation["line_decisions"],
    )
    check(
        "claim_decision",
        record.claim_decision.value if record.claim_decision else None,
        recommendation["claim_decision"],
    )
    check(
        "review_tier",
        record.review_tier.value if record.review_tier else None,
        recommendation["review_tier"],
    )
    check(
        "amounts",
        record.amounts.model_dump() if record.amounts else None,
        recommendation["amounts"],
    )
    return found


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_golden_end_to_end_case(api, load_case_reference, engine, case: dict[str, Any]) -> None:  # noqa: ANN001
    given = case["given"]
    load_case_reference(case)
    answer = given.get("model_answer")
    model = StubModel(json.dumps(answer) if answer is not None else "unused")
    client = api(model, CaseRetriever(case))
    claim = given["claim"]
    if given["source_format"] == "JSON":
        assert client.post("/v1/claims/intake", json=claim).status_code == 201
    else:
        with Session(engine) as session:
            intake_claim_data(
                session,
                claim,
                given["field_confidences"],
                SourceFormat(given["source_format"]),
                0.85,
            )

    response = client.post(f"/v1/claims/{claim['claim_id']}/process")

    assert response.status_code == 200, response.text
    record = DecisionRecord.model_validate(response.json())
    assert differences(record, case["expected"]) == [], record.output_errors
    if case["expected"]["recommendation"] is None:
        assert model.prompts == []  # a rule outcome never reaches the model
