"""Generator v3 datasets, Phase 5 (SPEC.md): records, splits, the training mix, statistics and check
packs, from the sheets whose notes passed the gate.

For each passing note:

1. A writer B note gets the noise layer around its verified quotes (writer A notes have it from
   writing; writer C notes keep their own style). The local checks run again on the result.
2. The target gets its exact quotes (`verify.filled_target`).
3. The claim gets the note.
4. The user message is decision_v3's (`render_user_message`).

Every record passes v2's record checks (`check_record_v2`): rules parity, the lookup, the
derivation, and quotes from the notes. Near-duplicates across splits are dropped from train. Each
split is trimmed to its size, keeping the writer mix. Written under <out>/final/:

- `<split>.jsonl` and `<split>_inputs.jsonl`, for train, validation, test_messy and
  test_unseen_style, in v2's record format, so training and the evaluation harness read them as
  they read v2's;
- `train_mix.jsonl`: v2 clean train and v3 messy train at `training_mix`;
- `stats.json`;
- `check_packs/`;
- `handwritten/`: the fact sheets and the writing guide.
"""

import json
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from app.domain.contracts import ContextPackage, IntakeClaim, RulesOutcome
from app.ml.prompt import PROMPT_V3, render_user_message, system_prompt
from app.rules import RULES_VERSION
from training.generate.checks_v2 import check_record_v2
from training.generate.common import DEFAULT_SEED, GENERATED_DIR
from training.generate.decision_dataset_v2 import exact_retriever, lookups_v2
from training.generate.reference import generate_reference
from training.generate.scenarios_v2 import TEST_ONLY_POLICIES, TRAIN_STYLES, ScenarioBuilderV2
from training.generate.v3 import noise
from training.generate.v3.config import OUT_DIR, config, leaks
from training.generate.v3.coverage import below, by_kind, cell_counts, sheet_cells
from training.generate.v3.dataset import TRICKY_OF, latest, load_sheets, read_jsonl, write_jsonl
from training.generate.v3.segments import render
from training.generate.v3.verify import check_note, filled_target, locate, near_duplicates

FINAL_SPLITS = ("train", "validation", "test_messy", "test_unseen_style")
V2_DIR = GENERATED_DIR / "decision_v2"  # the v2 clean data (read only)
DATASET_VERSION = "decision-dataset-v3"


