"""The base model's tokenizer for the prompt token guard (D-DOC-3), fetched once at setup.

Downloads tokenizer.json of unsloth/gemma-4-E2B-it at the pinned commit (app/ml/tokens.py
`TOKENIZER_COMMIT`, D-V3-31) to `Settings.prompt_tokenizer`, next to the model files
(data/generated, never committed), and checks its SHA-256 against `TOKENIZER_SHA256`. Does nothing
when the pinned file is already there, so `make setup` can run it every time; the API reads only
the local file.

    uv run python -m scripts.setup.fetch_tokenizer
"""

import hashlib
import sys

import httpx

from app.core.settings import get_settings
from app.ml.tokens import TOKENIZER_COMMIT, TOKENIZER_SHA256

URL = f"https://huggingface.co/unsloth/gemma-4-E2B-it/resolve/{TOKENIZER_COMMIT}/tokenizer.json"


def main() -> None:
    path = get_settings().prompt_tokenizer
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == TOKENIZER_SHA256:
        print(f"{path}: present, the pinned tokenizer")
        return
    data = httpx.get(URL, follow_redirects=True, timeout=300).raise_for_status().content
    digest = hashlib.sha256(data).hexdigest()
    if digest != TOKENIZER_SHA256:
        sys.exit(f"downloaded tokenizer has SHA-256 {digest}, not the pinned {TOKENIZER_SHA256}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"{path}: fetched ({len(data)} bytes, SHA-256 checked)")


if __name__ == "__main__":
    main()
