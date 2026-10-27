"""A GGUF file's packaging, for comparing a v3 export with v2's (the team's request of 24 Oct).
Report only.

Reads the metadata (not the weights): the file type (the quantization), the file size, the
architecture, the chat template's SHA-256 (and its length), the tokenizer (model, pre-tokenizer,
vocabulary size, special token ids, add-BOS and add-EOS), the count of tensors per type (the
quantization mix), and any general.* field naming the tool or version that made it. Needs the `gguf`
package (llama.cpp's gguf-py), which is not a project dependency:

    uv run --with gguf python -m scripts.verify.gguf_packaging [--names] <file.gguf> [...]

`--names` adds every tensor's name and type, for comparing by name.

The same `summary` runs inside the Kaggle export notebook (scripts/kaggle/v3_export.py).
"""

import hashlib
import json
import os
import sys
from collections import Counter


def summary(path: str, names: bool = False) -> dict:
    from gguf import GGUFReader

    reader = GGUFReader(path)

    def value(key: str):  # noqa: ANN202
        field = reader.fields.get(key)
        if field is None:
            return None
        parts = [field.parts[i] for i in field.data]
        if field.types and field.types[0].name == "STRING":
            return bytes(parts[0]).decode("utf-8", errors="replace")
        if field.types and field.types[0].name == "ARRAY":
            return len(parts)
        return parts[0].tolist()[0] if hasattr(parts[0], "tolist") else parts[0]

    template = value("tokenizer.chat_template")
    general = {
        key: value(key)
        for key in reader.fields
        if key.startswith("general.") and key not in ("general.name", "general.basename")
    }
    return {
        "file": os.path.basename(path),
        "size_gb": round(os.path.getsize(path) / 1e9, 3),
        "architecture": value("general.architecture"),
        "file_type": value("general.file_type"),
        "quantization_version": value("general.quantization_version"),
        "general": general,
        "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest() if template else None,
        "chat_template_characters": len(template) if template else 0,
        "tokenizer": {
            "model": value("tokenizer.ggml.model"),
            "pre": value("tokenizer.ggml.pre"),
            "tokens": value("tokenizer.ggml.tokens"),
            "bos_token_id": value("tokenizer.ggml.bos_token_id"),
            "eos_token_id": value("tokenizer.ggml.eos_token_id"),
            "padding_token_id": value("tokenizer.ggml.padding_token_id"),
            "unknown_token_id": value("tokenizer.ggml.unknown_token_id"),
            "add_bos_token": value("tokenizer.ggml.add_bos_token"),
            "add_eos_token": value("tokenizer.ggml.add_eos_token"),
        },
        "tensors": len(reader.tensors),
        "tensor_types": dict(sorted(Counter(t.tensor_type.name for t in reader.tensors).items())),
        **({"tensor_names": {t.name: t.tensor_type.name for t in reader.tensors}} if names else {}),
    }


def chat_template(path: str) -> str | None:
    from gguf import GGUFReader

    field = GGUFReader(path).fields.get("tokenizer.chat_template")
    return bytes(field.parts[field.data[0]]).decode("utf-8") if field else None


if __name__ == "__main__":
    paths = [p for p in sys.argv[1:] if p != "--names"]
    print(json.dumps([summary(p, "--names" in sys.argv) for p in paths], indent=2))
