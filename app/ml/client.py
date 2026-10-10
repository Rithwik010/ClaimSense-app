"""Local model client (INSTRUCTIONS.md §8.5). Inference runs through Ollama only (H8).

The `SLMOutput` JSON schema is passed as the structured output format, with temperature 0, a fixed
seed and thinking disabled, so the same model and prompt give the same answer. The client returns
the raw text; `app.ml.validate` decides whether it is usable.
"""

from typing import Any, Protocol

import httpx
import ollama

from app.domain.contracts import SLMOutput

MODEL_SEED = 20260921
# One retry when the first answer is invalid (D-DEC-1): another fixed seed, at temperature 0.7 so
# the seed matters (the open item's measurement recovered 5-8 of 16 dropped-line records).
RETRY_SEED = 20261010
RETRY_TEMPERATURE = 0.7
MODEL_TIMEOUT_SECONDS = 300.0

# An answer that repeats itself never closes its JSON, so the schema alone does not stop it: the
# P4.4 runs saw answers grow to 12-15k characters over 45-83 seconds before the server gave up,
# and every one of them was invalid anyway. The longest valid answer measured across the baseline,
# the fine-tuned model and the validation diagnostic is 3,080 characters (about 880 tokens), so
# this cap is roughly twice the longest real answer: it ends a loop early without truncating any
# answer that would have been usable.
MAX_OUTPUT_TOKENS = 1536
# Context window for every request (D-MODEL-1): the longest v2 prompt (about 2,700 tokens) plus the
# answer cap fit with room to spare; Ollama's 4,096 default would leave no margin and shifts the
# context silently when it overflows.
MODEL_NUM_CTX = 8192


class ModelUnavailable(RuntimeError):
    """Ollama could not be reached or refused the request; the claim can be processed later."""


class DecisionModel(Protocol):
    name: str

    def complete(self, system: str, user: str, attempt: int = 1) -> str: ...


class OllamaDecisionModel:
    def __init__(
        self, host: str, name: str, timeout: float = MODEL_TIMEOUT_SECONDS, **client_args: Any
    ) -> None:
        self.name = name
        self._client = ollama.Client(host=host, timeout=timeout, **client_args)

    def complete(self, system: str, user: str, attempt: int = 1) -> str:
        """Attempt 1: temperature 0 and MODEL_SEED; a retry: RETRY_TEMPERATURE and RETRY_SEED."""
        first = attempt == 1
        try:
            response = self._client.chat(
                model=self.name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                format=SLMOutput.model_json_schema(),
                options={
                    "temperature": 0 if first else RETRY_TEMPERATURE,
                    "seed": MODEL_SEED if first else RETRY_SEED,
                    "num_predict": MAX_OUTPUT_TOKENS,
                    "num_ctx": MODEL_NUM_CTX,
                },
                think=False,
            )
        except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as exc:
            raise ModelUnavailable(f"model {self.name} unavailable ({type(exc).__name__})") from exc
        return response.message.content or ""
