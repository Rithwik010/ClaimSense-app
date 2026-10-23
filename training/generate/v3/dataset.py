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
import hashlib
import json
import math
import random
import shutil
import zlib
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from training.generate.common import DEFAULT_SEED
from training.generate.decision_dataset_v2 import exact_retriever, lookups_v2
from training.generate.reference import generate_reference
from training.generate.scenarios import ScenarioError
from training.generate.scenarios_v2 import TEST_ONLY_POLICIES, reference_dicts
from training.generate.v3 import noise, writer_a
from training.generate.v3.config import OUT_DIR, borderlines, config, leaks
from training.generate.v3.coverage import NO_CRITERIA, Cell, cell_counts, policy_of, sheet_cells
from training.generate.v3.facts import ScenarioBuilderV3
from training.generate.v3.llm import (
    clean_note,
    neutral_words,
    parse_judge,
    parse_verifier,
    statements,
)
from training.generate.v3.segments import render
from training.generate.v3.sheets import fact_sheet
from training.generate.v3.verify import check_note, filled_target
from training.generate.v3.visits import over_limit_lines, usage_index

SPLITS = ("train", "validation", "test_messy", "test_unseen_style", "handwritten")
CODES = {
    "train": "TR",
    "validation": "VA",
    "test_messy": "TM",
    "test_unseen_style": "TU",
    "handwritten": "HW",
}
TOP_UP_CODE = "TP"  # top-up sheets: training split only (D-V3-6)
TARGETED_CODE = "TQ"  # round 4: writer B sheets for the cells and tricky types still short
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


class SheetMaker:
    """Builds fact sheets the way every split does, and drops a claim whose line would go beyond
    its plan's visit limit (D-V3-8)."""

    def __init__(self, seed: int) -> None:
        cfg = config()
        self.seed = seed
        self.reference = generate_reference(DEFAULT_SEED)[0]
        self.lookups = lookups_v2()
        self.retriever = exact_retriever()
        self.curated = load_curated(cfg["policy_set"])
        self.train_policies = set(self.curated.policies) - TEST_ONLY_POLICIES
        self.plan_of = {m["member_id"]: m["plan_id"] for m in self.reference.members}
        self.usage = usage_index(reference_dicts(self.reference.visit_usage))
        self.visit_drops: Counter[str] = Counter()

    def builder(self, offset: int, policies: set[str], excluded: set[str]) -> ScenarioBuilderV3:
        return ScenarioBuilderV3(
            self.seed + offset,
            ("A", "B"),
            policies,
            excluded,
            self.retriever,
            self.reference,
            self.lookups,
        )

    def sheet(
        self,
        b: ScenarioBuilderV3,
        scenario_type: str,
        split: str,
        code: str,
        number: int,
        writer: str,
        unseen: bool = False,
    ) -> dict[str, Any] | None:
        """One sheet, or None: a scenario the builder cannot make, or one over a visit limit."""
        try:
            scenario = b.build(scenario_type, f"CLM-V3{code}-{number:05d}")
        except ScenarioError:
            return None
        sheet = fact_sheet(
            scenario,
            b.draft,
            self.lookups,
            sheet_id=f"S3{code}-{number:05d}",
            split=split,
            writer=writer,
            seed=f"{self.seed}-{split}-{code}-{number}",
            unseen_policy=unseen,
        )
        inputs = sheet["inputs"]
        if over_limit_lines(
            inputs["claim"], inputs["rules_outcome"], self.plan_of, self.usage, self.curated
        ):
            self.visit_drops[split] += 1
            return None
        return sheet


