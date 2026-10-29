"""Estimated LLM API cost per 1,000 claims (docs/PROJECT_INFO.md section 7.4): an ESTIMATE.

Multiplies the mean o200k_base token counts of `llm_prompt_tokens.py`
(`data/generated/project_info/llm_prompt_tokens_<set>.json`) by list prices. Both models below use
the o200k_base encoding, so the counts are theirs. No API is called. Prices are the standard tier,
US dollars per 1M tokens, without prompt caching or batch discounts, read on 2026-10-23 from
https://developers.openai.com/api/docs/pricing (platform.openai.com/docs/pricing redirects there).
ClaimSense's own model runs locally through Ollama and has no per-token fee.

    uv run python -m scripts.project_info.llm_cost
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "data" / "generated" / "project_info"
PRICES_READ = "2026-10-23"
PRICE_PAGE = "https://developers.openai.com/api/docs/pricing"
PRICES = {  # model: (input, output) in US dollars per 1M tokens, standard tier
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def main() -> None:
    report = {"prices_read": PRICES_READ, "price_page": PRICE_PAGE, "prices": PRICES, "sets": {}}
    for name in ("clean", "messy"):
        path = DIR / f"llm_prompt_tokens_{name}.json"
        if not path.exists():
            continue
        per_1000 = json.loads(path.read_text())["per_1000_claims"]
        tokens_in = per_1000["llm_input_o200k"]
        costs = {}
        for model, (price_in, price_out) in PRICES.items():
            cost_in = tokens_in / 1e6 * price_in
            costs[model] = {
                "input": round(cost_in, 2),
                "total_without_reasoning": round(
                    cost_in + per_1000["llm_output_no_reasoning_o200k"] / 1e6 * price_out, 2
                ),
                "total_with_reasoning": round(
                    cost_in + per_1000["llm_output_with_reasoning_o200k"] / 1e6 * price_out, 2
                ),
            }
        report["sets"][name] = {"tokens_per_1000_claims": per_1000, "usd_per_1000_claims": costs}
    (DIR / "llm_cost.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
