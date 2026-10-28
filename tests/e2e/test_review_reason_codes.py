"""D-REV-9: a reviewer's DENY or PEND override names a reason code from the allowed list, through
the API on a test database. The code is stored on the line and in the REVIEW_OVERRIDDEN audit
event and gives the line its CARC/RARC; the provider sees the plain reason and the codes, never the
reviewer's free-text note. Built on golden case E2E-14 (one office visit the model approves),
which is not changed: the tests send their own review actions."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.explain.reasons import reason_text
from tests.e2e.support import PROVIDER, audit, process_case

CLAIM = "CLM-E2E-14"
NOTE = "Private reviewer note: the visit repeats one from last week"


def override(**line: Any) -> dict[str, Any]:
    return {
        "claim_id": CLAIM,
        "reviewer_id": "reviewer-1",
        "action": "OVERRIDE",
        "line_overrides": [{"line_no": 1, "reason": NOTE, **line}],
        "reason": "Overall comment the provider must not see",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ({"decision": "DENY"}, "a DENY override needs a reason code"),
        ({"decision": "PEND"}, "a PEND override needs a reason code"),
        (
            {"decision": "DENY", "reason_code": "DN_LATE_FILING"},
            "DN_LATE_FILING is not a reason for a DENY override",
        ),
        (
            {"decision": "PEND", "reason_code": "DN_NOT_MEDICALLY_NECESSARY"},
            "DN_NOT_MEDICALLY_NECESSARY is not a reason for a PEND override",
        ),
    ],
)
def test_an_override_without_an_allowed_reason_code_is_refused(
    api, load_case_reference, line: dict[str, Any], message: str
) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    before = audit(client, CLAIM)

    response = client.post(f"/v1/claims/{CLAIM}/review", json=override(**line))

    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert client.get(f"/v1/claims/{CLAIM}").json()["status"] == "AWAITING_REVIEW"
    assert audit(client, CLAIM) == before


def test_a_deny_override_stores_and_audits_its_code_and_the_provider_sees_no_note(
    api, load_case_reference
) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")

    response = client.post(
        f"/v1/claims/{CLAIM}/review",
        json=override(decision="DENY", reason_code="DN_NOT_MEDICALLY_NECESSARY"),
    )

    assert response.status_code == 200, response.text
    line = response.json()["line_decisions"][0]
    assert (line["decision"], line["source"], line["reason_codes"]) == (
        "DENY",
        "REVIEWER",
        ["DN_NOT_MEDICALLY_NECESSARY"],
    )
    overridden = next(e for e in audit(client, CLAIM) if e["event_type"] == "REVIEW_OVERRIDDEN")
    [change] = overridden["payload"]["changes"]
    assert (change["reason_code"], change["reason"]) == ("DN_NOT_MEDICALLY_NECESSARY", NOTE)
    assert change["after"]["reason_codes"] == ["DN_NOT_MEDICALLY_NECESSARY"]

    # Staff see the note and the code.
    staff = client.get(f"/v1/claims/{CLAIM}/explanation", params={"format": "text"}).text
    assert NOTE in staff and "reason DN_NOT_MEDICALLY_NECESSARY" in staff

    # The provider sees the final decision (the reviewer's DENY, never the model's APPROVE) with its
    # plain reason and CARC 50, never the reviewer's ID, the note or the comment.
    view = client.get(f"/v1/claims/{CLAIM}", headers=PROVIDER)
    assert view.status_code == 200, view.text
    body = view.json()
    explanation = body["explanation"]
    assert body["outcome"] == "DENIED"
    assert (1, reason_text("DN_NOT_MEDICALLY_NECESSARY").provider) in [
        (item["line_no"], item["text"]) for item in explanation["why"]
    ]
    assert [(g["line_no"], [c["code"] for c in g["codes"]]) for g in explanation["codes"]] == [
        (1, ["50"])
    ]
    assert "reviewer-1" not in json.dumps(body)
    for fmt in ("text", "html"):
        shown = client.get(
            f"/v1/claims/{CLAIM}/explanation", params={"format": fmt}, headers=PROVIDER
        )
        assert shown.status_code == 200, shown.text
        assert "not medically necessary under the coverage criteria" in shown.text
        assert "CARC 50" in shown.text
        assert "Private reviewer note" not in shown.text
        assert "Overall comment" not in shown.text
    assert "Private reviewer note" not in json.dumps(body)
    assert "Overall comment" not in json.dumps(body)
    listed = client.get("/v1/claims", headers=PROVIDER).json()
    assert "Private reviewer note" not in json.dumps(listed)


def test_a_pend_override_carries_its_pend_reason_without_a_carc(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")

    response = client.post(
        f"/v1/claims/{CLAIM}/review",
        json=override(decision="PEND", reason_code="PD_MISSING_DOCUMENTATION"),
    )

    assert response.status_code == 200, response.text
    assert response.json()["line_decisions"][0]["reason_codes"] == ["PD_MISSING_DOCUMENTATION"]
    body = client.get(f"/v1/claims/{CLAIM}", headers=PROVIDER).json()
    assert body["explanation"]["codes"] == []  # pended lines get no CARC (D-CARC-1)
    assert (1, reason_text("PD_MISSING_DOCUMENTATION").provider) in [
        (item["line_no"], item["text"]) for item in body["explanation"]["why"]
    ]
    shown = client.get(
        f"/v1/claims/{CLAIM}/explanation", params={"format": "text"}, headers=PROVIDER
    ).text
    assert "documentation is missing" in shown
    assert "Private reviewer note" not in shown


def test_an_approve_override_takes_no_reason_code(api, load_case_reference) -> None:  # noqa: ANN001
    """E2E-25: the model denies the line; a reviewer's APPROVE with a reason code is refused."""
    client = process_case(api, load_case_reference, "E2E-25")
    action = {
        **override(decision="APPROVE", reason_code="DN_NOT_MEDICALLY_NECESSARY"),
        "claim_id": "CLM-E2E-25",
    }

    response = client.post("/v1/claims/CLM-E2E-25/review", json=action)

    assert response.status_code == 422
    assert "a reason code goes with a DENY or PEND decision only" in response.json()["detail"]
