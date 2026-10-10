"""Before any Kaggle upload of the decision training data: check every file of the upload.

- AMA: no file holds AMA CPT descriptor text of any code the records bill or the scope lists
  (the descriptor texts from the MCD article download, as in V1b's guard);
- descriptions: every service line shows the team's own plain-language description of its code
  (data/curated/procedure_descriptions.csv), never another text;
- synthetic: every record comes from the generator (its generator version, synthetic claim and
  record IDs), patients appear only as age and sex, and no file holds an e-mail address, a phone
  number or a social security number pattern;
- private: every dataset-metadata.json and kernel-metadata.json is private.

    uv run python -m scripts.verify.kaggle_upload_check \
        data/generated/kaggle/claimsense-decision-v2 \
        data/generated/kaggle/claimsense-finetune-v2.ipynb
"""

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path

from app.db.curated import load_curated
from scripts.verify.policy_sources import cpt_descriptors, redact

LINE = re.compile(r"^\s+\d+\. \S+ \| POS \S+ \| (?P<code>\S+) (?P<desc>.+?) \| modifiers:", re.M)
PATIENT = re.compile(r"^Patient: (?P<value>.*)$", re.M)
PATIENT_OK = re.compile(r"^\d{1,3}-year-old, sex [MF]$")
CLAIM_ID = re.compile(r"^Claim ID: (?P<value>.*)$", re.M)
CLAIM_OK = re.compile(r"^CLM-[A-Z0-9]+-\d{5}$")
RECORD_OK = re.compile(r"^D[A-Z0-9]+-(?:TR|VA|TE)-\d{5}$")
PII = {
    "e-mail address": re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"),
    "phone number": re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b"),
    "social security number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}
GENERATORS = {"scenarios-v2", "scenarios-v1", "scenarios-v2-pilot"}


def files_of(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for path in paths:
        out += sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    return out


def record_problems(path: Path, descriptions: dict[str, str]) -> tuple[list[str], set[str], int]:
    """(problems, codes billed, records) of a JSONL file of chat records."""
    problems: list[str] = []
    codes: set[str] = set()
    count = 0
    for n, row in enumerate(map(json.loads, path.open(encoding="utf-8")), start=1):
        count += 1
        meta = row.get("metadata", {})
        if meta.get("generator_version") not in GENERATORS:
            problems.append(f"{path.name}:{n}: generator {meta.get('generator_version')!r}")
        if not RECORD_OK.match(str(meta.get("record_id", ""))):
            problems.append(f"{path.name}:{n}: record ID {meta.get('record_id')!r}")
        user = next(m["content"] for m in row["messages"] if m["role"] == "user")
        for found in PATIENT.finditer(user):
            if not PATIENT_OK.match(found.group("value")):
                problems.append(f"{path.name}:{n}: patient shown as {found.group('value')!r}")
        for found in CLAIM_ID.finditer(user):
            if not CLAIM_OK.match(found.group("value")):
                problems.append(f"{path.name}:{n}: claim ID {found.group('value')!r}")
        for found in LINE.finditer(user):
            code, desc = found.group("code"), found.group("desc")
            codes.add(code)
            if descriptions.get(code) != desc:
                problems.append(f"{path.name}:{n}: {code} shown as {desc!r}, not our description")
    return problems, codes, count


def check(paths: Iterable[Path]) -> tuple[list[str], dict[str, int]]:
    curated = load_curated()
    files = files_of(paths)
    problems: list[str] = []
    codes = set(curated.scope)
    records = 0
    for path in files:
        if path.suffix == ".jsonl":
            found, billed, count = record_problems(path, curated.descriptions)
            problems += found
            codes |= billed
            records += count
        if path.name in ("dataset-metadata.json", "kernel-metadata.json"):
            meta = json.loads(path.read_text(encoding="utf-8"))
            if not (meta.get("isPrivate") or meta.get("is_private")):
                problems.append(f"{path}: not private")
    descriptors = cpt_descriptors(codes)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = redact(text, descriptors)[1]
        if hits:
            problems.append(f"{path}: {hits} AMA CPT descriptor text(s)")
        for name, pattern in PII.items():
            if pattern.search(text):
                problems.append(f"{path}: a {name} pattern")
    return problems, {
        "files": len(files),
        "records": records,
        "codes": len(codes),
        "descriptors": len(descriptors),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path)
    problems, counts = check(parser.parse_args().paths)
    print(
        f"{counts['files']} files, {counts['records']} records, {counts['codes']} codes, "
        f"{counts['descriptors']} CPT descriptor texts checked; problems: {len(problems)}"
    )
    for p in problems[:40]:
        print(f"  {p}")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
