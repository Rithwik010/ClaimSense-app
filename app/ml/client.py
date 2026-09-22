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
MODEL_TIMEOUT_SECONDS = 300.0


class ModelUnavailable(RuntimeError):
    """Ollama could not be reached or refused the request; the claim can be processed later."""


class DecisionModel(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


class OllamaDecisionModel:
    def __init__(
        self, host: str, name: str, timeout: float = MODEL_TIMEOUT_SECONDS, **client_args: Any
    ) -> None:
        self.name = name
        self._client = ollama.Client(host=host, timeout=timeout, **client_args)

    def complete(self, system: str, user: str) -> str:
        try:
            response = self._client.chat(
                model=self.name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                format=SLMOutput.model_json_schema(),
                options={"temperature": 0, "seed": MODEL_SEED},
                think=False,
            )
        except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as exc:
            raise ModelUnavailable(f"model {self.name} unavailable ({type(exc).__name__})") from exc
        return response.message.content or ""
