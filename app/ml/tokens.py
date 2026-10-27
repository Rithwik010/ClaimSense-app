"""Prompt tokens before the model is called (D-DOC-3): the exact count of what Ollama receives, so a
prompt that would not fit the model's context is never sent (Ollama would cut it without saying).

The text is the decision model's chat format as its renderer writes it (Modelfile `RENDERER
gemma4`; the same as the chat template in the model's GGUF): the BOS token, then each message as
`<|turn>role\\n` + its trimmed text + `<turn|>\\n`, then `<|turn>model\\n` for the answer. It is
counted with the base model's own tokenizer (tokenizer.json of unsloth/gemma-4-E2B-it at the
commit the model was trained and exported from, D-V3-31), read from the local file only
(`Settings.prompt_tokenizer`; `scripts/setup/fetch_tokenizer.py` puts it next to the model files at
setup, its SHA-256 checked), never from the Hub. scripts/verify/prompt_token_check.py compares the
count with Ollama's own `prompt_eval_count`.
"""

import hashlib
from functools import cache
from pathlib import Path

from tokenizers import Tokenizer

from app.ml.client import MAX_OUTPUT_TOKENS, MODEL_NUM_CTX

TOKENIZER_COMMIT = "d36bdd3855c82a6a1a23f7c459b749f5724ae75d"  # unsloth/gemma-4-E2B-it (D-V3-31)
TOKENIZER_SHA256 = "cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f"
BOS = "<bos>"
PROMPT_BUDGET = MODEL_NUM_CTX - MAX_OUTPUT_TOKENS  # 6,656 (the answer has the rest of the context)


class TokenizerUnavailable(RuntimeError):
    """The local tokenizer file is missing or not the pinned one: prompts cannot be counted."""


def chat_text(system: str, user: str) -> str:
    """The text the model receives for one system and one user message, ready for its answer."""
    return (
        f"{BOS}<|turn>system\n{system.strip()}<turn|>\n"
        f"<|turn>user\n{user.strip()}<turn|>\n<|turn>model\n"
    )


@cache
def _tokenizer(path: str) -> Tokenizer:
    file = Path(path)
    if not file.is_file():
        raise TokenizerUnavailable(f"the prompt tokenizer {file} is missing: run make setup")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    if digest != TOKENIZER_SHA256:
        raise TokenizerUnavailable(f"the prompt tokenizer {file} is not the pinned one ({digest})")
    return Tokenizer.from_file(str(file))


def prompt_tokens(system: str, user: str, path: Path) -> int:
    """Tokens of the model's whole prompt, special tokens included."""
    return len(_tokenizer(str(path)).encode(chat_text(system, user), add_special_tokens=False))
