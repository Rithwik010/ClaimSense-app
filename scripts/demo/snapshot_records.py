"""Snapshot of the nine demo claims for the D-UI-6 unit tests (tests/fixtures/demo_records.json):
for each claim, as the running API holds it after `make e2e-api` (or `make offline-check`): its
status, the claim as stored at intake, its field confidences, its latest decision record and the
plan's coinsurance rate for the claim's network. The unit tests rebuild the provider's explanation
and billing and the claim summary from it, with no database or model, so CI checks the billing
arithmetic on every demo claim too. Synthetic data only (the demo claims of demo/claims/).

    uv run python -m scripts.demo.snapshot_records
"""

import json
from pathlib import Path

from scripts.demo.e2e_api import API, REVIEWER_ID, login

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "fixtures" / "demo_records.json"


def main() -> None:
    api = login(API, REVIEWER_ID)
    claims = []
    rates: dict[str, dict[str, int | None]] = {}
    for n in range(1, 10):
        claim_id = f"CLM-DEMO-{n:02d}"
        view = api.get(f"/v1/claims/{claim_id}").json()
        record = view["record"]
        context = record and record.get("context_refs")
        rate = None
        if context:
            plan_id = context["plan_id"]
            if plan_id not in rates:
                plan = api.get(f"/v1/plans/{plan_id}").json()
                rates[plan_id] = {
                    "IN_NETWORK": plan["inn_coinsurance_bps"],
                    "OUT_OF_NETWORK": plan["oon_coinsurance_bps"],
                }
            rate = rates[plan_id][context["network"]]
        claims.append(
            {
                "claim_id": claim_id,
                "status": view["status"],
                "outcome": view["outcome"],
                "received": view["received"],
                "field_confidences": view["field_confidences"],
                "record": record,
                "coinsurance_bps": rate,
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(claims, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(claims)} claims")


if __name__ == "__main__":
    main()
