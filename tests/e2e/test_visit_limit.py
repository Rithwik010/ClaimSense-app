"""R21, the yearly visit limit (D-RULE-10, D-CARC-3), through the API on a test database: the
member's visit one below the plan's limit is approved and finalized, finalization counts it
(D-REV-8), and the member's next therapy claim is denied by the rule before the model, with group
PR, CARC 119 and RARC N640 and its plain-language reason.

Built on golden case E2E-22 (two therapy lines on one date: line 1 approved, line 2 denied by the
MUE edit), which is not changed: the test adds the visits used and a second claim of its own."""

import copy
from datetime import date

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.curated import load_curated
from app.db.models import VisitUsage
from tests.e2e.support import E2E_CASES, StubModel, process_case, record_of

THERAPY = "REHAB_THERAPY"


def visits_used(engine: Engine, member_id: str) -> int:
    with Session(engine) as session:
        row = session.get(VisitUsage, (member_id, date(2026, 1, 1), THERAPY))
        return row.visits_used if row else 0


def test_the_visit_after_the_limit_is_denied_by_the_rule_with_pr_119(
    api, load_case_reference, engine: Engine
) -> None:  # noqa: ANN001
    case = copy.deepcopy(E2E_CASES["E2E-22"])
    claim = case["given"]["claim"]
    member = claim["member_id"]
    plan = case["given"]["reference_additions"]["members"][0]["plan_id"]
    limit = load_curated().benefit(plan, THERAPY).visit_limit
    assert limit is not None
    case["given"]["reference_additions"]["visit_usage"] = [
        {
            "member_id": member,
            "period_start": "2026-01-01",
            "benefit_category": THERAPY,
            "visits_used": limit - 1,
        }
    ]
    load_case_reference(case)

    # The last visit of the year: rules pass it to the model, the review finalizes it.
    client = process_case(api, load_case_reference, "E2E-22")
    first = record_of(client, claim["claim_id"])
    assert [(d.line_no, d.decision.value, d.reason_codes) for d in first.line_decisions] == [
        (1, "APPROVE", []),
        (2, "DENY", ["DN_MUE_EXCEEDED"]),
    ]
    review = client.post(
        f"/v1/claims/{claim['claim_id']}/review", json=case["given"]["review_action"]
    )
    assert review.status_code == 200, review.text
    assert visits_used(engine, member) == limit

    # The next visit: denied by R21 on both lines, so the claim never reaches the model.
    model = StubModel("unused")
    later = api(model)
    following = copy.deepcopy(claim)
    following["claim_id"] = "CLM-E2E-22-NEXT"
    following["received_date"] = "2026-10-30"
    for line in following["service_lines"]:
        line["date_of_service"] = "2026-10-23"
    assert later.post("/v1/claims/intake", json=following).status_code == 201
    processed = later.post("/v1/claims/CLM-E2E-22-NEXT/process")
    assert processed.status_code == 200, processed.text

    view = later.get("/v1/claims/CLM-E2E-22-NEXT").json()
    record = record_of(later, "CLM-E2E-22-NEXT")
    assert view["status"] == "DENIED_BY_RULE"
    assert model.prompts == []
    assert [(o.line_no, o.outcome, o.reason_codes) for o in record.rules_outcome.line_outcomes] == [
        (1, "DENY", ["DN_VISIT_LIMIT"]),
        (2, "DENY", ["DN_MUE_EXCEEDED", "DN_VISIT_LIMIT"]),
    ]
    [r21] = [r for r in record.rules_outcome.rule_results if r.rule_id == "R21" and r.line_no == 1]
    assert f"would be visit {limit + 1}" in r21.detail
    visit_codes = [
        (a["line_no"], a["group_code"], [(c["kind"], c["code"]) for c in a["codes"]])
        for a in view["adjustments"]
        if a["reason_code"] == "DN_VISIT_LIMIT"
    ]
    assert visit_codes == [
        (1, "PR", [("CARC", "119"), ("RARC", "N640")]),
        (2, "PR", [("CARC", "119"), ("RARC", "N640")]),
    ]
    text = later.get("/v1/claims/CLM-E2E-22-NEXT/explanation?format=text").text
    assert "the plan's yearly visit limit for this service is used up" in text
    assert visits_used(engine, member) == limit  # a rule denial uses no visit
