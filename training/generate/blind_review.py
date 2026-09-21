"""Blind-review subset (INSTRUCTIONS.md §9.5): 30 claims a reviewer decides before seeing the model.

Writes `tests/golden/blind_review/claims.json` (what the reviewer sees: the claim, rules result and
context, rendered exactly as the model sees them) and `review_sheet.csv` (one row per line to
decide). The generator's labels go only to `data/generated/blind_review/answer_key.json`, which is
never committed; reviewers must not open it until their sheet is complete. Deterministic: the
test suite regenerates the claims and compares them with the committed file.

    uv run python -m training.generate.blind_review
"""

import argparse
import csv
import io
import json
import random
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from app.domain.contracts import RulesOutcome
from app.ml.prompt import lines_to_decide, render_user_message
from training.generate.common import DEFAULT_SEED, GENERATED_DIR, write_json
from training.generate.decision_dataset import SCENARIO_WEIGHTS, prompt_lookups
from training.generate.reference import generate_reference
from training.generate.scenarios import ScenarioBuilder, ScenarioError

GENERATOR_VERSION = "blind-review-v1"
BLIND_SEED = 7_310_001
CLAIM_COUNT = 30
GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "golden" / "blind_review"
SHEET_COLUMNS = [
    "claim_id",
    "line_no",
    "decision",
    "benefit_category",
    "reason_code",
    "missing_information",
    "reviewer_id",
    "minutes_spent",
    "notes",
]


def build() -> tuple[dict[str, Any], str, dict[str, Any]]:
    curated = load_curated()
    policies = set(curated.policies)
    builder = ScenarioBuilder(
        BLIND_SEED, "B", policies, policies, generate_reference(DEFAULT_SEED)[0]
    )
    lookups = prompt_lookups()
    rng = random.Random(BLIND_SEED)
    types, weights = list(SCENARIO_WEIGHTS), list(SCENARIO_WEIGHTS.values())
    claims, key = [], {}
    while len(claims) < CLAIM_COUNT:
        claim_id = f"CLM-BLIND-{len(claims) + 1:03d}"
        try:
            scenario = builder.build(rng.choices(types, weights=weights)[0], claim_id)
        except ScenarioError:
            continue
        assert scenario.target is not None
        claims.append(
            {
                "claim_id": claim_id,
                "review_view": render_user_message(
                    scenario.claim, scenario.rules, scenario.context, lookups
                ),
                "claim": scenario.claim.model_dump(mode="json"),
                "rules_outcome": scenario.rules.model_dump(mode="json"),
                "context": scenario.context.model_dump(mode="json"),
            }
        )
        key[claim_id] = {
            "scenario_type": scenario.scenario_type,
            "target": scenario.target.model_dump(mode="json"),
            "line_labels": scenario.line_labels,
        }
    sheet = io.StringIO()
    writer = csv.writer(sheet, lineterminator="\n")
    writer.writerow(SHEET_COLUMNS)
    for claim in claims:
        for line_no in lines_to_decide(RulesOutcome.model_validate(claim["rules_outcome"])):
            writer.writerow([claim["claim_id"], line_no] + [""] * (len(SHEET_COLUMNS) - 2))
    document = {
        "generator_version": GENERATOR_VERSION,
        "seed": BLIND_SEED,
        "instructions": (
            "For each line listed in review_sheet.csv, read review_view and record APPROVE, PEND "
            "or DENY, the benefit category, a reason code (DN_NOT_MEDICALLY_NECESSARY, "
            "DN_CONDITIONAL_EXCLUSION or PD_MISSING_DOCUMENTATION) and what is missing. Decide "
            "before seeing any model output, and do not open "
            "data/generated/blind_review/answer_key.json."
        ),
        "claims": claims,
    }
    return document, sheet.getvalue(), key


def write(golden_dir: Path, key_path: Path) -> None:
    document, sheet, key = build()
    golden_dir.mkdir(parents=True, exist_ok=True)
    (golden_dir / "claims.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    (golden_dir / "review_sheet.csv").write_text(sheet, encoding="utf-8")
    write_json(key_path, {"generator_version": GENERATOR_VERSION, "seed": BLIND_SEED, "key": key})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--golden-dir", type=Path, default=GOLDEN_DIR)
    parser.add_argument(
        "--key", type=Path, default=GENERATED_DIR / "blind_review" / "answer_key.json"
    )
    args = parser.parse_args()
    write(args.golden_dir, args.key)
    print(f"wrote {CLAIM_COUNT} blind-review claims to {args.golden_dir}; key at {args.key}")


if __name__ == "__main__":
    main()
