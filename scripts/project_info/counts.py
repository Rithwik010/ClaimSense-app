"""Counts for docs/PROJECT_INFO.md that are not already in a results file (sections 5 and 7.5).

Read only; every input is a file the project already wrote:

- reason codes: the committed CARC/RARC map (`data/curated/reason_code_map.csv`);
- policies: policy sets v1 and v2 from `data/curated/coverage_policies/` (`load_curated`):
  policies, criteria, criteria by type, test-only policies;
- decision datasets v1 and v2: records, model lines, line and claim decisions per split (the
  generator's `summary.json`) and lines per claim (each record's `line_labels`);
- v3: fact sheets per split (`sheets.jsonl` IDs), the gate's passed, failed and waiting notes per
  split and writer (`gate.jsonl`, with the file's time), the gate fix's before-and-after table
  (`gate_change.json`, with its hand-check lines), the second looks and the judge's answers
  (`second_look.jsonl` against `verifier.jsonl`), the hand check of the fix (`--v3-hand-check`) and
  the preliminary build's records (`final/stats.json`);
- OCR held-out set (`data/generated/eval/ocr/heldout.jsonl`): field accuracy, the five worst
  kinds of field and the five most-missed boxes, and wrong reads at or above the 0.85 confidence
  threshold (the reads that H5 would not catch).

Output (git-ignored): `data/generated/project_info/counts.json`.

    uv run python -m scripts.project_info.counts --main-data ../ClaimSense/data/generated \
        --v3-data ../claimsense-v3/data/generated/v3 \
        --v3-hand-check ../claimsense-v3/training/generate/v3/hand_checks/gate_fix.json
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from training.evaluate.model import read_jsonl

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "generated" / "project_info" / "counts.json"
THRESHOLD = 0.85  # EXTRACTION_CONFIDENCE_MIN
SPLIT_OF_PREFIX = {
    "S3TR": "train",
    "S3TP": "train top-up",
    "S3VA": "validation",
    "S3TM": "test_messy",
    "S3TU": "test_unseen_style",
    "S3HW": "handwritten",
}


def policies() -> dict[str, Any]:
    out = {}
    for policy_set in ("v1", "v2"):
        data = load_curated(policy_set)
        criteria = [c for p in data.policies.values() for c in p.criteria]
        out[policy_set] = {
            "policies": len(data.policies),
            "criteria": len(criteria),
            "by_type": dict(Counter(c.criterion_type or "untyped" for c in criteria)),
            "in_indication_group": sum(1 for c in criteria if c.group),
            "procedure_codes": len(
                {code for p in data.policies.values() for code in p.procedure_codes}
            ),
            "splits": dict(Counter(p.split for p in data.policies.values())),
        }
    return out


def reason_codes() -> dict[str, Any]:
    """The committed CARC/RARC map (`data/curated/reason_code_map.csv`) of this checkout."""
    with (ROOT / "data" / "curated" / "reason_code_map.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {
        "internal_codes": len(rows),
        "by_outcome": dict(Counter(r["outcome"] for r in rows)),
        "by_group_code": dict(Counter(r["group_code"] for r in rows)),
        "with_carc": sum(1 for r in rows if r["carc"]),
        "with_rarc": sum(1 for r in rows if r["rarc"]),
    }


def decision_dataset(folder: Path) -> dict[str, Any]:
    summary = json.loads((folder / "summary.json").read_text())
    out: dict[str, Any] = {
        "generator_version": summary.get("generator_version"),
        "prompt_version": summary.get("prompt_version"),
        "sizes": summary["sizes"],
        "splits": {},
    }
    for split, dist in summary["distribution"].items():
        lines = Counter()
        model_lines = Counter()
        for record in read_jsonl(folder / f"{split}.jsonl"):
            labels = record["metadata"]["line_labels"]
            lines[len(labels)] += 1
            model_lines[sum(1 for x in labels if x["source"] == "MODEL")] += 1
        total_lines = sum(n * k for n, k in lines.items())
        out["splits"][split] = {
            "records": dist["records"],
            "model_lines": dist["model_lines"],
            "lines_denied_by_rules": dist.get("lines_denied_by_rules"),
            "line_decisions": dist["line_decisions"],
            "claim_decisions": dist["claim_decisions"],
            "lines_per_claim": dict(sorted(lines.items())),
            "mean_lines_per_claim": round(total_lines / dist["records"], 2),
            "model_lines_per_claim": dict(sorted(model_lines.items())),
            "note_styles": dist.get("template_sets"),
        }
    return out


def v3(folder: Path) -> dict[str, Any]:
    sheets = Counter()
    with (folder / "sheets.jsonl").open(encoding="utf-8") as f:
        for line in f:
            sheet_id = json.loads(line)["sheet_id"]
            sheets[SPLIT_OF_PREFIX.get(sheet_id[:4], sheet_id[:4])] += 1
    gate: dict[str, Counter] = defaultdict(Counter)
    attempts = Counter()
    for row in read_jsonl(folder / "gate.jsonl"):
        state = "passed" if row["passed"] else ("waiting" if row["pending"] else "failed")
        gate[f"{SPLIT_OF_PREFIX[row['sheet_id'][:4]]} / writer {row['writer']}"][state] += 1
        attempts[row["attempt"]] += 1
    change = json.loads((folder / "gate_change.json").read_text())
    after: dict[str, Counter] = defaultdict(Counter)
    for key, n in change["1_status_before_and_after"].items():
        writer, _, new = key.split(" ")[0], key.split(" ")[1], key.split(" ")[-1]
        after[writer][new] += n

    def mtime(name: str) -> str:
        stamp = (folder / name).stat().st_mtime
        return datetime.fromtimestamp(stamp).astimezone().isoformat(timespec="seconds")

    final = json.loads((folder / "final" / "stats.json").read_text())
    hand = change.get("2_hand_check_of_19_oct", {})
    return {
        "sheets_by_split": dict(sheets),
        "gate_file_time": mtime("gate.jsonl"),
        "gate_by_split_and_writer": {k: dict(v) for k, v in sorted(gate.items())},
        "gate_totals": dict(sum(gate.values(), Counter())),
        "gate_attempts": dict(sorted(attempts.items())),
        "gate_change_file_time": mtime("gate_change.json"),
        "gate_change_after_by_writer": {k: dict(v) for k, v in sorted(after.items())},
        "gate_change_hand_check": {
            "really_wrong_still_failing": hand.get("really_wrong_still_failing"),
            "good_now_passing": hand.get("good_now_passing"),
        },
        "second_looks": second_looks(folder),
        "final_build_time": mtime("final/stats.json"),
        "final_build_records": {k: v["records"] for k, v in final["splits"].items()},
        "kaggle_rounds": {
            p.parent.name: json.loads(p.read_text())
            for p in sorted((folder / "kaggle").glob("*/ingested.json"))
        },
    }


def second_looks(folder: Path) -> dict[str, Any]:
    """The gate's second looks (`second_look.jsonl`): rows without a `source` re-ask the verifier
    about one documented-fact finding (compared with its first quote in `verifier.jsonl`); rows
    with `source` "judge" ask about one missing fact (a quote is a yes, null a no)."""
    first: dict[tuple[str, int, str], Any] = {}
    for row in read_jsonl(folder / "verifier.jsonl"):
        for fact_id, quote in row.get("answers", {}).items():  # 5 rows hold only an error
            first[(row["sheet_id"], row["attempt"], fact_id)] = quote
    rows = read_jsonl(folder / "second_look.jsonl")
    looks = [r for r in rows if r.get("source") != "judge"]
    judge = [r for r in rows if r.get("source") == "judge"]

    def same(r: dict[str, Any]) -> bool:
        before = first.get((r["sheet_id"], r["attempt"], r["fact_id"]))
        return before is not None and " ".join(str(before).split()) == " ".join(
            str(r["quote"]).split()
        )

    return {
        "second_looks": len(looks),
        "second_looks_repeating_the_first_quote": sum(map(same, looks)),
        "judge_checks": len(judge),
        "judge_yes": sum(1 for r in judge if r["quote"] is not None),
        "judge_no": sum(1 for r in judge if r["quote"] is None),
    }


def hand_check(path: Path) -> dict[str, Any]:
    """The main session's hand check of the gate fix (`hand_checks/gate_fix.json`)."""
    data = json.loads(path.read_text())
    notes = data["newly_passing"]["notes"]
    return {
        "checked": data["checked"],
        "newly_passing_notes": data["newly_passing"]["of"],
        "sampled": len(notes),
        "correct_strict": sum(1 for n in notes if n["correct"]),
    }


