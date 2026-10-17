"""Generator v3 datasets (Phases 2 to 5; SPEC.md): fact sheets, notes, the gate, the records.

Everything is written under data/generated/v3/ (git-ignored):

- sheets.jsonl: every fact sheet, every split (with the writer each sheet is for);
- notes.jsonl: every note attempt ({sheet_id, attempt, writer, note, spans, noise}); writer A's are
  written here, writers B and C come back from Kaggle (`ingest`);
- verifier.jsonl: the verifier's answers per note attempt ({fact_id: quote or null});
- gate.jsonl: the gate's latest result per sheet;
- kaggle/round<N>/: the private dataset and notebook for one Kaggle round
  (training.generate.v3.kaggle);
- final/: the records per split, the training mix, statistics and the check packs.

    uv run python -m training.generate.v3.dataset sheets
    uv run python -m training.generate.v3.dataset write-a
    uv run python -m training.generate.v3.dataset jobs --round 1
    uv run python -m training.generate.v3.dataset ingest --round 1
    uv run python -m training.generate.v3.dataset gate
    uv run python -m training.generate.v3.dataset build
"""

import argparse
import json
import random
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from training.generate.common import DEFAULT_SEED
from training.generate.decision_dataset_v2 import exact_retriever, lookups_v2
from training.generate.reference import generate_reference
from training.generate.scenarios import ScenarioError
from training.generate.scenarios_v2 import TEST_ONLY_POLICIES
from training.generate.v3 import noise, writer_a
from training.generate.v3.config import OUT_DIR, config, leaks
from training.generate.v3.facts import ScenarioBuilderV3
from training.generate.v3.llm import clean_note, parse_verifier, statements
from training.generate.v3.segments import render
from training.generate.v3.sheets import fact_sheet
from training.generate.v3.verify import check_note, filled_target

SPLITS = ("train", "validation", "test_messy", "test_unseen_style", "handwritten")
CODES = {
    "train": "TR",
    "validation": "VA",
    "test_messy": "TM",
    "test_unseen_style": "TU",
    "handwritten": "HW",
}
TEST_SPLITS = ("test_messy", "test_unseen_style", "handwritten")
UNSEEN_SKIP = ("office_visit", "ncs_without_emg", "facet_two_regions", "extended_testing")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# --- Phase 2: fact sheets -----------------------------------------------------------------------


def split_size(split: str, limit: int | None = None) -> int:
    cfg = config()
    base = cfg["sizes"][split]
    size = base if split == "handwritten" else round(base * (1 + cfg["sizes_margin"]))
    return min(size, limit) if limit is not None else size


def writer_list(split: str, count: int, rng: random.Random) -> list[str]:
    if split == "handwritten":
        return ["H"] * count
    shares = config()["writer_mix"][split]
    writers: list[str] = []
    for writer, share in shares.items():
        writers += [writer] * round(count * share)
    while len(writers) < count:
        writers.append(next(iter(shares)))
    rng.shuffle(writers)
    return writers[:count]


