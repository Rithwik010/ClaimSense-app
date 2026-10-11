"""`make model-check`: are the demo model in Ollama and the model its Modelfile builds the model
that was evaluated? Part of the clean-clone run (SETUP.md Part I, D-PROC-3, D-MODEL-6).

Compared exactly with `training/finetune/evaluated/<model>.json` (written once, with --record,
from the model the evaluation ran on): the weights' sha256 and everything else the Modelfile sets
(template, system prompt, renderer, parser, every parameter; FROM aside).

1. the running model, from `ollama show <model> --modelfile`;
2. `data/generated/models/claimsense-decision-<tag>/Modelfile`, built into a throwaway model
   (`ollama create claimsense-decision:modelfile-check`, removed afterwards), so the check covers
   what a fresh setup builds; skipped when there is no Modelfile (the model was copied in).

The manifest digest is reported as well: the same digest means the very same model; another digest
with matching settings and weights usually means another Ollama version.

    uv run python -m scripts.verify.model_check [--model claimsense-decision:v2] [--record]
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from app.core.settings import get_settings
from training.finetune.modelfile import EVALUATED, differences, evaluated, settings, weights

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "data" / "generated" / "models"
THROWAWAY = "claimsense-decision:modelfile-check"


def show(url: str, model: str) -> tuple[str, str] | None:
    """The model's Modelfile as Ollama prints it and its manifest digest; None if absent."""
    shown = httpx.post(f"{url}/api/show", json={"model": model}, timeout=60)
    if shown.status_code == 404:
        return None
    shown.raise_for_status()
    tags = httpx.get(f"{url}/api/tags", timeout=30).json()["models"]
    digest = next((m["digest"] for m in tags if m["name"] == model), "")
    return shown.json()["modelfile"], digest


def compare(reference: dict[str, Any], modelfile: str) -> list[str]:
    found = differences(reference["settings"], settings(modelfile))
    sha = weights(modelfile)
    if sha != reference["weights_sha256"]:
        found.append(f"weights: sha256 {sha} (evaluated: {reference['weights_sha256']})")
    return found


def summary(reference: dict[str, Any], digest: str) -> str:
    kept = reference["settings"]
    parts = [
        f"weights {reference['weights_sha256'][:12]}",
        *(k.lower() for k in ("TEMPLATE", "RENDERER", "PARSER") if k in kept),
        f"{len(kept.get('PARAMETER', []))} parameters",
        "system prompt" if "SYSTEM" in kept else "no system prompt",
    ]
    evaluated_digest = reference["manifest_digest"]
    manifest = (
        "same manifest"
        if digest == evaluated_digest
        else f"manifest {digest[:12]} (evaluated {evaluated_digest[:12]})"
    )
    return f"{', '.join(parts)}; {manifest}"


def line(ok: bool, what: str, detail: str) -> bool:
    print(f"{'OK  ' if ok else 'FAIL'} {what:<14} {detail}")
    return ok


def record(url: str, model: str) -> None:
    shown = show(url, model)
    if shown is None:
        raise SystemExit(f"{model} is not in Ollama")
    modelfile, digest = shown
    version = httpx.get(f"{url}/api/version", timeout=30).json()["version"]
    reference = {
        "model": model,
        "recorded": date.today().isoformat(),
        "ollama": version,
        "manifest_digest": digest,
        "weights_sha256": weights(modelfile),
        "settings": settings(modelfile),
    }
    EVALUATED.mkdir(parents=True, exist_ok=True)
    path = EVALUATED / f"{model.replace(':', '-')}.json"
    path.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "claimsense-decision:v2"))
    parser.add_argument(
        "--record", action="store_true", help="pin the running model (only the evaluated one)"
    )
    args = parser.parse_args()
    url = get_settings().ollama_url
    if args.record:
        record(url, args.model)
        return
    reference = evaluated(args.model)
    if reference is None:
        raise SystemExit(f"no evaluated settings for {args.model} in {EVALUATED}")

    ok = True
    shown = show(url, args.model)
    if shown is None:
        ok = line(False, "running model", f"{args.model} is not in Ollama")
    else:
        found = compare(reference, shown[0])
        ok &= line(
            not found,
            "running model",
            f"{args.model}: " + ("; ".join(found) if found else summary(reference, shown[1])),
        )

    modelfile = MODELS / f"claimsense-decision-{args.model.split(':')[-1]}" / "Modelfile"
    if not modelfile.exists():
        print(f"--   Modelfile      {modelfile.relative_to(ROOT)} not found: build check skipped")
    else:
        env = dict(os.environ, OLLAMA_HOST=url)
        built = subprocess.run(
            ["ollama", "create", THROWAWAY, "-f", str(modelfile)],
            capture_output=True,
            text=True,
            env=env,
        )
        try:
            rebuilt = show(url, THROWAWAY) if built.returncode == 0 else None
            if rebuilt is None:
                failed = built.stderr.strip()[-200:]
                ok &= line(False, "Modelfile", f"ollama create failed: {failed}")
            else:
                found = compare(reference, rebuilt[0])
                ok &= line(
                    not found,
                    "Modelfile",
                    f"{modelfile.relative_to(ROOT)} builds "
                    + ("; ".join(found) if found else summary(reference, rebuilt[1])),
                )
        finally:
            subprocess.run(["ollama", "rm", THROWAWAY], capture_output=True, env=env)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
