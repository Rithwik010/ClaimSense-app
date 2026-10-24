"""Is model v3 ready to train? The team's go / no-go conditions of 23 Oct (D-V3-13). Report only.

From data/generated/v3/ (and the files each item names):

a. the gate bars: none of the 12 really wrong notes of the 19 Oct hand check passes, at least 24
   of the 28 good ones pass (gate_change.json), and at least 38 of the 40 newly passing notes are
   correct (the hand check's verdicts, training/generate/v3/hand_checks/gate_fix.json). That bar
   was not met and D-V3-14 replaced it; item (a) reads the fallback bar (D-V3-16): all 12 really
   wrong notes rejected by the final gate code (scripts/verify/v3_fallback_bar.py);
b. every coverage cell (training/generate/v3/coverage.py) of the training set at its floor, except
   the one cell the team accepted below it (D-V3-18: POL-SURG-001.c4 NOT_MET at 19 of 20);
c. each tricky-fact type within ±10% (relative) of the rate the fact sheets asked for: the share of
   training notes with the type, against its share among the training sheets drawn without a
   top-up (the spec's probabilities, as drawn);
d. sizes: training notes by writer B >= 2,700, unseen-style test >= 150, validation >= 270;
e. no record over the token limit, and the timing run within T4 memory (its training log);
f. the projected training time <= 14 h (the timing run);
g. model v2's macro-F1 on the messy test at least 0.03 under its clean 0.8487.

`--source gate` reads the training notes that pass the gate now (before the build, to plan the
next round); `--source final` (default) reads data/generated/v3/final/train.jsonl.

    uv run python -m scripts.verify.v3_readiness [--source gate] [--out <file>]
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.verify.v3_fallback_bar import fallback_bar
from training.generate.v3.config import OUT_DIR, config
from training.generate.v3.coverage import below, cell_counts
from training.generate.v3.dataset import TRICKY_OF, load_sheets, passing_training, read_jsonl

HAND_CHECKS = Path(__file__).resolve().parents[2] / "training/generate/v3/hand_checks"
V2_CLEAN_MACRO_F1 = 0.8487
TIMING_DIR = OUT_DIR / "timing"
ACCEPTED_UNDER_FLOOR = {"criterion_status POL-SURG-001.c4 NOT_MET": 19}  # D-V3-18
STUDY = OUT_DIR.parent / "eval" / "v3study"


def training_sheets(source: str, out_dir: Path) -> list[dict[str, Any]]:
    if source == "gate":
        return passing_training(out_dir)
    sheets = load_sheets(out_dir)
    rows = read_jsonl(out_dir / "final" / "train.jsonl")
    return [sheets[r["metadata"]["sheet_id"]] for r in rows if r["metadata"].get("sheet_id")]


def tricky_rates(chosen: list[dict[str, Any]], drawn: list[dict[str, Any]]) -> dict[str, Any]:
    natural = [s for s in drawn if s["split"] == "train" and not s.get("top_up")]
    found = {}
    for name, has in TRICKY_OF.items():
        asked = sum(map(has, natural)) / len(natural)
        rate = sum(map(has, chosen)) / len(chosen) if chosen else 0.0
        ratio = rate / asked if asked else None
        found[name] = {
            "asked": round(asked, 4),
            "training_set": round(rate, 4),
            "ratio": round(ratio, 3) if ratio is not None else None,
            "within_10_percent": ratio is not None and 0.9 <= ratio <= 1.1,
        }
    return found


def coverage(chosen: list[dict[str, Any]], drawn: list[dict[str, Any]]) -> dict[str, Any]:
    floors = config()["top_up"]["floors"]
    counts = cell_counts(chosen)
    for cell in cell_counts(s for s in drawn if s["split"] == "train"):
        counts.setdefault(cell, 0)
    short = {f"{k} {n}": counts[(k, n)] for (k, n) in below(counts, floors)}
    unaccepted = {k: v for k, v in short.items() if ACCEPTED_UNDER_FLOOR.get(k) != v}
    accepted = sorted(set(short) - set(unaccepted))
    reading = (
        "met" if not short else "not met: " + ", ".join(f"{k} {v}" for k, v in unaccepted.items())
    )
    if short and not unaccepted:
        reading = "met except " + ", ".join(
            f"{k.split()[1]}, {short[k]} of {floors.get(k.split()[0], 20)}, accepted"
            for k in accepted
        )
    return {
        "cells": len(counts),
        "cells_under_floor": short,
        "all_at_floor": not short,
        "reading": reading,
        "ok": not unaccepted,
    }


def sizes(source: str, chosen: list[dict[str, Any]], out_dir: Path) -> dict[str, Any]:
    found: dict[str, Any] = {"training_by_writer": dict(Counter(s["writer"] for s in chosen))}
    if source == "final":
        for split in ("validation", "test_messy", "test_unseen_style"):
            path = out_dir / "final" / f"{split}.jsonl"
            found[split] = len(read_jsonl(path)) if path.exists() else 0
    found["ok"] = (
        found["training_by_writer"].get("B", 0) >= 2700
        and found.get("test_unseen_style", 0) >= 150
        and found.get("validation", 0) >= 270
    )
    return found


def gate_bars(out_dir: Path) -> dict[str, Any]:
    change = out_dir / "gate_change.json"
    verdicts = HAND_CHECKS / "gate_fix.json"
    if not change.exists() or not verdicts.exists():
        return {"ok": False, "missing": [str(p) for p in (change, verdicts) if not p.exists()]}
    hand = json.loads(change.read_text())["2_hand_check_of_19_oct"]
    wrong_passing = hand["really_wrong_now_passing"]
    good = int(hand["good_now_passing"].split(" of ")[0])
    checked = json.loads(verdicts.read_text())["newly_passing"]
    correct = sum(v["correct"] for v in checked["notes"])
    return {
        "really_wrong_passing": wrong_passing,
        "good_passing": hand["good_now_passing"],
        "newly_passing_correct": f"{correct} of {len(checked['notes'])}",
        "ok": not wrong_passing and good >= 24 and correct >= 38,
    }


def item_a(out_dir: Path) -> dict[str, Any]:
    """The original bar, then the fallback that replaced it (D-V3-14, D-V3-16)."""
    original = gate_bars(out_dir)
    fallback = fallback_bar()
    reading = (
        f"original bar not met ({original.get('good_passing')} good notes passed); replaced by "
        f"D-V3-14; fallback bar: {fallback['rejected']} really-wrong notes rejected"
        if not original["ok"]
        else "original bar met"
    )
    return {
        "original": original,
        "fallback_rejected": fallback["rejected"],
        "reading": reading,
        "ok": original["ok"] or fallback["met"],
    }


def timing(out_dir: Path) -> dict[str, Any]:
    summary = TIMING_DIR / "summary.json"  # scripts/verify/v3_timing.py
    if not summary.exists():
        return {"ok": None, "missing": str(summary)}
    data = json.loads(summary.read_text())
    longest, limit = data.get("longest_record_tokens"), data.get("max_seq_length")
    projected = data.get("projected_full_run_hours")
    return {
        **{k: data.get(k) for k in ("longest_record_tokens", "max_seq_length", "peak_memory_gb")},
        "gpu_total_gb": data.get("gpu_total_gb"),
        "projected_full_run_hours": projected,
        "resume_matches": data.get("resume_matches"),
        "tokens_ok": longest is not None and limit is not None and longest <= limit,
        "memory_ok": bool(data.get("fits_t4_memory")),
        "time_ok": projected is not None and projected <= 14,
    }


def messy_gap() -> dict[str, Any]:
    report = STUDY / "v2-test_messy.json"
    if not report.exists():
        return {"ok": None, "missing": str(report)}
    f1 = json.loads(report.read_text())["guard_on"]["macro_f1"]
    return {
        "v2_messy_macro_f1": f1,
        "v2_clean_macro_f1": V2_CLEAN_MACRO_F1,
        "gap": round(V2_CLEAN_MACRO_F1 - f1, 4),
        "ok": V2_CLEAN_MACRO_F1 - f1 >= 0.03,
    }


def readiness(source: str = "final", out_dir: Path = OUT_DIR) -> dict[str, Any]:
    drawn = list(load_sheets(out_dir).values())
    chosen = training_sheets(source, out_dir)
    report = {
        "source": source,
        "a_gate_bars": item_a(out_dir),
        "b_coverage": coverage(chosen, drawn),
        "c_tricky_rates": tricky_rates(chosen, drawn),
        "d_sizes": sizes(source, chosen, out_dir),
        "e_f_timing": timing(out_dir),
        "g_messy_gap": messy_gap(),
    }
    report["c_all_within_10_percent"] = all(
        v["within_10_percent"] for v in report["c_tricky_rates"].values()
    )
    t = report["e_f_timing"]
    items = {
        "a": report["a_gate_bars"]["ok"],
        "b": report["b_coverage"]["ok"],
        "c": report["c_all_within_10_percent"],
        "d": report["d_sizes"]["ok"],
        "e": None if "missing" in t else bool(t["tokens_ok"] and t["memory_ok"]),
        "f": None if "missing" in t else t["time_ok"],
        "g": report["g_messy_gap"]["ok"],
    }
    report["items"] = items
    report["go"] = all(v is True for v in items.values())
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=("gate", "final"), default="final")
    parser.add_argument("--data", type=Path, default=OUT_DIR)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = readiness(args.source, args.data)
    print(json.dumps(report, indent=2))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
