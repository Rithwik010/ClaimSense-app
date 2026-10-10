"""Ollama Modelfile for the fine-tuned GGUF (P4.5), on the laptop after downloading it from Kaggle.

Copies the base model's chat handling (TEMPLATE, RENDERER, PARSER and parameters) from
`ollama show <base> --modelfile`, so the fine-tuned model formats chats exactly like the base model
used for the baseline. Then:

    uv run python -m training.finetune.modelfile --gguf path/to/model.Q4_K_M.gguf --version 1
    ollama create claimsense-decision:v1 -f data/generated/models/claimsense-decision-v1/Modelfile
    # then MODEL_NAME=claimsense-decision:v1 in .env
"""

import argparse
from pathlib import Path

import httpx

from training.generate.common import GENERATED_DIR

COPIED = ("TEMPLATE", "RENDERER", "PARSER", "PARAMETER")


def base_directives(modelfile: str) -> list[str]:
    """The lines of the base Modelfile that control chat formatting and sampling."""
    lines = []
    for line in modelfile.splitlines():
        keyword = line.split(" ", 1)[0]
        if keyword in COPIED:
            lines.append(line)
    return lines


def build(gguf: Path, base_modelfile: str) -> str:
    """The FROM line, the base model's directives and the context window the client asks for
    (D-MODEL-1), so `ollama run` gives the same context as the pipeline."""
    from app.ml.client import MODEL_NUM_CTX

    directives = [
        d for d in base_directives(base_modelfile) if not d.startswith("PARAMETER num_ctx")
    ]
    lines = [f"FROM {gguf.resolve()}", *directives, f"PARAMETER num_ctx {MODEL_NUM_CTX}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    from app.core.settings import get_settings

    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--base", default="gemma4:e2b")
    args = parser.parse_args()
    response = httpx.post(f"{settings.ollama_url}/api/show", json={"model": args.base}, timeout=30)
    response.raise_for_status()
    name = f"claimsense-decision:v{args.version}"
    out = GENERATED_DIR / "models" / f"claimsense-decision-v{args.version}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "Modelfile").write_text(build(args.gguf, response.json()["modelfile"]))
    print(f"ollama create {name} -f {out / 'Modelfile'}")


if __name__ == "__main__":
    main()