def _noised_model_note(
    sheet: Mapping[str, Any], note: str, spans: Mapping[str, tuple[int, int]], seed: str
) -> tuple[str, dict[str, tuple[int, int]], dict[str, int]]:
    """Writer B: noise around the verified quotes; the spans found again in the new text."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans.values()):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    segments = noise.free_text_segments(note, {f"P{i}": s for i, s in enumerate(merged)})
    noised, report = noise.apply(segments, random.Random(seed), sections=False)
    text, _ = render(noised)
    found: dict[str, tuple[int, int]] = {}
    for fid, (start, end) in sorted(spans.items(), key=lambda kv: kv[1][0]):
        quote = note[start:end]
        position = text.find(quote)
        if position < 0:
            raise ValueError(f"{fid}: quote lost in noise")
        found[fid] = (position, position + len(quote))
    return text, found, dict(report)


def _probe() -> tuple[Any, Any, Any]:
    from app.rules.lcd_edits import supported as r15_supported

    reference = generate_reference(DEFAULT_SEED)[0]
    lookups = lookups_v2()
    retriever = exact_retriever()
    probe = ScenarioBuilderV2(0, TRAIN_STYLES, set(), set(), retriever, reference, lookups)

    def supported(claim: IntakeClaim, index: int) -> bool:
        line = claim.service_lines[index]
        support = probe.rules_reference.diagnosis_support.get(line.procedure_code)
        return support is None or r15_supported(claim, line, support, probe.rules_reference)

    return probe, retriever, (lookups, supported)


def build_record(
    sheet: Mapping[str, Any],
    note: str,
    spans: Mapping[str, tuple[int, int]],
    lookups: Any,  # noqa: ANN401
    meta: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    target, problems = filled_target(sheet, note, spans)
    if problems or target is None:
        raise ValueError("; ".join(problems))
    inputs = sheet["inputs"]
    claim = IntakeClaim.model_validate({**inputs["claim"], "clinical_notes": note})
    rules = RulesOutcome.model_validate(inputs["rules_outcome"])
    context = ContextPackage.model_validate(inputs["context"])
    user = render_user_message(claim, rules, context, lookups, PROMPT_V3)
    record_id = "DV3-" + sheet["sheet_id"].removeprefix("S3")
    labels = sheet["label"]
    metadata = {
        "record_id": record_id,
        "sheet_id": sheet["sheet_id"],
        "split": sheet["split"],
        "claim_id": claim.claim_id,
        "writer": sheet["writer"],
        "dataset_version": DATASET_VERSION,
        "generator_version": sheet["generator_version"],
        "scenario_type": sheet["scenario_type"],
        "policy_ids": sheet["policy_ids"],
        "profiles": sheet["profiles"],
        "unseen_policy": sheet["unseen_policy"],
        "policy_set": config()["policy_set"],
        "prompt_version": PROMPT_V3,
        "rules_version": RULES_VERSION,
        "line_labels": labels["line_labels"],
        "claim_decision": labels["claim_decision"],
        "complexity": labels["complexity"],
        "tricky": sheet["tricky"],
        "top_up": sheet.get("top_up") or [],
        "style": sheet["style"],
        "note_words": len(note.split()),
        "lines": len(claim.service_lines),
        **meta,
    }
    record = {
        "messages": [
            {"role": "system", "content": system_prompt(PROMPT_V3)},
            {"role": "user", "content": user},
            {"role": "assistant", "content": target.model_dump_json()},
        ],
        "metadata": metadata,
    }
    sidecar = {
        "record_id": record_id,
        "claim": claim.model_dump(mode="json"),
        "rules_outcome": inputs["rules_outcome"],
        "context": inputs["context"],
        "target": target.model_dump(mode="json"),
        "authorizations": inputs["authorizations"],
    }
    return record, sidecar


def _balanced_train(
    rows: list[tuple[dict, dict]], sheets: Mapping[str, Mapping[str, Any]]
) -> tuple[list[tuple[dict, dict]], dict[str, Any]]:
    """The training split at `sizes.train` records in all (D-V3-13): every top-up kept, each
    writer at its `writer_mix` share overall, and the natural records cut one at a time, each cut
    the one that brings the tricky-fact types' shares closest to the shares the natural training
    sheets were drawn with (the ±10% rule of 19 Oct), never one that would take a coverage cell
    under its floor. When no record can be cut without that, the split stays larger (reported)."""
    size = config()["sizes"]["train"]
    shares = config()["writer_mix"]["train"]
    floors = config()["top_up"]["floors"]
    natural_drawn = [s for s in sheets.values() if s["split"] == "train" and not s.get("top_up")]
    asked = {
        name: sum(map(has, natural_drawn)) / len(natural_drawn) for name, has in TRICKY_OF.items()
    }
    names = sorted(TRICKY_OF)

    def sheet(row: tuple[dict, dict]) -> Mapping[str, Any]:
        return sheets[row[0]["metadata"]["sheet_id"]]

    def kinds(row: tuple[dict, dict]) -> tuple[bool, ...]:
        return tuple(TRICKY_OF[n](sheet(row)) for n in names)

    topped = [r for r in rows if r[0]["metadata"].get("top_up")]
    natural = [r for r in rows if not r[0]["metadata"].get("top_up")]
    kept = topped + natural
    report: dict[str, Any] = {"records_before": len(kept), "size": size, "cut": 0}
    if len(kept) <= size:
        return kept, report
    counts = [sum(kinds(r)[i] for r in kept) for i in range(len(names))]
    cells = cell_counts(sheet(r) for r in kept)
    writers = Counter(r[0]["metadata"]["writer"] for r in kept)
    wanted = {w: round(size * share) for w, share in shares.items()}
    groups: dict[tuple[str, tuple[bool, ...]], list[tuple[dict, dict]]] = {}
    for row in reversed(natural):  # cut from the end of each group: the last records drawn
        groups.setdefault((row[0]["metadata"]["writer"], kinds(row)), []).append(row)

    def cuttable(row: tuple[dict, dict]) -> bool:
        return all(
            cells[c] - n >= floors[c[0]]
            for c, n in sheet_cells(sheet(row)).items()
            if c[0] in floors
        )

    total = len(kept)
    while total > size:
        excess = {w: writers[w] - wanted.get(w, 0) for w in writers}

        def worst(vector: tuple[bool, ...], left: int = total - 1) -> float:
            return max(
                abs((counts[i] - vector[i]) / left / asked[n] - 1)
                for i, n in enumerate(names)
                if asked[n]
            )

        order = sorted(
            (k for k, v in groups.items() if v),
            key=lambda k: (-excess.get(k[0], 0), worst(k[1]), k),
        )
        chosen = None
        for key in order:
            chosen = next((r for r in reversed(groups[key]) if cuttable(r)), None)
            if chosen is not None:
                groups[key].remove(chosen)
                break
        if chosen is None:  # every record left holds a cell at its floor: stop here
            report["stopped_at_floors"] = True
            break
        for i in range(len(names)):
            counts[i] -= key[1][i]
        cells.subtract(sheet_cells(sheet(chosen)))
        writers[key[0]] -= 1
        total -= 1
        report["cut"] += 1
    left = {id(r) for v in groups.values() for r in v}
    report["records_after"] = total
    report["writers"] = dict(writers)
    return topped + [r for r in natural if id(r) in left], report


def _trim(rows: list[tuple[dict, dict]], split: str) -> list[tuple[dict, dict]]:
    """The split at its size, keeping the writer mix (the training split: `_balanced_train`)."""
    size = config()["sizes"][split]
    shares = config()["writer_mix"][split]
    wanted = {w: round(size * share) for w, share in shares.items()}
    kept: list[tuple[dict, dict]] = []
    taken: Counter[str] = Counter()
    for record, sidecar in rows:
        writer = record["metadata"]["writer"]
        if taken[writer] < wanted.get(writer, 0):
            kept.append((record, sidecar))
            taken[writer] += 1
    for record, sidecar in rows:  # a writer short of its share: the other fills the split
        if len(kept) >= size:
            break
        if (record, sidecar) not in kept:
            kept.append((record, sidecar))
    return kept[:size]


def build(out_dir: Path = OUT_DIR, v2_dir: Path = V2_DIR) -> dict[str, Any]:
    sheets = load_sheets(out_dir)
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    gate = {g["sheet_id"]: g for g in read_jsonl(out_dir / "gate.jsonl")}
    verifier = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(out_dir / "verifier.jsonl")}
    probe, retriever, (lookups, supported) = _probe()
    curated = load_curated(config()["policy_set"])

    def render_v3(claim: IntakeClaim, rules: RulesOutcome, context: ContextPackage) -> str:
        return render_user_message(claim, rules, context, lookups, PROMPT_V3)

    by_split: dict[str, list[tuple[dict, dict]]] = {s: [] for s in FINAL_SPLITS}
    dropped: Counter[str] = Counter()
    noise_totals: Counter[str] = Counter()
    for sheet_id, result in sorted(gate.items()):
        sheet = sheets[sheet_id]
        note_row = notes.get(sheet_id)
        if sheet["split"] not in by_split or not result["passed"] or note_row is None:
            continue
        if note_row["attempt"] != result["attempt"]:
            continue
        note = note_row["note"]
        spans = {k: tuple(v) for k, v in result["spans"].items()}
        report = dict(note_row.get("noise") or {})
        if sheet["writer"] == "B":
            try:
                note, spans, report = _noised_model_note(
                    sheet, note, spans, f"{sheet['seed']}-b{note_row['attempt']}-noise"
                )
            except ValueError:
                dropped["noise lost a quote"] += 1
                continue
            answers = (verifier.get((sheet_id, note_row["attempt"])) or {}).get("answers") or {}
            again = check_note(sheet, note, spans, {k: None for k in answers})
            if again.failures:
                dropped["noise broke a check"] += 1
                continue
        if leaks(note):
            dropped["leakage after noise"] += 1
            continue
        noise_totals.update(report)
        try:
            record, sidecar = build_record(
                sheet,
                note,
                spans,
                lookups,
                {"noise": report, "attempt": note_row["attempt"], "model": note_row.get("model")},
            )
        except ValueError:
            dropped["target"] += 1
            continue
        excluded = set() if sheet["split"].startswith("test") else set(TEST_ONLY_POLICIES)

        def lookup(plan_id: str, code: str, day, excluded: set[str] = excluded):  # noqa: ANN001, ANN202
            return retriever.retrieve("", plan_id, day, code, excluded)

        problems = check_record_v2(
            sidecar,
            record["messages"],
            curated,
            lookup=lookup,
            engine=probe.engine,
            supported=supported,
            render=render_v3,
        )
        if problems:
            dropped["record check: " + problems[0][:60]] += 1
            continue
        by_split[sheet["split"]].append((record, sidecar))
    texts = {
        split: {r["metadata"]["record_id"]: s["claim"]["clinical_notes"] for r, s in rows}
        for split, rows in by_split.items()
    }
    duplicates = near_duplicates(texts)
    drop_ids = set()
    for a, b, _ in duplicates:
        train_side = [x for x in (a, b) if x in texts["train"]]
        drop_ids.add(train_side[0] if train_side else b)
    final = {}
    for split, rows in by_split.items():
        rows = [(r, s) for r, s in rows if r["metadata"]["record_id"] not in drop_ids]
        if split == "train":
            final[split], trim_report = _balanced_train(rows, sheets)
        else:
            final[split] = _trim(rows, split)
    folder = out_dir / "final"
    for split, rows in final.items():
        write_jsonl(folder / f"{split}.jsonl", [r for r, _ in rows])
        write_jsonl(folder / f"{split}_inputs.jsonl", [s for _, s in rows])
    test_notes = {
        r["metadata"]["record_id"]: s["claim"]["clinical_notes"]
        for split in ("test_messy", "test_unseen_style")
        for r, s in final[split]
    }
    mix, mix_report = training_mix(
        [r for r, _ in final["train"]], v2_dir, out_dir / "v2_extra", test_notes
    )
    write_jsonl(folder / "train_mix.jsonl", mix)
    stats = statistics(out_dir, final, dropped, duplicates, noise_totals)
    stats["training_mix"] = mix_report
    stats["training_trim"] = trim_report
    floors = config()["top_up"]["floors"]
    train_counts = cell_counts(sheets[r["metadata"]["sheet_id"]] for r, _ in final["train"])
    universe = cell_counts(s for s in sheets.values() if s["split"] == "train")
    for cell in universe:  # a cell the sheets hold but no final record does counts as zero
        train_counts.setdefault(cell, 0)
    stats["coverage"] = {
        "floors": floors,
        "cells": len(train_counts),
        "cells_under_floor": {
            f"{k} {n}": train_counts[(k, n)] for (k, n) in below(train_counts, floors)
        },
        "by_kind": by_kind(train_counts),
    }
    (folder / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    from training.generate.v3.packs import check_packs, handwritten_pack

    check_packs(folder, final, sheets)
    handwritten_pack(folder, [s for s in sheets.values() if s["writer"] == "H"])
    return {
        "sizes": {s: len(r) for s, r in final.items()},
        "train_mix": mix_report,
        "cells_under_floor": len(stats["coverage"]["cells_under_floor"]),
        "training_trim": trim_report,
        "dropped": dict(dropped),
        "near_duplicates": len(duplicates),
    }


def training_mix(
    v3_train: Sequence[dict], v2_dir: Path, extra_dir: Path, test_notes: Mapping[str, str]
) -> tuple[list[dict], dict[str, Any]]:
    """v2 clean train records and v3 messy train records at `training_mix`, shuffled: every v2
    training record, then the extra v2-style ones (D-V3-7) as many as the shares need, without any
    that is a near-duplicate of a v3 test note."""
    shares = config()["training_mix"]
    want_v2 = round(len(v3_train) * shares["v2_clean"] / shares["v3_messy"])
    v2 = read_jsonl(v2_dir / "train.jsonl")
    extra_path = extra_dir / "train.jsonl"
    extra = read_jsonl(extra_path) if extra_path.exists() else []
    inputs = read_jsonl(v2_dir / "train_inputs.jsonl")
    if extra_path.exists():
        inputs += read_jsonl(extra_dir / "train_inputs.jsonl")
    notes = {i["record_id"]: i["claim"]["clinical_notes"] for i in inputs}
    near = {a for a, _, _ in near_duplicates({"v2": notes, "test": dict(test_notes)})}
    v2 = [r for r in v2 if r["metadata"]["record_id"] not in near]
    extra = [r for r in extra if r["metadata"]["record_id"] not in near]
    rng = random.Random(config()["seed"])
    chosen = rng.sample(v2, min(want_v2, len(v2)))
    chosen += rng.sample(extra, min(want_v2 - len(chosen), len(extra)))
    extra_ids = {e["metadata"]["record_id"] for e in extra}
    mix = [*chosen, *v3_train]
    rng.shuffle(mix)
    return mix, {
        "v3_records": len(v3_train),
        "v2_records": len(chosen),
        "v2_from_extra": sum(r["metadata"]["record_id"] in extra_ids for r in chosen),
        "v2_wanted": want_v2,
        "v2_near_duplicates_of_v3_tests": len(near),
        "records": len(mix),
        "v2_share": round(len(chosen) / max(1, len(mix)), 3),
    }


def statistics(
    out_dir: Path,
    final: Mapping[str, Sequence[tuple[dict, dict]]],
    dropped: Mapping[str, int],
    duplicates: Sequence[tuple[str, str, float]],
    noise_totals: Mapping[str, int],
) -> dict[str, Any]:
    def quantiles(values: Sequence[int]) -> dict[str, int]:
        ordered = sorted(values)
        if not ordered:
            return {}
        return {
            "min": ordered[0],
            "p50": ordered[len(ordered) // 2],
            "p90": ordered[int(0.9 * (len(ordered) - 1))],
            "max": ordered[-1],
        }

    notes = read_jsonl(out_dir / "notes.jsonl")
    gate = read_jsonl(out_dir / "gate.jsonl")
    attempts = Counter((n["writer"], n["attempt"]) for n in notes)
    passed_at = Counter((g["writer"], g["attempt"]) for g in gate if g["passed"])
    out: dict[str, Any] = {
        "splits": {},
        "dropped": dict(dropped),
        "near_duplicates": len(duplicates),
    }
    count = sum(len(rows) for rows in final.values()) or 1
    out["noise_per_note"] = {k: round(v / count, 3) for k, v in sorted(noise_totals.items())}
    out["verification"] = {
        "notes_written_by_writer_and_attempt": {
            f"{w} {a}": n for (w, a), n in sorted(attempts.items())
        },
        "passed_by_writer_and_attempt": {f"{w} {a}": n for (w, a), n in sorted(passed_at.items())},
    }
    for split, rows in final.items():
        records = [r for r, _ in rows]
        meta = [r["metadata"] for r in records]
        out["splits"][split] = {
            "records": len(records),
            "writers": dict(Counter(m["writer"] for m in meta)),
            "note_words": quantiles([m["note_words"] for m in meta]),
            "record_characters": quantiles(
                [sum(len(x["content"]) for x in r["messages"]) for r in records]
            ),
            "lines_per_claim": dict(sorted(Counter(m["lines"] for m in meta).items())),
            "claim_decisions": dict(Counter(m["claim_decision"] for m in meta)),
            "line_decisions": dict(
                Counter(
                    f"{label['source']} {label['decision']}"
                    for m in meta
                    for label in m["line_labels"]
                )
            ),
            "scenarios": dict(sorted(Counter(m["scenario_type"] for m in meta).items())),
            "tricky": dict(Counter(t for m in meta for t in m["tricky"])),
            "unseen_policy_records": sum(m["unseen_policy"] for m in meta),
        }
    return out


def locate_all(note: str, quotes: Mapping[str, str]) -> dict[str, tuple[int, int] | None]:
    return {fid: locate(note, q) for fid, q in quotes.items()}
