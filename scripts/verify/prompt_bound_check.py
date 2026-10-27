"""The largest prompt counted at intake is never below a claim's real prompt (D-DOC-3). Report only.

For decision records (the given folder, e.g. claimsense-v3 data/generated/v3/final: each split's
`<split>_inputs.jsonl` claims and `<split>.jsonl` prompts, rendered by the generator from the
claim's own plan, network, rules result, benefits and retrieved criteria), compares
`largest_prompt_tokens` (app/context/prompt_budget.py), counted from the claim alone as intake
counts it, with the tokens of the record's own prompt (`prompt_tokens`, which equals Ollama's count:
scripts/verify/prompt_token_check.py). Every bound must be at least its prompt; any below is
listed. Also: the margin (bound minus prompt), the largest bound, and how many bounds are over the
budget (`PROMPT_BUDGET`) and so would be refused at intake; with `--rendered`, the same for the
rendered claims (claimsense-v3 scripts/demo/render_v3_claims.py) by their number of pages.

The descriptions are those the database is seeded with: ICD-10-CM from data/raw, procedures from
data/curated. Writes data/generated/eval/prompt_bound_check.json.

    uv run python -m scripts.verify.prompt_bound_check <records dir> [--rendered <dir>]
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from app.context.prompt_budget import largest_prompt_tokens
from app.core.settings import get_settings
from app.db.curated import load_curated
from app.db.raw import read_icd10_codes
from app.domain.contracts import IntakeClaim
from app.ml.prompt import PromptLookups
from app.ml.tokens import PROMPT_BUDGET, prompt_tokens
from app.workflow.pipeline import bypass_keys

SPLITS = ("train", "validation", "test_messy", "test_unseen_style", "test_human_style")


def summary(rows: list[dict]) -> dict:
    margins = [r["bound"] - r["prompt"] for r in rows]
    return {
        "records": len(rows),
        "bound_below_prompt": [r["record_id"] for r in rows if r["bound"] < r["prompt"]],
        "margin_min": min(margins),
        "margin_median": statistics.median(margins),
        "margin_max": max(margins),
        "prompt_max": max(r["prompt"] for r in rows),
        "bound_max": max(r["bound"] for r in rows),
        "over_budget": [r["record_id"] for r in rows if r["bound"] > PROMPT_BUDGET],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("records", type=Path)
    parser.add_argument("--rendered", type=Path)
    args = parser.parse_args()
    tokenizer = get_settings().prompt_tokenizer
    icd10 = read_icd10_codes()
    keys = bypass_keys()
    curated = {name: load_curated(name) for name in ("v1", "v2")}
    rows = []
    for split in SPLITS:
        claims = {}
        for line in (args.records / f"{split}_inputs.jsonl").open(encoding="utf-8"):
            row = json.loads(line)
            claims[row["record_id"]] = IntakeClaim.model_validate(row["claim"])
        for line in (args.records / f"{split}.jsonl").open(encoding="utf-8"):
            record = json.loads(line)
            meta = record["metadata"]
            claim = claims[meta["record_id"]]
            data = curated[meta["policy_set"]]
            lookups = PromptLookups(
                icd10_descriptions={c: icd10[c] for c in claim.diagnoses if c in icd10},
                procedure_descriptions=data.descriptions,
                policy_codes={p: list(x.procedure_codes) for p, x in data.policies.items()},
                bypass_keys=keys,
            )
            system, user = (m["content"] for m in record["messages"][:2])
            rows.append(
                {
                    "record_id": meta["record_id"],
                    "split": split,
                    "prompt": prompt_tokens(system, user, tokenizer),
                    "bound": largest_prompt_tokens(
                        claim, lookups, data, meta["prompt_version"], tokenizer
                    ),
                }
            )
    report: dict = {"budget": PROMPT_BUDGET, "all": summary(rows)}
    by_split = defaultdict(list)
    for row in rows:
        by_split[row["split"]].append(row)
    report["by_split"] = {split: summary(items) for split, items in by_split.items()}
    if args.rendered:
        found = {row["record_id"]: row for row in rows}
        index = json.loads((args.rendered / "index.json").read_text())["claims"]
        by_pages = defaultdict(list)
        for claim in index:
            by_pages[f"{claim['pages']} pages"].append(found[claim["record_id"]])
        report["rendered"] = {pages: summary(items) for pages, items in sorted(by_pages.items())}
    report["rows"] = rows
    out = Path(__file__).resolve().parents[2] / "data/generated/eval/prompt_bound_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