def build_sheets(
    seed: int,
    out_dir: Path = OUT_DIR,
    limit: int | None = None,
    sizes: Mapping[str, int] | None = None,
    top_up: bool = False,
) -> dict[str, Any]:
    """Every split's fact sheets; `limit`: at most that many per split (a pilot); `sizes`: exact
    counts for the splits given, and none for the others (scripts/verify/v3_coverage.py);
    `top_up`: then top up the training split until every cell reaches its floor (D-V3-6)."""
    cfg = config()
    maker = SheetMaker(seed)
    weights = dict(cfg["scenario_weights"])
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
                b = maker.builder(offset * 10 + 1, set(TEST_ONLY_POLICIES), set())
                allowed = {t: w for t, w in weights.items() if t not in UNSEEN_SKIP}
            else:
                excluded = set() if split in TEST_SPLITS else set(TEST_ONLY_POLICIES)
                b = maker.builder(offset * 10, maker.train_policies, excluded)
                allowed = dict(weights)
            made, failures = 0, Counter()
            while made < wanted:
                scenario_type = rng.choices(list(allowed), weights=list(allowed.values()))[0]
                sheet = maker.sheet(
                    b, scenario_type, split, CODES[split], number, writers[number], kind == "unseen"
                )
                if sheet is None:
                    failures[scenario_type] += 1
                    if failures[scenario_type] > 200:
                        allowed.pop(scenario_type, None)
                    continue
                sheets.append(sheet)
                number += 1
                made += 1
        counts[split] = number
    report: dict[str, Any] = {"sheets": counts}
    if top_up:
        extra, report["top_up"] = top_up_sheets(maker, sheets)
        sheets += extra
        counts["train_top_up"] = len(extra)
    report["visit_limit_drops"] = dict(maker.visit_drops)
    write_jsonl(out_dir / "sheets.jsonl", sheets)
    (out_dir / "sheets_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


# --- Top-ups: the training split until every cell reaches its floor (D-V3-6) ---------------------

DECISION_TYPES = {
    "APPROVE": ("approve_single", "same_profile_multi"),
    "DENY": ("deny_criterion", "deny_exclusion"),
    "PEND": ("pend_missing",),
}
STATUS_TYPES = {
    "MET": ("approve_single", "same_profile_multi", "deny_criterion"),
    "NOT_MET": ("deny_criterion", "deny_exclusion", "approve_single"),
    "NOT_DOCUMENTED": ("pend_missing",),
}
TRICKY_TYPES = {
    "missing": ("pend_missing",),
    "hedged": ("pend_missing",),
    "negated": ("approve_single", "deny_criterion"),
    "borderline": ("approve_single", "deny_criterion"),
}
SIDE_TYPES = {"above": ("approve_single", "same_profile_multi"), "below": ("deny_criterion",)}


def cell_policy(cell: Cell) -> str:
    name = cell[1]
    return NO_CRITERIA if name.startswith(NO_CRITERIA) else policy_of(name.split()[0])


def cell_types(
    cell: Cell, weights: Mapping[str, float], seen: Mapping[Cell, Counter[str]]
) -> dict[str, float]:
    """The scenario types most likely to add to a cell: the types of the natural training sheets
    that hold it, by how often; else the types its label points to; else all of them."""
    if seen.get(cell):
        return {t: float(n) for t, n in seen[cell].items() if t in weights}
    kind, name = cell
    last = name.split()[-1]
    hints: tuple[str, ...] = ()
    if kind == "policy_decision":
        hints = DECISION_TYPES.get(last, ())
        if name.startswith(NO_CRITERIA):
            hints = ("office_visit", "office_same_day", "office_plus_procedure")
    elif kind == "criterion_status":
        hints = STATUS_TYPES.get(last, ())
    elif kind == "tricky":
        hints = TRICKY_TYPES.get(last, ())
    elif kind == "borderline":
        hints = SIDE_TYPES.get(last, ())
    found = {t: weights[t] for t in hints if t in weights}
    return found or dict(weights)


def cell_universe(train: list[Mapping[str, Any]], policies: set[str]) -> set[Cell]:
    """The cells to fill: every cell the natural training sheets hold, and both sides of every
    borderline criterion of a training policy (a side may not occur naturally at all)."""
    found = set(cell_counts(train))
    for criterion_id, borderline in borderlines().items():
        if policy_of(criterion_id) not in policies:
            continue
        for side in ("above", "below"):
            if any(getattr(form, side) for form in borderline.forms):
                found.add(("borderline", f"{criterion_id} {side}"))
    return found


def top_up_sheets(
    maker: SheetMaker,
    sheets: list[dict[str, Any]],
    counted: list[dict[str, Any]] | None = None,
    code: str = TOP_UP_CODE,
    writer: str | None = None,
    tag: str = "top-up",
    offset_base: int = 500,
    weight: float = 1.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Training sheets for the cells under their floor (plus the cushion), thinnest cell first:
    sheets of the cell's policy, from the scenario types likely to add to it, kept only when
    they add to a cell still short. Validation and test splits are not touched. `counted`: the
    sheets whose cells count (default: every training sheet; round 4: the training notes that pass
    the gate); `writer`: every new sheet's writer (default: the training mix); `code`, `tag` and
    `offset_base` keep a later top-up's sheets and scenarios apart from an earlier one's;
    `weight`: what a new sheet adds to its cells (a note expected to pass the gate at that rate)."""
    cfg = config()["top_up"]
    weights = dict(config()["scenario_weights"])
    targets = {k: math.ceil(v * (1 + cfg["cushion"])) for k, v in cfg["floors"].items()}
    train = [s for s in sheets if s["split"] == "train"]
    counts = cell_counts(train if counted is None else counted)
    seen: dict[Cell, Counter[str]] = {}
    for sheet in train:
        for cell in sheet_cells(sheet):
            seen.setdefault(cell, Counter())[sheet["scenario_type"]] += 1
    universe = cell_universe(train, maker.train_policies)
    short = {c for c in universe if counts.get(c, 0) < targets[c[0]]}
    report = {
        f"{kind} {name}": {
            "floor": cfg["floors"][kind],
            "target": targets[kind],
            "before": counts.get((kind, name), 0),
            "top_up_sheets": 0,
            "attempts": 0,
        }
        for kind, name in sorted(short)
    }
    rng = random.Random(f"{maker.seed}-{tag}")
    builders: dict[str, ScenarioBuilderV3] = {}
    added: list[dict[str, Any]] = []
    while short:
        cell = min(short, key=lambda c: (counts.get(c, 0) / targets[c[0]], c))
        policy = cell_policy(cell)
        if policy not in builders:
            policies = maker.train_policies if policy == NO_CRITERIA else {policy}
            offset = offset_base + zlib.crc32(policy.encode()) % 10000
            builders[policy] = maker.builder(offset, policies, set(TEST_ONLY_POLICIES))
        allowed = cell_types(cell, weights, seen)
        entry = report[f"{cell[0]} {cell[1]}"]
        failures: Counter[str] = Counter()
        while cell in short and entry["attempts"] < cfg["max_attempts_per_cell"]:
            entry["attempts"] += 1
            scenario_type = rng.choices(list(allowed), weights=list(allowed.values()))[0]
            mix = config()["writer_mix"]["train"]["A"]
            chosen = writer or ("A" if rng.random() < mix else "B")
            sheet = maker.sheet(builders[policy], scenario_type, "train", code, len(added), chosen)
            if sheet is None:
                failures[scenario_type] += 1
                if failures[scenario_type] > 200 and len(allowed) > 1:
                    allowed.pop(scenario_type)
                elif failures[scenario_type] > 200:  # nothing this policy can build: all types
                    allowed = {t: w for t, w in weights.items() if failures[t] <= 200}
                    if not allowed:
                        break
                continue
            cells = sheet_cells(sheet)
            helped = sorted(c for c in cells if c in short)
            if not helped:
                continue
            sheet["top_up"] = [f"{k} {n}" for k, n in helped]
            added.append(sheet)
            for c, n in cells.items():
                counts[c] += n * weight
            for c in helped:
                report[f"{c[0]} {c[1]}"]["top_up_sheets"] += 1
                if counts[c] >= targets[c[0]]:
                    short.discard(c)
        short.discard(cell)  # reached, or not reachable within the attempts
    for key, entry in report.items():
        kind, name = key.split(" ", 1)
        entry["after"] = counts.get((kind, name), 0)
        entry["reached_floor"] = entry["after"] >= entry["floor"]
    return added, {
        "sheets": len(added),
        "cells_short_before": len(report),
        "cells_under_floor_after": sum(not e["reached_floor"] for e in report.values()),
        "cells": report,
    }


TRICKY_OF = {  # the tricky-fact types of the team's ±10% rule (19 Oct), per sheet
    "negation": lambda s: "negation" in s["tricky"],
    "history": lambda s: bool(s["distractors"].get("past")),
    "uncertainty": lambda s: "uncertainty" in s["tricky"],
    "contradiction": lambda s: "contradiction" in s["tricky"],
    "borderline": lambda s: "borderline" in s["tricky"],
}


def passing_training(out_dir: Path = OUT_DIR) -> list[dict[str, Any]]:
    """The training sheets whose latest note passes the gate (gate.jsonl)."""
    sheets = load_sheets(out_dir)
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    return [
        sheets[g["sheet_id"]]
        for g in read_jsonl(out_dir / "gate.jsonl")
        if g["passed"]
        and sheets[g["sheet_id"]]["split"] == "train"
        and notes.get(g["sheet_id"], {}).get("attempt") == g["attempt"]
    ]


def targeted_sheets(
    out_dir: Path = OUT_DIR, pass_rate: float = 0.75, aim: float = 1.0
) -> dict[str, Any]:
    """Round 4 (team decision of 19 Oct: gaps closed with writer B first): writer B training
    sheets (TARGETED_CODE) for (1) the coverage cells under their floor on the training notes
    that pass the gate, then (2) each tricky-fact type whose share among those notes is under
    `aim` times its share among the training sheets drawn without a top-up, until the expected
    share reaches it. A new sheet counts at `pass_rate`, the share of its notes expected to pass.
    Appended to sheets.jsonl."""
    sheets = list(load_sheets(out_dir).values())
    passing = passing_training(out_dir)
    maker = SheetMaker(config()["seed"])
    added, cells = top_up_sheets(
        maker, sheets, passing, TARGETED_CODE, "B", "targeted-r4", 20000, pass_rate
    )
    natural = [s for s in sheets if s["split"] == "train" and not s.get("top_up")]
    rng = random.Random(f"{maker.seed}-targeted-r4-tricky")
    weights = dict(config()["scenario_weights"])
    b = maker.builder(30000, maker.train_policies, set(TEST_ONLY_POLICIES))
    tricky: dict[str, Any] = {}
    for name, has in sorted(TRICKY_OF.items()):
        asked = sum(map(has, natural)) / len(natural)

        def expected(name_has=has) -> tuple[float, float]:
            n = len(passing) + pass_rate * len(added)
            c = sum(map(name_has, passing)) + pass_rate * sum(map(name_has, added))
            return c, n

        c, n = expected()
        entry = {"asked": round(asked, 4), "before": round(c / n, 4), "sheets": 0, "draws": 0}
        while c / n < aim * asked and entry["draws"] < 200000:
            entry["draws"] += 1
            scenario_type = rng.choices(list(weights), weights=list(weights.values()))[0]
            sheet = maker.sheet(b, scenario_type, "train", TARGETED_CODE, len(added), "B")
            if sheet is None or not has(sheet):
                continue
            sheet["top_up"] = [f"tricky type {name}"]
            added.append(sheet)
            entry["sheets"] += 1
            c, n = expected()
        entry["expected_after"] = round(c / n, 4)
        tricky[name] = entry
    with (out_dir / "sheets.jsonl").open("a", encoding="utf-8") as f:
        for sheet in added:
            f.write(json.dumps(sheet, ensure_ascii=False) + "\n")
    report = {
        "sheets_added": len(added),
        "for_cells": cells["sheets"],
        "cells_short_before": cells["cells_short_before"],
        "cells_still_short_expected": cells["cells_under_floor_after"],
        "tricky": tricky,
        "short_cells": {k: v for k, v in cells["cells"].items() if not v["reached_floor"]},
    }
    (out_dir / "targeted_r4.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def fix_leads(out_dir: Path = OUT_DIR) -> dict[str, Any]:
    """The lead-line rule on the sheets already drawn (D-V3-14, phrases/leads.yaml): each sheet
    whose lead states part of a criterion it marks missing gets the neutral lead, and its note so
    far is failed at the gate (`lead_fixes.json`) so that it is written again. sheets.jsonl is kept
    as sheets_before_lead_fix.jsonl first."""
    from training.generate.v3.sheets import safe_lead

    rows = read_jsonl(out_dir / "sheets.jsonl")
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    gate = {g["sheet_id"]: g for g in read_jsonl(out_dir / "gate.jsonl")}
    fixes_path = out_dir / "lead_fixes.json"
    fixes = json.loads(fixes_path.read_text()) if fixes_path.exists() else {}
    found: Counter[str] = Counter()
    for sheet in rows:
        lead, replaced = safe_lead(sheet.get("lead") or {}, sheet["facts"])
        if not replaced:
            continue
        note = notes.get(sheet["sheet_id"])
        g = gate.get(sheet["sheet_id"])
        state = (
            "no note"
            if note is None
            else (
                "passed" if g and g["passed"] and g["attempt"] == note["attempt"] else "not passed"
            )
        )
        found[f"{sheet['split']} {sheet['writer']} {state}"] += 1
        fixes[sheet["sheet_id"]] = {
            "attempt": note["attempt"] if note else 0,
            "old": sheet["lead"],
            "new": lead,
        }
        sheet["lead"] = lead
    if found:
        shutil.copy(out_dir / "sheets.jsonl", out_dir / "sheets_before_lead_fix.jsonl")
        write_jsonl(out_dir / "sheets.jsonl", rows)
        fixes_path.write_text(json.dumps(fixes, indent=1) + "\n")
    return {
        "sheets_fixed": sum(found.values()),
        "by_split_writer_state": dict(sorted(found.items())),
    }


def lead_fixed(out_dir: Path = OUT_DIR) -> dict[str, int]:
    """{sheet: the last note attempt written with the old lead} (fix_leads)."""
    path = out_dir / "lead_fixes.json"
    return (
        {k: v["attempt"] for k, v in json.loads(path.read_text()).items()} if path.exists() else {}
    )


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
    old_lead = lead_fixed(out_dir)
    found = {}
    for sheet_id, sheet in sheets.items():
        if sheet["writer"] == "H":
            continue
        note = notes.get(sheet_id)
        if note is None:
            found[sheet_id] = 1
            continue
        result = gate.get(sheet_id)
        failed = result and not result["passed"] and not result.get("pending")
        if failed and result["attempt"] == note["attempt"]:
            if note["attempt"] < limit or note["attempt"] == old_lead.get(sheet_id):
                found[sheet_id] = note["attempt"] + 1  # a lead fix gets one more attempt
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
    """The notebook's outputs: model notes (writers B and C) and verifier answers. The jobs are in
    <round>/dataset/; `kaggle kernels output -p <round>/output` keeps the notebook's own output/
    folder, so the files are found wherever they landed under <round>/output/. A round is ingested
    once (<round>/ingested.json)."""
    marker = round_dir / "ingested.json"
    if marker.exists():
        raise SystemExit(f"{round_dir.name} was ingested already: {marker.read_text()}")
    sheets = load_sheets(out_dir)
    jobs = {j["job_id"]: j for j in read_jsonl(round_dir / "dataset" / "writers.jsonl")}
    jobs |= {j["job_id"]: j for j in read_jsonl(round_dir / "dataset" / "verify.jsonl")}

    def output(name: str) -> Path:
        found = sorted((round_dir / "output").rglob(name))
        return found[0] if found else round_dir / "output" / name

    notes, answers, looks, broken = [], [], [], 0
    for row in read_jsonl(output("notes_out.jsonl")):
        job = jobs[row["job_id"]]
        text, neutral = neutral_words(clean_note(row["text"]))
        notes.append(
            {
                "sheet_id": job["sheet_id"],
                "attempt": job["attempt"],
                "writer": job["writer"],
                "note": text,
                "neutral_words": neutral,
                "spans": None,
                "noise": {},
                "model": row.get("model"),
                "revision": row.get("revision"),
                "finish_reason": row.get("finish_reason"),
            }
        )
    for row in read_jsonl(output("verifier_out.jsonl")):
        job = jobs.get(row["job_id"]) or {}
        sheet_id, attempt = row["sheet_id"], row["attempt"]
        if row["job_id"].startswith(("look-", "judge-")):  # second looks: after the answers
            looks.append(row)
            continue
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
    first = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(out_dir / "verifier.jsonl")}
    first |= {(a["sheet_id"], a["attempt"]): a for a in answers}
    run = json.loads((round_dir / "dataset" / "run.json").read_text())
    judge_prompt = hashlib.sha256(
        (run.get("judge_system", "") + run.get("judge_user", "")).encode()
    ).hexdigest()[:8]
    second = []
    for row in looks:
        kind, fact_id = row["job_id"].split("-", 1)[0], row["job_id"].rsplit(":", 1)[1]
        error = None
        try:
            if kind == "judge":  # yes: the finding stands, on the passage the verifier cited
                cited = (first.get((row["sheet_id"], row["attempt"])) or {}).get("answers") or {}
                quote = cited.get(fact_id) if parse_judge(row["text"]) else None
            else:
                quote = parse_verifier(row["text"]).get(1)
        except ValueError as exc:
            broken += 1
            quote, error = None, str(exc)
        second.append(
            {
                "sheet_id": row["sheet_id"],
                "attempt": row["attempt"],
                "fact_id": fact_id,
                "source": kind,
                **({"prompt": judge_prompt} if kind == "judge" else {}),
                "quote": quote,
                "error": error,
                "model": row.get("model"),
            }
        )
    found = {
        "notes": append_jsonl(out_dir / "notes.jsonl", notes),
        "verifier": append_jsonl(out_dir / "verifier.jsonl", answers),
        "second_looks": append_jsonl(out_dir / "second_look.jsonl", second),
        "verifier_unparsed": broken,
    }
    marker.write_text(json.dumps(found) + "\n")
    return found


# --- Phase 4: the gate ---------------------------------------------------------------------------


def run_gate(out_dir: Path = OUT_DIR) -> dict[str, Any]:
    """The gate on every sheet's latest note, written to gate.jsonl (`gate_rows`)."""
    results, tallies, reasons = gate_rows(out_dir)
    write_jsonl(out_dir / "gate.jsonl", results)
    return {
        "by_writer_attempt": {k: dict(v) for k, v in sorted(tallies.items())},
        "reasons": dict(reasons),
    }


def second_look_answers(
    out_dir: Path, sheets: Mapping[str, Mapping[str, Any]], ignore: tuple[str, ...] = ()
) -> dict[tuple[str, int], dict[str, str | None]]:
    """{(sheet, attempt): {fact: quote or None}}: each finding's second look (D-V3-12). For a
    missing fact the judge's (the passage it agreed establishes the fact, or None), for an
    exclusion the verifier's own answer when asked about it alone; the latest of each counts,
    and an unreadable one is asked again."""
    found: dict[tuple[str, int], dict[str, str | None]] = {}
    for row in read_jsonl(out_dir / "second_look.jsonl"):
        if row.get("error") is not None or row.get("source", "look") in ignore:
            continue
        facts = {f["fact_id"]: f for f in sheets[row["sheet_id"]]["facts"]}
        wanted = "judge" if facts[row["fact_id"]]["status"] == "missing" else "look"
        if row.get("source", "look") == wanted:
            found.setdefault((row["sheet_id"], row["attempt"]), {})[row["fact_id"]] = row["quote"]
    return found


def gate_rows(
    out_dir: Path = OUT_DIR, ignore: tuple[str, ...] = ()
) -> tuple[list[dict[str, Any]], dict[str, Counter[str]], Counter[str]]:
    """The gate (verify.py) on every sheet's latest note, with the verifier's answers and second
    looks so far; nothing is written. Rows, then statuses by writer and attempt, then failure
    kinds."""
    sheets = load_sheets(out_dir)
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    verifier = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(out_dir / "verifier.jsonl")}
    looks = second_look_answers(out_dir, sheets, ignore)  # `ignore`: second looks to ask again
    old_lead = lead_fixed(out_dir)
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
        result = check_note(
            sheet, note["note"], known, answers, looks.get((sheet_id, note["attempt"]))
        )
        if answer is not None and answers is None:
            result.failures.append(f"verifier answer unreadable: {answer.get('error')}")
            result.verifier_pending = False
        if note["attempt"] <= old_lead.get(sheet_id, 0):
            result.failures.append("lead: written with a lead line that states a missing fact")
        if result.failures:  # a local check failed: the note is rewritten, not sent for verifying
            result.verifier_pending = False
        if not result.failures and not result.verifier_pending and not result.looks:
            _, problems = filled_target(sheet, note["note"], result.spans)
            result.failures += problems
        status = "pending" if result.pending else ("passed" if result.passed else "failed")
        tallies.setdefault(f"{sheet['writer']} attempt {note['attempt']}", Counter())[status] += 1
        for failure in result.failures:
            reasons[_reason_kind(failure)] += 1
        results.append(
            {
                "sheet_id": sheet_id,
                "attempt": note["attempt"],
                "writer": sheet["writer"],
                "passed": result.passed,
                "pending": result.pending,
                "failures": result.failures,
                "looks": result.looks,
                "spans": {k: list(v) for k, v in result.spans.items()},
                "local_spans": result.local_spans,
            }
        )
    return results, tallies, reasons


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
    jobs.add_argument("--round", required=True, help="round label: 4, 3b, ...")
    jobs.add_argument("--limit", type=int, help="pilot: at most N jobs per writer")
    jobs.add_argument(
        "--looks-only",
        action="store_true",
        help="only the second looks the gate is waiting for (from the gate run in memory)",
    )
    jobs.add_argument(
        "--rejudge", action="store_true", help="with --looks-only: every judge's answer again"
    )
    take = sub.add_parser("ingest")
    take.add_argument("--round", required=True)
    sub.add_parser("gate")
    sub.add_parser("targeted", help="round 4: writer B sheets for the cells and tricky types short")
    sub.add_parser("fix-leads", help="the lead-line rule on the sheets drawn (D-V3-14)")
    sub.add_parser("build")
    args = parser.parse_args()
    out = args.out
    if args.command == "sheets":
        report = build_sheets(args.seed, out, args.limit, top_up=args.limit is None)
        print(json.dumps({k: v for k, v in report.items() if k != "top_up"}))
        if "top_up" in report:
            print(json.dumps({k: v for k, v in report["top_up"].items() if k != "cells"}))
    elif args.command == "write-a":
        print(f"writer A notes written: {write_a(out)}")
    elif args.command == "jobs":
        from training.generate.v3.kaggle import prepare_round

        report = prepare_round(
            args.round, args.limit, out, looks_only=args.looks_only, rejudge=args.rejudge
        )
        print(json.dumps(report, indent=2))
    elif args.command == "ingest":
        print(json.dumps(ingest(out / "kaggle" / f"round{args.round}", out)))
    elif args.command == "gate":
        print(json.dumps(run_gate(out), indent=2))
    elif args.command == "targeted":
        print(json.dumps(targeted_sheets(out), indent=2))
    elif args.command == "fix-leads":
        print(json.dumps(fix_leads(out), indent=2))
    elif args.command == "build":
        from training.generate.v3.build import build

        print(json.dumps(build(out), indent=2))


def leak_free(text: str) -> bool:
    return not leaks(text)


if __name__ == "__main__":
    main()
