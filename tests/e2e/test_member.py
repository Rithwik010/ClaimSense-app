"""D-MEM-1, D-MEM-2, D-MEM-3: a member (a patient) through the API.

- A member lists only the claims in which they are the patient (claim.member_id is their member
  ID); another member's claim is 404 on every member route, the same answer as a claim that does
  not exist.
- Until a claim is final the member sees "Your claim is being processed" and nothing else of it:
  no outcome, amount or EOB. Once final: its outcome, the record's totals and, for a claim the
  plan decided, the patient EOB of D-EOB-1, the same one its provider gets, so its amounts equal
  the provider's EOB and the provider view's billing to the cent.
- On every golden end-to-end case (v1 and v2), before processing, after it and after review,
  nothing a member is sent holds clinical notes, model output, criteria, rule IDs, internal reason
  codes, reviewer IDs or reasons, or field confidences (asserted on the JSON).
- Benefits: the stored accumulators and visit usage of the current benefit year next to the
  plan's limits, as stored (nothing added or subtracted), before and after a finalization; another
  benefit year has nothing met; profile: name,
  member ID, plan and coverage dates only.
"""

import json
from datetime import date
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.deps import get_today
from app.api.main import app
from app.calculator.progress import remaining, used_bps
from app.db.curated import load_curated
from app.db.models import Accumulator, Benefit, Member, Plan, VisitUsage
from app.domain.contracts import ClaimStatus, DecisionRecord
from app.explain.eob import EOB_STATUSES, NOT_A_BILL
from app.explain.member import DUPLICATE, HEADINGS, PROCESSING
from app.explain.reasons import claim_outcome
from tests.e2e.support import E2E_CASES, PROVIDER, StubModel, add_member_user, record_of
from tests.e2e.test_provider_view import CASES, HIDDEN, HIDDEN_KEYS, run

TODAY = date(2026, 12, 20)  # the golden reviews' day: benefit year 2026 (D7)
NEVER_KEYS = (
    *HIDDEN_KEYS,
    "criteria",
    "evidence",
    "reviewer_id",
    "review",
    "line_decisions",
    "context_refs",
    "output_errors",
    "confidence",
    "clinical_notes",
    "intake",
    "explanation",
    "filed_by",
    "provider_id",
    "documents",
    "summary",
    "reasons",
)


def windows(text: str, size: int = 40) -> list[str]:
    """Stretches of a text long enough to be recognized anywhere (the privacy scan's rule)."""
    text = " ".join(text.split())
    return [text[i : i + size] for i in range(0, max(len(text) - size, 0) + 1, 20)]


def note_windows(notes: str) -> list[str]:
    """Stretches of the clinical notes, lower case, without the team-written service descriptions
    the notes restate ("Plan: ..."): the EOB names each service by that description."""
    text = " ".join(notes.lower().split())
    for description in load_curated().descriptions.values():
        text = text.replace(" ".join(description.lower().split()), " | ")
    return [piece for piece in windows(text) if "|" not in piece]


def member_unsafe(
    response: Any, case: dict[str, Any], record: DecisionRecord | None = None
) -> list[str]:  # noqa: ANN401
    """Everything in a member's response that must not be there."""
    text = json.dumps(response)
    flat = " ".join(text.split())
    found = HIDDEN.findall(text)
    found += [f'key "{key}"' for key in NEVER_KEYS if f'"{key}":' in text]
    notes = case["given"]["claim"].get("clinical_notes") or ""
    found += [f"note: {piece!r}" for piece in note_windows(notes) if piece in flat.lower()]
    action = case["given"].get("review_action") or {}
    secrets = [action.get("reviewer_id"), action.get("reason")]
    secrets += [o.get("reason") for o in action.get("line_overrides", [])]
    found += [f"review: {s!r}" for s in secrets if isinstance(s, str) and s and s in text]
    contexts = record.context_refs.lines if record and record.context_refs else []
    for line in contexts:
        for criterion in line.criteria:
            found += [f"criterion text: {p!r}" for p in windows(criterion.text)[:1] if p in flat]
    return found


