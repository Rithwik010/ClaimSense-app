"""Ollama Modelfile for the fine-tuned GGUF (P4.5), on the laptop after downloading it from Kaggle.

Copies the base model's chat handling (TEMPLATE, RENDERER, PARSER and parameters) from
`ollama show <base> --modelfile`, so the fine-tuned model formats chats exactly like the base model
used for the baseline; parameters in the order `ollama show` prints them. A model that has been
evaluated has its settings pinned in `training/finetune/evaluated/<model>.json`: the writer stops
when the Modelfile would set anything else (a newer base model with another template, say), and
`make model-check` compares the running model and a model built from the Modelfile with it. Then:

    uv run python -m training.finetune.modelfile --gguf path/to/model.Q4_K_M.gguf --version 1
    ollama create claimsense-decision:v1 -f data/generated/models/claimsense-decision-v1/Modelfile
    # then MODEL_NAME=claimsense-decision:v1 in .env
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

import httpx

from training.generate.common import GENERATED_DIR

COPIED = ("TEMPLATE", "RENDERER", "PARSER", "PARAMETER")
EVALUATED = Path(__file__).parent / "evaluated"
QUOTES = '"""'


def parse(modelfile: str) -> list[tuple[str, str]]:
    """(KEYWORD, value) in file order; a value in triple quotes may span lines. Comments and blank
    lines are skipped."""
    found = []
    lines = iter(modelfile.splitlines())
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        keyword, _, value = line.strip().partition(" ")
        value = value.strip()
        if value.startswith(QUOTES):
            value = value[len(QUOTES) :]
            while not value.endswith(QUOTES):
                value += "\n" + next(lines)
            value = value[: -len(QUOTES)]
        found.append((keyword.upper(), value))
    return found


def directive(keyword: str, value: str) -> str:
    return f"{keyword} {QUOTES}{value}{QUOTES}" if "\n" in value else f"{keyword} {value}"


def base_directives(modelfile: str) -> list[str]:
    """The directives of the base Modelfile that control chat formatting and sampling."""
    return [directive(k, v) for k, v in parse(modelfile) if k in COPIED]


def settings(modelfile: str) -> dict[str, list[str]]:
    """Everything a Modelfile sets except FROM (KEYWORD -> values; parameters sorted, since Ollama
    keeps them as a map): what must match the evaluated model exactly."""
    found: dict[str, list[str]] = {}
    for keyword, value in parse(modelfile):
        if keyword != "FROM":
            found.setdefault(keyword, []).append(value)
    if "PARAMETER" in found:
        found["PARAMETER"] = sorted(" ".join(v.split()) for v in found["PARAMETER"])
    return found


def weights(modelfile: str) -> str | None:
    """The weights' sha256 when FROM names an Ollama blob (as `ollama show` prints it)."""
    match = re.search(r"sha256[-:]([0-9a-f]{64})", dict(parse(modelfile)).get("FROM", ""))
    return match.group(1) if match else None


def evaluated(model: str) -> dict[str, Any] | None:
    path = EVALUATED / f"{model.replace(':', '-')}.json"
    return json.loads(path.read_text()) if path.exists() else None


def differences(expected: dict[str, list[str]], found: dict[str, list[str]]) -> list[str]:
    return [
        f"{key}: {found.get(key, [])} (evaluated: {expected.get(key, [])})"
        for key in sorted(set(expected) | set(found))
        if expected.get(key, []) != found.get(key, [])
    ]


def build(gguf: Path, base_modelfile: str) -> str:
    """The FROM line, the base model's directives and the context window the client asks for
    (D-MODEL-1), so `ollama run` gives the same context as the pipeline."""
    from app.ml.client import MODEL_NUM_CTX

    if "mmproj" in gguf.name.lower():
        raise SystemExit(f"{gguf.name} is the vision projector; pass the model's Q4_K_M GGUF")
    directives = base_directives(base_modelfile)
    others = [d for d in directives if not d.startswith("PARAMETER ")]
    parameters = [d for d in directives if d.startswith("PARAMETER ") and d.split()[1] != "num_ctx"]
    parameters = sorted([*parameters, f"PARAMETER num_ctx {MODEL_NUM_CTX}"])
    return "\n".join([f"FROM {gguf.resolve()}", *others, *parameters]) + "\n"


def main() -> None:
    from app.core.settings import get_settings

    config = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--base", default="gemma4:e2b")
    parser.add_argument("--tag", help="model tag and folder (default v<version>; e4b for E4B)")
    args = parser.parse_args()
    tag = args.tag or f"v{args.version}"
    response = httpx.post(f"{config.ollama_url}/api/show", json={"model": args.base}, timeout=30)
    response.raise_for_status()
    name = f"claimsense-decision:{tag}"
    out = GENERATED_DIR / "models" / f"claimsense-decision-{tag}"
    text = build(args.gguf, response.json()["modelfile"])
    reference = evaluated(name)
    if reference is not None and (found := differences(reference["settings"], settings(text))):
        raise SystemExit(
            f"{name} was evaluated with other settings than {args.base} gives now; not written:\n"
            + "\n".join(found)
        )
    out.mkdir(parents=True, exist_ok=True)
    (out / "Modelfile").write_text(text)
    print(f"ollama create {name} -f {out / 'Modelfile'}")


if __name__ == "__main__":
    main()
