"""What the gate fix of 20 Oct changes (team checks before the official rerun). Report only.

The fixed gate (training/generate/v3/verify.py) runs in memory on each sheet's latest note, against
round 3's gate results saved before the fix (`--before`, gate_r3_before_fix.jsonl):

1. Notes per writer by status before and after (passed, failed, pending; "second look": a leak
   finding the verifier is asked about again, alone, in the next round).
2. The 40 failed notes of the hand check (gate_analysis_r3.json, seed 20261019): the 12 the team
   judged really wrong must still fail, and at least 24 of the other 28 must pass.
3. Two seeded samples written out for a hand check (hand_check_gate_fix.md): 20 notes that passed
   before and fail now, 40 that failed before and pass now. For each: the old and new failures,
   every documented fact's quote (and whether the note's own text gave it), and what the verifier
   cited for each missing or absent fact.
4. Evidence quotes: for every note that passes both before and after, each documented fact whose
   quote changed (the verifier had given it another fact's sentence, or a passage that now resolves
   differently), with the share of the fact's words in the old and the new quote.

    uv run python -m scripts.verify.v3_gate_change [--out data/generated/v3/gate_change.json]
"""

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from training.generate.v3.config import OUT_DIR
from training.generate.v3.dataset import latest, load_sheets, read_jsonl
from training.generate.v3.verify import GateResult, check_note, filled_target, share

# The hand check of 19 Oct: the failed notes the team judged really wrong (the others failed on
# the verifier, the gate's matching or the claim's own wording).
REALLY_WRONG = frozenset(
    "S3TR-05583 S3TR-00599 S3TR-06574 S3VA-00025 S3TR-03942 S3TR-02170 "
    "S3TU-00036 S3TU-00120 S3TU-00109 S3TU-00096 S3TU-00081 S3TU-00043".split()
)
SEED = 20261020


def gate_now(
    sheet: dict[str, Any],
    note: dict[str, Any],
    answer: dict | None,
    looks: dict[str, str | None] | None = None,
) -> GateResult:
    """The fixed gate on one note, as `dataset.run_gate` runs it."""
    answers = answer.get("answers") if answer else None
    known = {k: tuple(v) for k, v in note["spans"].items()} if note.get("spans") else None
    result = check_note(sheet, note["note"], known, answers, looks)
    if answer is not None and answers is None:
        result.failures.append(f"verifier answer unreadable: {answer.get('error')}")
        result.verifier_pending = False
    if result.failures:
        result.verifier_pending = False
    if not result.failures and not result.verifier_pending and not result.looks:
        result.failures += filled_target(sheet, note["note"], result.spans)[1]
    return result


def status(passed: bool, pending: bool) -> str:
    return "pending" if pending else ("passed" if passed else "failed")


def fact_words(fact: dict[str, Any], fid: str) -> list[str]:
    texts = fact.get("original") if fid.endswith(":original") else fact.get("text")
    return list((texts or {}).values())


def describe(
    sheet: dict[str, Any],
    note: dict[str, Any],
    old: dict[str, Any],
    new: GateResult,
    answer: dict | None,
) -> list[str]:
    text = note["note"]
    facts = {f["fact_id"]: f for f in sheet["facts"]}
    answers = (answer or {}).get("answers") or {}
    lines = [f"## {sheet['sheet_id']} (writer {note['writer']}, attempt {note['attempt']})", ""]
    lines += [f"- before: {f}" for f in old["failures"]] or ["- before: passed"]
    lines += [f"- now: {f}" for f in new.failures] or [
        f"- now: waiting for a second look at {new.looks}" if new.looks else "- now: passed"
    ]
    for fid, (start, end) in sorted(new.spans.items()):
        fact = facts[fid.split(":")[0]]
        how = "note's own text" if fid in new.local_spans else "verifier"
        lines += [
            f"- {fid} ({fact['status']}, {how}): {text[start:end]!r}",
            f"  - asked: {fact_words(fact, fid)[0]}",
        ]
    for fact in sheet["facts"]:
        if fact["status"] in ("missing", "absent") and answers.get(fact["fact_id"]):
            asked = fact.get("missing_text") or (fact.get("forbidden") or ["-"])[0]
            lines += [
                f"- {fact['fact_id']} ({fact['status']}): verifier cited "
                f"{answers[fact['fact_id']]!r}",
                f"  - asked: {asked}",
            ]
    lines += ["", "<details><summary>note</summary>", "", "```text", text, "```", "</details>", ""]
    return lines


