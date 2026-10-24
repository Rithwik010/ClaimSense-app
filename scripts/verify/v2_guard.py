"""Model v2 is untouched (the team's rule of 24 Oct, D-V3-27): read only, exits 1 on any difference.

Run before and after every v3 export or copy step that touches the laptop. Hashes (SHA-256) and
compares with the evaluated file's `weights_sha256` (training/finetune/evaluated/
claimsense-decision-v2.json, 7cbaf133...):

- v2's GGUF file, the one its Modelfile names (data/generated/models/claimsense-decision-v2/
  Modelfile in the main worktree, found with `git worktree list`);
- the weights blob Ollama serves for claimsense-decision:v2 (its manifest's model layer, read from
  ~/.ollama/models without the Ollama server), which must be the same digest and hash to it.

    uv run python -m scripts.verify.v2_guard [--label "before the export download"]
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINNED = ROOT / "training" / "finetune" / "evaluated" / "claimsense-decision-v2.json"
MANIFEST = (
    Path.home() / ".ollama/models/manifests/registry.ollama.ai/library/claimsense-decision/v2"
)
BLOBS = Path.home() / ".ollama/models/blobs"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def main_worktree() -> Path:
    found = subprocess.run(
        ["git", "worktree", "list", "--porcelain"], cwd=ROOT, capture_output=True, text=True
    ).stdout
    return Path(found.splitlines()[0].removeprefix("worktree "))


def guard() -> dict:
    expected = json.loads(PINNED.read_text())["weights_sha256"]
    modelfile = main_worktree() / "data/generated/models/claimsense-decision-v2/Modelfile"
    source = Path(
        next(
            line.removeprefix("FROM ").strip()
            for line in modelfile.read_text().splitlines()
            if line.startswith("FROM ")
        )
    )
    layer = next(
        layer
        for layer in json.loads(MANIFEST.read_text())["layers"]
        if layer["mediaType"] == "application/vnd.ollama.image.model"
    )
    blob = BLOBS / layer["digest"].replace(":", "-")
    found = {"gguf_file": sha256(source), "ollama_blob": sha256(blob)}
    return {
        "expected": expected,
        "gguf_path": str(source),
        "ollama_manifest_digest": layer["digest"],
        **found,
        "ok": layer["digest"] == f"sha256:{expected}"
        and all(v == expected for v in found.values()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="")
    label = parser.parse_args().label
    try:
        report = guard()
    except (OSError, StopIteration, KeyError, json.JSONDecodeError) as exc:
        report = {"ok": False, "error": repr(exc)}
    report["label"] = label
    print(json.dumps(report))
    sys.exit(0 if report["ok"] else 1)