def patient_of(case: dict[str, Any]) -> str:
    """The member to log in as: the claim's patient, or, when the claim names a member not on
    file (rule R04), the case's member, who then has no claim to see."""
    on_file = [m["member_id"] for m in case["given"]["reference_additions"]["members"]]
    claimed = case["given"]["claim"]["member_id"]
    return claimed if claimed in on_file else on_file[0]


def check_member(client, member: dict[str, str], case: dict[str, Any], record) -> None:  # noqa: ANN001
    """What the member is sent for the case's claim at this point, against the provider's view."""
    claim_id = case["given"]["claim"]["claim_id"]
    patient = patient_of(case)
    mine = case["given"]["claim"]["member_id"] == patient
    on_file = {  # the patient's earlier claims the case puts on file (the duplicate check)
        row["claim_id"]
        for row in case["given"]["reference_additions"].get("existing_claims", [])
        if row["member_id"] == patient
    }
    listed = client.get("/v1/member/claims", headers=member).json()
    view = client.get(f"/v1/member/claims/{claim_id}", headers=member)
    eob = client.get(f"/v1/member/claims/{claim_id}/eob", headers=member)
    assert member_unsafe(listed, case, record) == []
    if not mine:
        assert {c["claim_id"] for c in listed} == on_file
        assert view.status_code == eob.status_code == 404
        return
    assert sorted(c["claim_id"] for c in listed) == sorted({claim_id} | on_file)
    assert view.status_code == 200, view.text
    shown = view.json()
    assert shown == next(c for c in listed if c["claim_id"] == claim_id)
    assert member_unsafe(shown, case, record) == []
    status = record.status if record else ClaimStatus.RECEIVED
    if status in (ClaimStatus.RECEIVED, ClaimStatus.AWAITING_REVIEW):
        assert (shown["final"], shown["outcome"], shown["eob"]) == (False, PROCESSING, False)
        assert shown["heading"] == "Your claim is being processed"
        assert [shown[k] for k in ("billed_cents", "plan_pays_cents", "patient_pays_cents")] == [
            None,
            None,
            None,
        ]
        assert eob.status_code == 409
        return
    outcome = claim_outcome(status, record)
    failed = [r for r in record.rules_outcome.rule_results if not r.passed]
    if outcome == "REJECTED" and failed and all(r.reason_code == "RJ_DUPLICATE" for r in failed):
        outcome = DUPLICATE  # a copy of a claim the plan has, not returned to the provider (fix 11)
    assert (shown["final"], shown["outcome"], shown["heading"]) == (
        True,
        outcome,
        HEADINGS[outcome],
    )
    totals = record.amounts.totals if record.amounts else None
    assert (shown["billed_cents"], shown["plan_pays_cents"], shown["patient_pays_cents"]) == (
        (totals.billed_cents, totals.plan_pays_cents, totals.member_pays_cents)
        if totals
        else (None, None, None)
    )
    assert shown["eob"] is (status in EOB_STATUSES)
    if status not in EOB_STATUSES:
        assert eob.status_code == 409
        return
    assert eob.status_code == 200, eob.text
    theirs = eob.json()
    assert member_unsafe(theirs, case, record) == []
    assert theirs["notes"][0] == NOT_A_BILL
    # The same EOB the provider gets, so every amount is the same to the cent.
    assert theirs == client.get(f"/v1/claims/{claim_id}/eob", headers=PROVIDER).json()
    billing = client.get(f"/v1/claims/{claim_id}", headers=PROVIDER).json()["explanation"][
        "billing"
    ]
    if billing is not None:
        names = ("billed_cents", "allowed_cents", "plan_pays_cents", "patient_pays_cents")
        names += ("other_plan_paid_cents",)
        assert [[line[n] for n in names] for line in theirs["lines"]] == [
            [line[n] for n in names] for line in billing["lines"]
        ]
        assert [theirs["totals"][n] for n in names] == [billing["totals"][n] for n in names]
    if theirs["totals"] is not None:
        assert (shown["billed_cents"], shown["plan_pays_cents"], shown["patient_pays_cents"]) == (
            theirs["totals"]["billed_cents"],
            theirs["totals"]["plan_pays_cents"],
            theirs["totals"]["patient_pays_cents"],
        )


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_what_a_member_is_sent_before_and_after_the_decision(
    api, load_case_reference, engine, case: dict[str, Any]
) -> None:  # noqa: ANN001
    client = run(api, load_case_reference, engine, case)
    member = add_member_user(engine, patient_of(case))
    claim_id = case["given"]["claim"]["claim_id"]
    check_member(client, member, case, None)  # filed, not processed

    assert client.post(f"/v1/claims/{claim_id}/process").status_code == 200
    record = record_of(client, claim_id)
    check_member(client, member, case, record)
    action = case["given"].get("review_action")
    if action is None:
        return

    reviewed = client.post(f"/v1/claims/{claim_id}/review", json=action)
    assert reviewed.status_code == 200, reviewed.text
    check_member(client, member, case, DecisionRecord.model_validate(reviewed.json()))


