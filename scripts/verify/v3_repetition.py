"""Notes stuck in a loop (found on 25 Oct while rendering v3 claims; D-V3-29). Report only.

A writer model sometimes repeats a phrase until it stops ("no new symp no new symp ..."). The
rule is the gate's own (training/generate/v3/verify.py `worst_repeat`, config
`verification.loop_span` and `verification.loop_repeats`): a note loops when one 6-word sequence
(words: lower case, letters and digits) occurs 5 times or more; notes under 40 words count as 0.
The gate fails such notes from now on; the datasets built on 24 Oct were made before it.

Covered: every record the model trains on (data/generated/v3/final/train_mix.jsonl, 10,000: the
v3 notes from final/train_inputs.jsonl, the v2-style ones from decision_v2/train_inputs.jsonl and
v3/v2_extra/train_inputs.jsonl), validation, every test set (messy, unseen-style, the LLM-written
human-style one, and v2's clean test). For each: how many notes loop, by writer, how many repeat 10
times or more, how many fall just under the rule (a sequence 3 or 4 times), the distribution of the
highest repeat count, and the looping record ids (the stage 5 main sets leave them out). Writes
data/generated/v3/repetition.json.

    uv run python -m scripts.verify.v3_repetition
"""

import json
from collections import Counter
from pathlib import Path

from training.generate.common import GENERATED_DIR
from training.generate.v3.config import OUT_DIR, config
from training.generate.v3.verify import worst_repeat

FINAL = OUT_DIR / "final"
V2 = GENERATED_DIR / "decision_v2"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def notes_of(path: Path) -> dict[str, str]:
    return {r["record_id"]: r["claim"]["clinical_notes"] for r in read_jsonl(path)}


def looping(note: str) -> bool:
    return worst_repeat(note)[0] >= config()["verification"]["loop_repeats"]


def sets() -> dict[str, list[tuple[dict, str]]]:
    """(metadata, note) for every record of each set."""
    v2_style = notes_of(V2 / "train_inputs.jsonl") | notes_of(
        OUT_DIR / "v2_extra/train_inputs.jsonl"
    )
    v3_train = notes_of(FINAL / "train_inputs.jsonl")
    found = {}
    mix = []
    for record in read_jsonl(FINAL / "train_mix.jsonl"):
        meta = record["metadata"]
        rid = meta["record_id"]
        mix.append((meta, v3_train.get(rid) or v2_style[rid]))  # a KeyError: a note not found
    found["train_mix"] = mix
    for split in ("validation", "test_messy", "test_unseen_style", "test_human_style"):
        notes = notes_of(FINAL / f"{split}_inputs.jsonl")
        found[split] = [
            (r["metadata"], notes[r["metadata"]["record_id"]])
            for r in read_jsonl(FINAL / f"{split}.jsonl")
        ]
    notes = notes_of(V2 / "test_inputs.jsonl")
    found["clean"] = [
        (r["metadata"], notes[r["metadata"]["record_id"]]) for r in read_jsonl(V2 / "test.jsonl")
    ]
    return found


def report() -> dict:
    limit = config()["verification"]["loop_repeats"]
    found = {
        "rule": {
            "span_words": config()["verification"]["loop_span"],
            "repeats": limit,
            "min_words": 40,
        }
    }
    for name, rows in sets().items():
        scored = []
        for meta, note in rows:
            count, phrase = worst_repeat(note)
            writer = meta.get("writer") or (
                "v2-style" if meta["record_id"].startswith("DV2") else ""
            )
            scored.append((count, phrase, meta["record_id"], writer, len(note.split())))
        loops = [s for s in scored if s[0] >= limit]
        highest = Counter(min(s[0], limit) for s in scored)
        found[name] = {
            "records": len(scored),
            "looping": len(loops),
            "repeating_10_or_more": sum(s[0] >= 10 for s in loops),
            "by_writer": dict(Counter(s[3] for s in loops)),
            "just_under": {
                "3 times": sum(s[0] == 3 for s in scored),
                "4 times": sum(s[0] == limit - 1 for s in scored),
            },
            "highest_repeat": {
                (f"{k}+" if k == limit else str(k)): v for k, v in sorted(highest.items())
            },
            "worst": [
                {"record_id": s[2], "writer": s[3], "repeats": s[0], "phrase": s[1], "words": s[4]}
                for s in sorted(loops, reverse=True)[:5]
            ],
            "record_ids": sorted(s[2] for s in loops),
        }
    return found


if __name__ == "__main__":
    result = report()
    (OUT_DIR / "repetition.json").write_text(json.dumps(result, indent=2) + "\n")
    print("rule:", result.pop("rule"))
    for name, r in result.items():
        print(
            f"{name}: {r['looping']} of {r['records']} loop "
            f"({r['repeating_10_or_more']} repeat 10+ times; by writer {r['by_writer']}); "
            f"just under: {r['just_under']}"
        )