def build_sheets(
    seed: int,
    out_dir: Path = OUT_DIR,
    limit: int | None = None,
    sizes: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """Every split's fact sheets; `limit`: at most that many per split (a pilot); `sizes`: exact
    counts for the splits given, and none for the others (scripts/verify/v3_coverage.py)."""
    cfg = config()
    reference = generate_reference(DEFAULT_SEED)[0]
    lookups = lookups_v2()
    retriever = exact_retriever()
    everything = set(load_curated(cfg["policy_set"]).policies)
    train_policies = everything - TEST_ONLY_POLICIES
    weights = dict(cfg["scenario_weights"])

    def builder(offset: int, policies: set[str], excluded: set[str]) -> ScenarioBuilderV3:
        return ScenarioBuilderV3(
            seed + offset, ("A", "B"), policies, excluded, retriever, reference, lookups
        )

    sheets: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for offset, split in enumerate(SPLITS, start=30):
        rng = random.Random(f"{seed}-v3-{split}")
        count = split_size(split, limit) if sizes is None else sizes.get(split, 0)
        writers = writer_list(split, count, rng)
        unseen = round(count * cfg["test_unseen_policy_share"]) if split in TEST_SPLITS else 0
        plans = [("unseen", unseen), ("seen", count - unseen)]
        number = 0
        for kind, wanted in plans:
            if not wanted:
                continue
            if kind == "unseen":
                b = builder(offset * 10 + 1, set(TEST_ONLY_POLICIES), set())
                allowed = {t: w for t, w in weights.items() if t not in UNSEEN_SKIP}
            else:
                excluded = set() if split in TEST_SPLITS else set(TEST_ONLY_POLICIES)
                b = builder(offset * 10, train_policies, excluded)
                allowed = dict(weights)
            made, failures = 0, Counter()
            while made < wanted:
                scenario_type = rng.choices(list(allowed), weights=list(allowed.values()))[0]
                claim_id = f"CLM-V3{CODES[split]}-{number:05d}"
                try:
                    scenario = b.build(scenario_type, claim_id)
                except ScenarioError:
                    failures[scenario_type] += 1
                    if failures[scenario_type] > 200:
                        allowed.pop(scenario_type, None)
                    continue
                writer = writers[number]
                sheets.append(
                    fact_sheet(
                        scenario,
                        b.draft,
                        lookups,
                        sheet_id=f"S3{CODES[split]}-{number:05d}",
                        split=split,
                        writer=writer,
                        seed=f"{seed}-{split}-{number}",
                        unseen_policy=kind == "unseen",
                    )
                )
                number += 1
                made += 1
        counts[split] = number
    write_jsonl(out_dir / "sheets.jsonl", sheets)
    return counts


def load_sheets(out_dir: Path = OUT_DIR) -> dict[str, dict[str, Any]]:
    return {s["sheet_id"]: s for s in read_jsonl(out_dir / "sheets.jsonl")}


# --- Phase 3: writer A, and what needs writing ---------------------------------------------------


def latest(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """The latest attempt per sheet."""
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = found.get(row["sheet_id"])
        if current is None or row["attempt"] >= current["attempt"]:
            found[row["sheet_id"]] = dict(row)
    return found


def needs_note(out_dir: Path = OUT_DIR) -> dict[str, int]:
    """Sheets that need a new note, with the attempt number: never written, or failed at the gate
    with retries left."""
    sheets = load_sheets(out_dir)
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    gate = {g["sheet_id"]: g for g in read_jsonl(out_dir / "gate.jsonl")}
    limit = config()["verification"]["max_regenerations"] + 1
    found = {}
    for sheet_id, sheet in sheets.items():
        if sheet["writer"] == "H":
            continue
        note = notes.get(sheet_id)
        if note is None:
            found[sheet_id] = 1
            continue
        result = gate.get(sheet_id)
        if result and result["attempt"] == note["attempt"] and not result["passed"]:
            if note["attempt"] < limit:
                found[sheet_id] = note["attempt"] + 1
    return found


def write_a(out_dir: Path = OUT_DIR) -> int:
    sheets = load_sheets(out_dir)
    rows = []
    for sheet_id, attempt in needs_note(out_dir).items():
        sheet = sheets[sheet_id]
        if sheet["writer"] != "A":
            continue
        seed = f"{sheet['seed']}-a{attempt}"
        segments = writer_a.write(sheet, seed)
        noised, report = noise.apply(segments, random.Random(f"{seed}-noise"))
        text, spans = render(noised)
        rows.append(
            {
                "sheet_id": sheet_id,
                "attempt": attempt,
                "writer": "A",
                "note": text,
                "spans": {k: list(v) for k, v in spans.items()},
                "noise": dict(report),
            }
        )
    return append_jsonl(out_dir / "notes.jsonl", rows)


# --- Kaggle rounds -------------------------------------------------------------------------------


def verifier_items(sheet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return statements(sheet)


def ingest(round_dir: Path, out_dir: Path = OUT_DIR) -> dict[str, int]:
    """The notebook's outputs: model notes (writers B and C) and verifier answers."""
    sheets = load_sheets(out_dir)
    jobs = {j["job_id"]: j for j in read_jsonl(round_dir / "writers.jsonl")}
    jobs |= {j["job_id"]: j for j in read_jsonl(round_dir / "verify.jsonl")}
    output = round_dir / "output"
    notes, answers, broken = [], [], 0
    for row in read_jsonl(output / "notes_out.jsonl"):
        job = jobs[row["job_id"]]
        notes.append(
            {
                "sheet_id": job["sheet_id"],
                "attempt": job["attempt"],
                "writer": job["writer"],
                "note": clean_note(row["text"]),
                "spans": None,
                "noise": {},
                "model": row.get("model"),
                "revision": row.get("revision"),
                "finish_reason": row.get("finish_reason"),
            }
        )
    for row in read_jsonl(output / "verifier_out.jsonl"):
        job = jobs.get(row["job_id"]) or {}
        sheet_id, attempt = row["sheet_id"], row["attempt"]
        items = verifier_items(sheets[sheet_id])
        try:
            parsed = parse_verifier(row["text"])
        except ValueError as exc:
            broken += 1
            answers.append({"sheet_id": sheet_id, "attempt": attempt, "error": str(exc)})
            continue
        answers.append(
            {
                "sheet_id": sheet_id,
                "attempt": attempt,
                "answers": {item["fact_id"]: parsed.get(item["id"]) for item in items},
                "model": row.get("model"),
                "job": job.get("job_id"),
            }
        )
    return {
        "notes": append_jsonl(out_dir / "notes.jsonl", notes),
        "verifier": append_jsonl(out_dir / "verifier.jsonl", answers),
        "verifier_unparsed": broken,
    }


# --- Phase 4: the gate ---------------------------------------------------------------------------


def run_gate(out_dir: Path = OUT_DIR) -> dict[str, Any]:
    sheets = load_sheets(out_dir)
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    verifier = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(out_dir / "verifier.jsonl")}
    results = []
    tallies: dict[str, Counter[str]] = {}
    reasons: Counter[str] = Counter()
    for sheet_id, note in notes.items():
        sheet = sheets[sheet_id]
        answer = verifier.get((sheet_id, note["attempt"]))
        answers = None
        if answer is not None:
            answers = answer.get("answers")
        known = {k: tuple(v) for k, v in note["spans"].items()} if note.get("spans") else None
        result = check_note(sheet, note["note"], known, answers)
        if answer is not None and answers is None:
            result.failures.append(f"verifier answer unreadable: {answer.get('error')}")
            result.verifier_pending = False
        if not result.failures and not result.verifier_pending:
            _, problems = filled_target(sheet, note["note"], result.spans)
            result.failures += problems
        status = "pending" if result.verifier_pending else ("passed" if result.passed else "failed")
        tallies.setdefault(f"{sheet['writer']} attempt {note['attempt']}", Counter())[status] += 1
        for failure in result.failures:
            reasons[_reason_kind(failure)] += 1
        results.append(
            {
                "sheet_id": sheet_id,
                "attempt": note["attempt"],
                "writer": sheet["writer"],
                "passed": result.passed,
                "pending": result.verifier_pending,
                "failures": result.failures,
                "spans": {k: list(v) for k, v in result.spans.items()},
            }
        )
    write_jsonl(out_dir / "gate.jsonl", results)
    return {
        "by_writer_attempt": {k: dict(v) for k, v in sorted(tallies.items())},
        "reasons": dict(reasons),
    }


def _reason_kind(failure: str) -> str:
    for key in (
        "not found",
        "not in the note",
        "lacks the values",
        "shorter than",
        "before the copied",
        "fact appears",
        "verifier found",
        "leakage",
        "recomputed",
        "target invalid",
        "evidence guard",
        "unreadable",
        "placeholder",
    ):
        if key in failure:
            return key
    return "other"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="data folder (a pilot's own)")
    sub = parser.add_subparsers(dest="command", required=True)
    sheets = sub.add_parser("sheets")
    sheets.add_argument("--seed", type=int, default=config()["seed"])
    sheets.add_argument("--limit", type=int, help="pilot: at most N sheets per split")
    sub.add_parser("write-a")
    jobs = sub.add_parser("jobs")
    jobs.add_argument("--round", type=int, required=True)
    jobs.add_argument("--limit", type=int, help="pilot: at most N jobs per writer")
    take = sub.add_parser("ingest")
    take.add_argument("--round", type=int, required=True)
    sub.add_parser("gate")
    sub.add_parser("build")
    args = parser.parse_args()
    out = args.out
    if args.command == "sheets":
        print(json.dumps(build_sheets(args.seed, out, args.limit)))
    elif args.command == "write-a":
        print(f"writer A notes written: {write_a(out)}")
    elif args.command == "jobs":
        from training.generate.v3.kaggle import prepare_round

        print(json.dumps(prepare_round(args.round, limit=args.limit, out_dir=out), indent=2))
    elif args.command == "ingest":
        print(json.dumps(ingest(out / "kaggle" / f"round{args.round}", out)))
    elif args.command == "gate":
        print(json.dumps(run_gate(out), indent=2))
    elif args.command == "build":
        from training.generate.v3.build import build

        print(json.dumps(build(out), indent=2))


def leak_free(text: str) -> bool:
    return not leaks(text)


if __name__ == "__main__":
    main()