def file_and_process(api, load_case_reference, engine, case_id: str):  # noqa: ANN001, ANN201
    """A golden case's claim filed and processed with its own stub model (each case's client
    replaces the model the API uses, so a claim is processed before the next is filed)."""
    case = E2E_CASES[case_id]
    client = run(api, load_case_reference, engine, case)
    claim_id = case["given"]["claim"]["claim_id"]
    assert client.post(f"/v1/claims/{claim_id}/process").status_code == 200
    return client


def outcomes(client, member: dict[str, str]) -> dict[str, tuple[str, bool]]:  # noqa: ANN001
    return {
        c["claim_id"]: (c["outcome"], c["eob"])
        for c in client.get("/v1/member/claims", headers=member).json()
    }


def test_a_member_sees_only_their_own_claims_and_each_outcome_once_final(
    api, load_case_reference, engine
) -> None:  # noqa: ANN001
    """MBR-000328 is the patient of E2E-19 (the model denies its line) and E2E-20 (it pends it);
    MBR-000318 of E2E-22 (a rule denies one line, the model approves the other)."""
    for case_id in ("E2E-19", "E2E-20"):
        file_and_process(api, load_case_reference, engine, case_id)
    client = file_and_process(api, load_case_reference, engine, "E2E-22")
    patient = add_member_user(engine, "MBR-000328")
    other = add_member_user(engine, "MBR-000318", "member-other")
    assert outcomes(client, patient) == {
        "CLM-E2E-19": (PROCESSING, False),
        "CLM-E2E-20": (PROCESSING, False),
    }
    assert outcomes(client, other) == {"CLM-E2E-22": (PROCESSING, False)}

    for case_id in ("E2E-19", "E2E-22"):
        action = E2E_CASES[case_id]["given"]["review_action"]
        assert client.post(f"/v1/claims/CLM-{case_id}/review", json=action).status_code == 200

    assert outcomes(client, patient) == {
        "CLM-E2E-19": ("DENIED", True),
        "CLM-E2E-20": (PROCESSING, False),  # still in review: nothing of its recommendation
    }
    assert outcomes(client, other) == {"CLM-E2E-22": ("PARTLY_APPROVED", True)}
    waiting = client.get("/v1/member/claims/CLM-E2E-20", headers=patient).json()
    assert waiting["heading"] == "Your claim is being processed" and waiting["eob"] is False
    assert client.get("/v1/member/claims/CLM-E2E-20/eob", headers=patient).status_code == 409

    # The EOB a member gets is their provider's EOB, to the cent.
    for member, claim_id in ((patient, "CLM-E2E-19"), (other, "CLM-E2E-22")):
        mine = client.get(f"/v1/member/claims/{claim_id}/eob", headers=member).json()
        assert mine == client.get(f"/v1/claims/{claim_id}/eob", headers=PROVIDER).json()
    partly = client.get("/v1/member/claims/CLM-E2E-22/eob", headers=other).json()
    expected = E2E_CASES["E2E-22"]["expected"]["final"]["line_decisions"]  # golden: 1 paid, 2 not
    assert [line["status"] for line in partly["lines"]] == [
        {"APPROVE": "PAID", "DENY": "NOT_PAID", "PEND": "PENDING"}[d["decision"]] for d in expected
    ]


