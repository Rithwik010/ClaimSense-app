"""D-DOC-3: the prompt token guard, through the API.

- A claim whose prompt could be longer than the model reads with its answer (`PROMPT_BUDGET`) is
  refused when it is filed, as a form of too many pages is, and nothing is kept.
- A correction that would make it so is refused, and the claim stays as it was; one that does
  not is made.
- The real prompt of a processed claim is never above the bound counted when it was filed.
- A claim that reaches processing with a prompt that long all the same (filed without the check,
  as no upload can be) is never sent to the model: its answer is unusable, so its lines pend for
  FULL review, with "model not called: prompt too long" in the details.
"""

import json

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.domain.contracts import IntakeClaim, LineDecision, ReviewTier, SourceFormat
from app.intake.form_codec import to_form_values
from app.ml.tokens import PROMPT_BUDGET, prompt_tokens
from app.workflow import pipeline
from app.workflow.pipeline import PROMPT_TOO_LONG, claim_prompt_bound, intake_claim_data
from tests.e2e.support import (
    E2E_CASES,
    FILED_BY_TEST_PROVIDER,
    PROVIDER,
    CaseRetriever,
    StubModel,
    audit,
    record_of,
)
from training.generate.forms import render_pdf

CASE = E2E_CASES["E2E-14"]  # clean claim, awaiting review after processing
CLAIM = CASE["given"]["claim"]
CLAIM_ID = CLAIM["claim_id"]
SETTINGS = Settings(policy_set="v1", prompt_version="decision_v2")  # the api fixture's default
SENTENCE = "Low back pain for six months, worse with standing, better with rest."
LONG = CLAIM | {"clinical_notes": " ".join([SENTENCE] * 600)}  # over 8,000 tokens of notes


def client_with(api, load_case_reference):  # noqa: ANN001, ANN201
    load_case_reference(CASE)
    model = StubModel(json.dumps(CASE["given"]["model_answer"]))
    return api(model, CaseRetriever(CASE)), model


def test_a_claim_whose_prompt_could_not_fit_is_refused_when_filed(api, load_case_reference) -> None:  # noqa: ANN001
    client, _ = client_with(api, load_case_reference)

    refused = client.post("/v1/claims/intake", json=LONG)

    assert refused.status_code == 422, refused.text
    detail = refused.json()["detail"]
    assert "clinical notes are too long for the decision model" in detail
    assert f"at most {PROMPT_BUDGET:,}" in detail
    assert client.get(f"/v1/claims/{CLAIM_ID}").status_code == 404  # nothing kept
    assert client.post("/v1/claims/intake", json=CLAIM).status_code == 201


def test_its_real_prompt_is_never_above_the_bound(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client, model = client_with(api, load_case_reference)
    assert client.post("/v1/claims/intake", json=CLAIM).status_code == 201

    assert client.post(f"/v1/claims/{CLAIM_ID}/process").status_code == 200

    (system, user), *_ = model.prompts
    with Session(engine) as session:
        bound = claim_prompt_bound(session, IntakeClaim.model_validate(CLAIM), SETTINGS)
    assert prompt_tokens(system, user, SETTINGS.prompt_tokenizer) <= bound <= PROMPT_BUDGET


def test_a_correction_that_could_not_fit_is_refused(
    api, load_case_reference, engine, monkeypatch
) -> None:  # noqa: ANN001, E501
    client, _ = client_with(api, load_case_reference)
    claim = IntakeClaim.model_validate(CLAIM)
    filed = client.post(
        "/v1/claims/intake/file",
        content=render_pdf(to_form_values(claim)),
        headers={**PROVIDER, "X-File-Name": "claim.pdf"},
    )
    assert filed.status_code == 201, filed.text
    longer = claim.model_copy(
        update={
            "service_lines": [claim.service_lines[0].model_copy(update={"procedure_code": "64490"})]
        }
    )
    with Session(engine) as session:
        bound = claim_prompt_bound(session, claim, SETTINGS)
        assert claim_prompt_bound(session, longer, SETTINGS) > bound  # the code shows criteria
    monkeypatch.setattr(pipeline, "PROMPT_BUDGET", bound)  # the claim as filed just fits

    def correct(field: str, value: str):  # noqa: ANN202
        return client.post(
            f"/v1/claims/{CLAIM_ID}/corrections",
            json={"corrections": [{"field": field, "value": value}]},
            headers=PROVIDER,
        )

    refused = correct("service_lines.0.procedure_code", "64490")
    assert refused.status_code == 422, refused.text
    assert "too long for the decision model" in refused.json()["detail"]
    form = client.get(f"/v1/claims/{CLAIM_ID}/form", headers=PROVIDER).json()
    code = next(b for b in form["boxes"] if b["field"] == "service_lines.0.procedure_code")
    assert code["text"] == claim.service_lines[0].procedure_code and not code["corrected"]
    assert correct("patient.last_name", "Another").status_code == 200  # not in the prompt


def test_a_prompt_too_long_is_never_sent_to_the_model(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client, model = client_with(api, load_case_reference)
    with Session(engine) as session:  # filed without the check, as no upload can be
        intake_claim_data(session, LONG, {}, SourceFormat.JSON, 0.9, **FILED_BY_TEST_PROVIDER)

    processed = client.post(f"/v1/claims/{CLAIM_ID}/process")

    assert processed.status_code == 200, processed.text
    assert model.prompts == []
    record = record_of(client, CLAIM_ID)
    assert record.status.value == "AWAITING_REVIEW" and record.review_tier is ReviewTier.FULL
    assert record.slm_output is None
    assert record.output_errors[0].startswith(PROMPT_TOO_LONG)
    assert {line.decision for line in record.line_decisions} == {LineDecision.PEND}
    invalid = [e for e in audit(client, CLAIM_ID) if e["event_type"] == "OUTPUT_INVALID"]
    assert len(invalid) == 1 and invalid[0]["payload"]["errors"][0].startswith(PROMPT_TOO_LONG)