def gate_change(out_dir: Path = OUT_DIR, before_file: str = "gate_r3_before_fix.jsonl") -> dict:
    sheets = load_sheets(out_dir)
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    verifier = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(out_dir / "verifier.jsonl")}
    before = {g["sheet_id"]: g for g in read_jsonl(out_dir / before_file)}
    after: dict[str, GateResult] = {}
    for sheet_id, note in notes.items():
        after[sheet_id] = gate_now(
            sheets[sheet_id], note, verifier.get((sheet_id, note["attempt"]))
        )
    report: dict[str, Any] = {}

    flips: Counter[str] = Counter()
    moved: dict[str, list[str]] = {"passed_to_failed": [], "failed_to_passed": []}
    for sheet_id, result in after.items():
        old = before.get(sheet_id)
        if old is None or old["attempt"] != notes[sheet_id]["attempt"]:
            continue
        was = status(old["passed"], old["pending"])
        now = "second look" if result.looks else status(result.passed, result.pending)
        flips[f"{notes[sheet_id]['writer']} {was} -> {now}"] += 1
        if was == "passed" and now == "failed":
            moved["passed_to_failed"].append(sheet_id)
        if was == "failed" and now == "passed":
            moved["failed_to_passed"].append(sheet_id)
    report["1_status_before_and_after"] = dict(sorted(flips.items()))

    picks = json.loads((out_dir / "gate_analysis_r3.json").read_text())["3_hand_check_sample"]
    rows = {
        sid: "second look" if after[sid].looks else status(after[sid].passed, after[sid].pending)
        for sid in picks
    }
    good = [sid for sid in picks if sid not in REALLY_WRONG]
    report["2_hand_check_of_19_oct"] = {
        "really_wrong_still_failing": f"{sum(rows[s] == 'failed' for s in REALLY_WRONG)} of "
        f"{len(REALLY_WRONG)}",
        "good_now_passing": f"{sum(rows[s] == 'passed' for s in good)} of {len(good)}",
        "good_waiting_for_a_second_look": {s: after[s].looks for s in good if after[s].looks},
        "good_still_failing": {s: after[s].failures for s in good if rows[s] == "failed"},
        "really_wrong_now_passing": [s for s in REALLY_WRONG if rows[s] == "passed"],
    }

    rng = random.Random(SEED)
    samples = {
        "passed_to_failed": rng.sample(sorted(moved["passed_to_failed"]), 20),
        "failed_to_passed": rng.sample(sorted(moved["failed_to_passed"]), 40),
    }
    lines = ["# Hand check: the gate fix of 20 Oct", "", "Synthetic data only.", ""]
    for kind, ids in samples.items():
        lines += [f"# {kind.replace('_', ' ')} ({len(ids)})", ""]
        for sheet_id in ids:
            note = notes[sheet_id]
            lines += describe(
                sheets[sheet_id],
                note,
                before[sheet_id],
                after[sheet_id],
                verifier.get((sheet_id, note["attempt"])),
            )
    (out_dir / "hand_check_gate_fix.md").write_text("\n".join(lines), encoding="utf-8")
    report["3_hand_check_samples"] = {
        "seed": SEED,
        "passed_to_failed": {
            "of": len(moved["passed_to_failed"]),
            **{"ids": samples["passed_to_failed"]},
        },
        "failed_to_passed": {
            "of": len(moved["failed_to_passed"]),
            **{"ids": samples["failed_to_passed"]},
        },
    }

    changed = []
    both = 0
    for sheet_id, result in after.items():
        old = before.get(sheet_id)
        if (
            not (old and old["passed"] and result.passed)
            or old["attempt"] != notes[sheet_id]["attempt"]
        ):
            continue
        both += 1
        text = notes[sheet_id]["note"]
        facts = {f["fact_id"]: f for f in sheets[sheet_id]["facts"]}
        for fid, span in result.spans.items():
            was = old["spans"].get(fid)
            if was is None or tuple(was) == tuple(span) or ":" in fid:
                continue
            wording = fact_words(facts[fid], fid)
            changed.append(
                {
                    "sheet_id": sheet_id,
                    "fact_id": fid,
                    "split": sheets[sheet_id]["split"],
                    "old_share": round(max(share(w, text[was[0] : was[1]]) for w in wording), 2),
                    "new_share": round(max(share(w, text[span[0] : span[1]]) for w in wording), 2),
                    "overlapping": was[0] < span[1] and span[0] < was[1],
                }
            )
    report["4_evidence_quotes"] = {
        "notes_passing_before_and_after": both,
        "quotes_changed": len(changed),
        "notes_with_a_changed_quote": len({c["sheet_id"] for c in changed}),
        "training_notes_with_a_changed_quote": len(
            {c["sheet_id"] for c in changed if c["split"] == "train"}
        ),
        "old_quote_another_passage": sum(not c["overlapping"] for c in changed),
        "old_quote_overlapping_the_new": sum(c["overlapping"] for c in changed),
        "old_quote_share_under_0.2": sum(c["old_share"] < 0.2 for c in changed),
        "changed": changed,
    }
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=OUT_DIR)
    parser.add_argument("--before", default="gate_r3_before_fix.jsonl")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = gate_change(args.data, args.before)
    shown = {k: v for k, v in report.items() if k != "4_evidence_quotes"}
    shown["4_evidence_quotes"] = {
        k: v for k, v in report["4_evidence_quotes"].items() if k != "changed"
    }
    print(json.dumps(shown, indent=2))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
