"""Notes stuck in a loop (found on 25 Oct while rendering v3 claims). Report only.

A writer model sometimes repeats a phrase until it stops ("no new symp no new symp ..."), and the
gate does not look for it. A note counts as looping when one 6-word sequence occurs `LOOP_REPEATS`
times or more (words: lower case, letters and digits). For each final split
(data/generated/v3/final/): how many notes loop, by writer, how many repeat 10 times or more, and
the worst ones. `looping(note)` is used by scripts/demo/render_v3_claims.py to leave them out.

    uv run python -m scripts.verify.v3_repetition
"""

import json
import re
from collections import Counter

from training.generate.v3.config import OUT_DIR

SPLITS = ("train", "validation", "test_messy", "test_unseen_style", "test_human_style")
LOOP_REPEATS = 5
SPAN = 6


def worst_repeat(note: str) -> tuple[int, str]:
    words = re.findall(r"[a-z0-9']+", note.lower())
    if len(words) < 40:
        return 0, ""
    grams = Counter(tuple(words[i : i + SPAN]) for i in range(len(words) - SPAN + 1))
    gram, count = grams.most_common(1)[0]
    return count, " ".join(gram)


def looping(note: str) -> bool:
    return worst_repeat(note)[0] >= LOOP_REPEATS


def report() -> dict:
    found = {}
    for split in SPLITS:
        final = OUT_DIR / "final"
        inputs = [json.loads(line) for line in (final / f"{split}_inputs.jsonl").open()]
        metas = [json.loads(line)["metadata"] for line in (final / f"{split}.jsonl").open()]
        rows = []
        for given, meta in zip(inputs, metas, strict=True):
            count, phrase = worst_repeat(given["claim"]["clinical_notes"])
            if count >= LOOP_REPEATS:
                rows.append(
                    {
                        "record_id": meta["record_id"],
                        "writer": meta.get("writer"),
                        "repeats": count,
                        "phrase": phrase,
                        "words": len(given["claim"]["clinical_notes"].split()),
                    }
                )
        found[split] = {
            "records": len(inputs),
            "looping": len(rows),
            "repeating_10_or_more": sum(r["repeats"] >= 10 for r in rows),
            "by_writer": dict(Counter(r["writer"] for r in rows)),
            "worst": sorted(rows, key=lambda r: -r["repeats"])[:5],
            "record_ids": sorted(r["record_id"] for r in rows),
        }
    return found


if __name__ == "__main__":
    result = report()
    (OUT_DIR / "repetition.json").write_text(json.dumps(result, indent=2) + "\n")
    for split, r in result.items():
        print(
            f"{split}: {r['looping']} of {r['records']} loop ({r['repeating_10_or_more']} repeat "
            f"10+ times), by writer {r['by_writer']}"
        )
