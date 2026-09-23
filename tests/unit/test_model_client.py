"""The Ollama client sends the schema, temperature 0, a fixed seed and thinking off (§8.5).

Ollama is simulated with an httpx mock transport."""

import json

import httpx
import pytest

from app.domain.contracts import SLMOutput
from app.ml.client import (
    MAX_OUTPUT_TOKENS,
    MODEL_SEED,
    ModelUnavailable,
    OllamaDecisionModel,
)


def model(handler) -> OllamaDecisionModel:
    return OllamaDecisionModel(
        "http://ollama.test", "gemma4:e2b", transport=httpx.MockTransport(handler)
    )


def test_request_carries_schema_and_deterministic_options() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "gemma4:e2b",
                "message": {"role": "assistant", "content": '{"lines": []}'},
                "done": True,
            },
        )

    text = model(handler).complete("system text", "user text")

    assert text == '{"lines": []}'
    assert seen["model"] == "gemma4:e2b"
    assert seen["format"] == SLMOutput.model_json_schema()
    assert seen["options"] == {
        "temperature": 0,
        "seed": MODEL_SEED,
        "num_predict": MAX_OUTPUT_TOKENS,  # a repeating answer is cut off, not left to run
    }
    assert seen["think"] is False
    assert seen["stream"] is False
    assert [m["role"] for m in seen["messages"]] == ["system", "user"]
    assert [m["content"] for m in seen["messages"]] == ["system text", "user text"]


def test_unreachable_or_failing_ollama_raises_model_unavailable() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    def missing_model(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'gemma4:e2b' not found"})

    for handler in (refused, missing_model):
        with pytest.raises(ModelUnavailable, match="gemma4:e2b"):
            model(handler).complete("s", "u")