def ocr(path: Path) -> dict[str, Any]:
    fields = [f for case in read_jsonl(path) for f in case["fields"] if f["written"]]
    wrong = [f for f in fields if not f["correct"]]

    def low(f: dict[str, Any]) -> bool:
        return f["confidence"] is None or f["confidence"] < THRESHOLD

    kinds: dict[str, list[bool]] = defaultdict(list)
    for f in fields:
        kinds[f["kind"]].append(f["correct"])
    by_kind = {k: (round(sum(v) / len(v), 4), len(v)) for k, v in kinds.items()}
    missed = Counter(f["field"] for f in wrong)
    high_wrong = [f for f in wrong if not low(f)]
    return {
        "fields": len(fields),
        "field_accuracy": round(1 - len(wrong) / len(fields), 4),
        "wrong": len(wrong),
        "wrong_below_threshold": len(wrong) - len(high_wrong),
        "wrong_at_or_above_threshold": len(high_wrong),
        "high_confidence_wrong_share_of_fields": round(len(high_wrong) / len(fields), 4),
        "high_confidence_wrong_share_of_wrong": round(len(high_wrong) / len(wrong), 4),
        "high_confidence_wrong_by_kind": dict(Counter(f["kind"] for f in high_wrong)),
        "worst_kinds": sorted(by_kind.items(), key=lambda kv: kv[1][0])[:5],
        "most_missed_fields": missed.most_common(5),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--main-data", type=Path, required=True)
    parser.add_argument("--v3-data", type=Path, required=True)
    parser.add_argument(
        "--v3-hand-check",
        type=Path,
        help="training/generate/v3/hand_checks/gate_fix.json of branch v3-realistic-data",
    )
    args = parser.parse_args()
    report = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "policies": policies(),
        "reason_code_map": reason_codes(),
        "decision_v1": decision_dataset(args.main_data / "decision"),
        "decision_v2": decision_dataset(args.main_data / "decision_v2"),
        "v3": v3(args.v3_data),
        "v3_hand_check": hand_check(args.v3_hand_check) if args.v3_hand_check else None,
        "ocr_heldout": ocr(args.main_data / "eval" / "ocr" / "heldout.jsonl"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