def test_another_members_claim_is_not_found(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client = file_and_process(api, load_case_reference, engine, "E2E-14")
    action = E2E_CASES["E2E-14"]["given"]["review_action"]
    assert client.post("/v1/claims/CLM-E2E-14/review", json=action).status_code == 200
    load_case_reference(E2E_CASES["E2E-15"])  # another member on file, with no claim
    patient = add_member_user(engine, "MBR-000020")
    stranger = add_member_user(engine, "MBR-000154", "member-other")

    for path in ("/v1/member/claims/{}", "/v1/member/claims/{}/eob"):
        assert client.get(path.format("CLM-E2E-14"), headers=patient).status_code == 200
        for claim_id in ("CLM-E2E-14", "CLM-NOT-ON-FILE"):
            response = client.get(path.format(claim_id), headers=stranger)
            assert response.status_code == 404  # as if it did not exist
            assert response.json()["detail"] == f"claim {claim_id} not found"
    assert client.get("/v1/member/claims", headers=stranger).json() == []
    for path in ("/v1/claims/CLM-E2E-14", "/v1/claims/CLM-E2E-14/eob", "/v1/claims"):
        assert client.get(path, headers=patient).status_code == 403  # not through the claims API


def stored(engine: Engine, member_id: str) -> dict[str, Any]:
    """The member's plan and their stored accumulators and visit usage for benefit year 2026."""
    with Session(engine) as session:
        member = session.get(Member, member_id)
        assert member is not None
        plan = session.get(Plan, member.plan_id)
        rows = {
            network: session.get(Accumulator, (member_id, date(2026, 1, 1), network))
            for network in ("IN_NETWORK", "OUT_OF_NETWORK")
        }
        visits = session.get(VisitUsage, (member_id, date(2026, 1, 1), "REHAB_THERAPY"))
        rehab = session.get(Benefit, (member.plan_id, "REHAB_THERAPY"))
        return {
            "plan": plan,
            "met": {n: (r.deductible_met_cents, r.oop_met_cents) for n, r in rows.items() if r},
            "rehab_visits": visits.visits_used if visits else 0,
            "rehab_limit": rehab.visit_limit if rehab else None,
        }


def check_benefits(benefits: dict[str, Any], facts: dict[str, Any]) -> None:
    plan = facts["plan"]
    limits = {"IN_NETWORK": (plan.inn_deductible_cents, plan.inn_oop_max_cents)}
    if plan.oon_covered:
        limits["OUT_OF_NETWORK"] = (plan.oon_deductible_cents, plan.oon_oop_max_cents)
    assert [n["network"] for n in benefits["networks"]] == list(limits)
    for shown in benefits["networks"]:
        deductible, oop_max = limits[shown["network"]]
        met = facts["met"].get(shown["network"], (0, 0))
        assert shown == {  # the plan's limits and the stored amounts, as they are
            "network": shown["network"],
            "period_start": benefits["benefit_year_start"],
            "deductible_met_cents": met[0],
            "deductible_cents": deductible,
            "oop_met_cents": met[1],
            "oop_max_cents": oop_max,
            # what is left and the share met: the calculator's (D-MEM-5), passed on as they are
            "deductible_left_cents": remaining(deductible, met[0]),
            "deductible_met_bps": used_bps(deductible, met[0]),
            "oop_left_cents": remaining(oop_max, met[1]),
            "oop_met_bps": used_bps(oop_max, met[1]),
        }


def test_benefits_are_the_stored_amounts_next_to_the_plans_limits(
    api, load_case_reference, engine
) -> None:  # noqa: ANN001
    """E2E-22 (HMO, in network only): deductible 200.00 and out-of-pocket 300.00 met as stored, no
    rehab visit yet; once its approved therapy line is finalized, the amounts and visits are the
    ones the FINALIZED event stored."""
    client = file_and_process(api, load_case_reference, engine, "E2E-22")
    app.dependency_overrides[get_today] = lambda: TODAY
    member = add_member_user(engine, "MBR-000318")

    before = client.get("/v1/member/benefits", headers=member).json()
    facts = stored(engine, "MBR-000318")
    check_benefits(before, facts)
    assert facts["met"]["IN_NETWORK"] == (20000, 30000)
    # Worked by hand on PLN-HMO's 250.00 deductible and 4,000.00 maximum: 50.00 and 3,700.00 left,
    # 80.00% and 7.50% met.
    network = before["networks"][0]
    assert (network["deductible_left_cents"], network["deductible_met_bps"]) == (5000, 8000)
    assert (network["oop_left_cents"], network["oop_met_bps"]) == (370000, 750)
    assert (before["benefit_year_start"], before["benefit_year_end"], before["as_of"]) == (
        "2026-01-01",
        "2026-12-31",
        "2026-12-20",
    )
    assert (before["plan_id"], before["plan_type"], before["member_id"]) == (
        "PLN-HMO",
        "HMO",
        "MBR-000318",
    )
    assert facts["rehab_limit"] == 20  # PLN-HMO REHAB_THERAPY: 20 visits a year (benefits.yaml)
    assert before["visits"] == [
        {
            "benefit_category": "REHAB_THERAPY",
            "visit_limit": 20,
            "visits_used": 0,
            "visits_left": 20,
            "used_bps": 0,
        }
    ]
    assert member_unsafe(before, E2E_CASES["E2E-22"]) == []

    action = E2E_CASES["E2E-22"]["given"]["review_action"]
    assert client.post("/v1/claims/CLM-E2E-22/review", json=action).status_code == 200
    finalized = next(
        e
        for e in client.get("/v1/claims/CLM-E2E-22/audit").json()
        if e["event_type"] == "FINALIZED"
    )["payload"]

    after = client.get("/v1/member/benefits", headers=member).json()
    facts = stored(engine, "MBR-000318")
    check_benefits(after, facts)
    stored_after = finalized["accumulators"]["after"]
    assert facts["met"]["IN_NETWORK"] == (
        stored_after["deductible_met_cents"],
        stored_after["oop_met_cents"],
    )
    used = finalized["visit_usage"]["REHAB_THERAPY"]["after"]
    assert used == facts["rehab_visits"] == 1
    assert after["visits"] == [  # 1 of 20 used: 19 left, 5.00%
        {
            "benefit_category": "REHAB_THERAPY",
            "visit_limit": 20,
            "visits_used": used,
            "visits_left": 19,
            "used_bps": 500,
        }
    ]


def test_out_of_network_terms_are_shown_when_the_plan_covers_them(
    api, load_case_reference, engine
) -> None:  # noqa: ANN001
    """E2E-28 (PPO Silver, out-of-network visit): both networks; the in-network one has no stored
    row, so nothing is met of it; another benefit year has nothing stored at all."""
    client = file_and_process(api, load_case_reference, engine, "E2E-28")
    member = add_member_user(engine, "MBR-000321")
    app.dependency_overrides[get_today] = lambda: TODAY

    benefits = client.get("/v1/member/benefits", headers=member).json()
    facts = stored(engine, "MBR-000321")
    check_benefits(benefits, facts)
    assert [n["network"] for n in benefits["networks"]] == ["IN_NETWORK", "OUT_OF_NETWORK"]
    assert benefits["networks"][0]["deductible_met_cents"] == 0

    app.dependency_overrides[get_today] = lambda: date(2027, 1, 4)  # a new benefit year
    next_year = client.get("/v1/member/benefits", headers=member).json()
    assert next_year["benefit_year_start"] == "2027-01-01"
    for network in next_year["networks"]:
        assert network["deductible_met_cents"] == network["oop_met_cents"] == 0
        assert network["period_start"] == "2027-01-01"


def test_the_profile_is_name_member_id_plan_and_coverage_dates(
    api, load_case_reference, engine
) -> None:  # noqa: ANN001
    load_case_reference(E2E_CASES["E2E-14"])
    client = api(StubModel("unused"))  # no claim is processed
    member = add_member_user(engine, "MBR-000020")

    profile = client.get("/v1/member/profile", headers=member)

    assert profile.status_code == 200, profile.text
    written = next(
        m
        for m in E2E_CASES["E2E-14"]["given"]["reference_additions"]["members"]
        if m["member_id"] == "MBR-000020"
    )
    assert profile.json() == {
        "member_id": "MBR-000020",
        "name": f"{written['first_name']} {written['last_name']}",
        "plan_id": "PLN-PPO-SILVER",
        "plan_name": "ClaimSense PPO Silver",
        "plan_type": "PPO",
        "coverage_start": written["coverage_start"],
        "coverage_end": written.get("coverage_end"),
    }
    text = json.dumps(profile.json())
    for private in (written["date_of_birth"], written["address_line"], written["zip_code"]):
        assert private not in text
    me = client.get("/v1/auth/me", headers=member).json()
    assert (me["role"], me["member_id"], me["provider_id"]) == ("member", "MBR-000020", None)


def test_a_member_cannot_file_process_correct_or_review(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client = file_and_process(api, load_case_reference, engine, "E2E-14")
    member = add_member_user(engine, "MBR-000020")
    claim = dict(E2E_CASES["E2E-14"]["given"]["claim"], claim_id="CLM-MEMBER-TRY")
    accept = E2E_CASES["E2E-14"]["given"]["review_action"]
    for method, path, body in (
        ("POST", "/v1/claims/intake", claim),
        ("POST", "/v1/claims/intake/files", {"files": [{"content_base64": "bm90IGEgY2xhaW0="}]}),
        ("POST", "/v1/claims/CLM-E2E-14/process", None),
        ("POST", "/v1/claims/CLM-E2E-14/corrections", {"corrections": []}),
        ("POST", "/v1/claims/CLM-E2E-14/review/open", {"reviewer_id": "member-test"}),
        ("POST", "/v1/claims/CLM-E2E-14/review", dict(accept, reviewer_id="member-test")),
        ("GET", "/v1/claims/CLM-E2E-14/check", None),
        ("GET", "/v1/claims/CLM-E2E-14/document", None),
        ("GET", "/v1/claims/CLM-E2E-14/explanation", None),
        ("GET", "/v1/claims/CLM-E2E-14/audit", None),
        ("GET", "/v1/review/queue", None),
        ("GET", "/v1/plans/PLN-PPO-SILVER", None),
        ("GET", "/v1/metrics/overview", None),
    ):
        response = client.request(method, path, json=body, headers=member)
        assert response.status_code == 403, (method, path, response.text)
    view = client.get("/v1/claims/CLM-E2E-14", headers=PROVIDER).json()
    assert view["status"] == "IN_REVIEW"  # nothing changed
    refused = client.get("/v1/claims", headers=member).json()["detail"]
    assert refused.startswith("a member cannot do this")
