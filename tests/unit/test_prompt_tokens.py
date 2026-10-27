"""D-DOC-3: prompt tokens before the model is called (app/ml/tokens.py) and the largest prompt a
claim can get (app/context/prompt_budget.py). The count against Ollama's own is
scripts/verify/prompt_token_check.py (26 of 26 equal); the bound against 7,116 real prompts is
scripts/verify/prompt_bound_check.py (none above it)."""

from pathlib import Path

import pytest

from app.context.prompt_budget import (
    LINE_FLAGS,
    criteria_shown,
    largest_prompt_tokens,
    worst_contexts,
)
from app.core.settings import get_settings
from app.db.curated import load_curated
from app.domain.contracts import Network
from app.ml.prompt import PromptLookups
from app.ml.tokens import PROMPT_BUDGET, TokenizerUnavailable, _tokenizer, chat_text, prompt_tokens
from tests.unit.test_forms import full_claim

TOKENIZER = get_settings().prompt_tokenizer
CURATED = load_curated("v2")
LOOKUPS = PromptLookups(
    icd10_descriptions={},
    procedure_descriptions=CURATED.descriptions,
    policy_codes={p: list(policy.procedure_codes) for p, policy in CURATED.policies.items()},
)


def test_the_text_is_the_chat_format_ollama_renders() -> None:
    assert chat_text(" sys \n", "\nuser ") == (
        "<bos><|turn>system\nsys<turn|>\n<|turn>user\nuser<turn|>\n<|turn>model\n"
    )
    assert PROMPT_BUDGET == 8192 - 1536


def test_the_turn_markers_and_bos_are_one_token_each() -> None:
    tokenizer = _tokenizer(str(TOKENIZER))
    for special in ("<bos>", "<|turn>", "<turn|>"):
        assert len(tokenizer.encode(special, add_special_tokens=False).ids) == 1
    assert prompt_tokens("a", "b", TOKENIZER) == len(
        tokenizer.encode(chat_text("a", "b"), add_special_tokens=False).ids
    )


def test_a_missing_or_other_tokenizer_file_counts_nothing(tmp_path: Path) -> None:
    with pytest.raises(TokenizerUnavailable, match="missing: run make setup"):
        prompt_tokens("a", "b", tmp_path / "tokenizer.json")
    other = tmp_path / "other.json"
    other.write_text("{}")
    with pytest.raises(TokenizerUnavailable, match="not the pinned one"):
        prompt_tokens("a", "b", other)


def test_the_worst_case_covers_every_plan_network_flag_and_criterion() -> None:
    claim = full_claim()
    contexts = list(worst_contexts(claim, CURATED))
    assert len(contexts) == 2 * len(CURATED.plans)
    assert {c.network for c in contexts} == set(Network)
    for context in contexts:
        assert [line.line_no for line in context.lines] == [x.line_no for x in claim.service_lines]
        for line, service in zip(context.lines, claim.service_lines, strict=True):
            assert line.rule_flags == LINE_FLAGS
            shown = criteria_shown(CURATED, service.procedure_code, service.date_of_service)
            assert line.criteria == shown
            for policy in CURATED.policies.values():  # every plan's criteria for the code
                for criterion in policy.criteria:
                    if service.procedure_code in policy.criterion_codes(criterion) and (
                        policy.effective_date <= service.date_of_service
                    ):
                        assert criterion.criterion_id in {c.criterion_id for c in shown}


def test_the_notes_are_counted_exactly() -> None:
    claim = full_claim()
    notes = "Exam today: tenderness over the lower lumbar facets. " * 40
    longer = claim.model_copy(update={"clinical_notes": claim.clinical_notes + " " + notes})
    base = largest_prompt_tokens(claim, LOOKUPS, CURATED, "decision_v3", TOKENIZER)
    more = largest_prompt_tokens(longer, LOOKUPS, CURATED, "decision_v3", TOKENIZER)
    added = len(_tokenizer(str(TOKENIZER)).encode(" " + notes.strip(), add_special_tokens=False))
    assert abs((more - base) - added) <= 2  # the notes' own tokens, give or take a boundary
