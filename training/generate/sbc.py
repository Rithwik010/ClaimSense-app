"""Summary of Benefits and Coverage generator (P3.2, INSTRUCTIONS.md §9.3).

Writes one fictional SBC per plan from `plans.yaml`, `benefits.yaml` and `exclusions.yaml`, as
Markdown with one `##` section per chunk for the `plan_documents` collection. The section order
loosely follows the CMS SBC template (data/raw/sbc/); the wording is our own. Every amount comes
from the curated files; `test_sbc.py` checks that each figure in the text matches them (H16: plan
facts for decisions still come from the database, never from these documents).

    uv run python -m training.generate.sbc [--out DIR]
"""

import argparse
from pathlib import Path

from app.db.curated import BenefitConfig, CuratedData, NetworkTerms, PlanConfig, load_curated
from training.generate.common import GENERATED_DIR, write_json

GENERATOR_VERSION = "sbc-v1"

CATEGORY_LABELS = {
    "OFFICE_VISIT_PCP": "Primary care visit",
    "OFFICE_VISIT_SPECIALIST": "Specialist visit",
    "PREVENTIVE_CARE": "Preventive care and screening",
    "ADVANCED_IMAGING": "Advanced imaging (CT, MRI)",
    "DIAGNOSTIC_TESTS": "Diagnostic tests (heart, sleep, nerve, allergy, ultrasound)",
    "MENTAL_HEALTH_OUTPATIENT": "Outpatient mental health services",
    "PAIN_MANAGEMENT": "Pain management injections",
    "OUTPATIENT_SURGERY": "Outpatient surgery",
    "ENDOSCOPY": "Endoscopy (colonoscopy)",
    "MINOR_PROCEDURES": "Minor procedures (foot care, wound care)",
    "REHAB_THERAPY": "Physical therapy",
}


def dollars(cents: int) -> str:
    """Display format for an integer cent amount, e.g. 50000 -> $500.00."""
    return f"${cents // 100:,}.{cents % 100:02d}"


def percent(bps: int) -> str:
    return f"{bps // 100}%" if bps % 100 == 0 else f"{bps / 100:.2f}%"


def _member_cost(benefit: BenefitConfig, terms: NetworkTerms | None) -> str:
    if terms is None:
        return "Not covered"
    if benefit.cost_share_rule == "COPAY" and benefit.copay_cents is not None:
        if benefit.copay_cents == 0:
            return "No charge; deductible does not apply"
        return f"{dollars(benefit.copay_cents)} copay per service; deductible does not apply"
    return f"{percent(terms.coinsurance_bps)} coinsurance after deductible"


def _oon_cost(terms: NetworkTerms | None) -> str:
    # Out-of-network services always use the out-of-network deductible and coinsurance.
    return (
        "Not covered"
        if terms is None
        else f"{percent(terms.coinsurance_bps)} coinsurance after deductible"
    )


def _limitations(benefit: BenefitConfig) -> str:
    notes = []
    if benefit.auth_required:
        notes.append("Prior authorization required")
    if benefit.visit_limit:
        notes.append(f"Limited to {benefit.visit_limit} visits per calendar year")
    return "; ".join(notes) or "None"


def render_sbc(plan: PlanConfig, curated: CuratedData) -> dict[str, str]:
    """Return the SBC sections (title -> Markdown body) for one plan."""
    inn, oon = plan.in_network, plan.out_of_network
    copay_categories = [
        CATEGORY_LABELS[c]
        for c in curated.categories
        if curated.benefit(plan.plan_id, c).cost_share_rule == "COPAY"
    ]
    referral = (
        "Yes. You need a referral from your primary care provider to see: "
        + ", ".join(
            t.replace("_", " ").lower() for t in sorted(plan.referral_required_provider_types)
        )
        + "."
        if plan.referral_required_provider_types
        else "No. You can see a specialist without a referral."
    )
    sections: dict[str, str] = {}
    sections["Important questions"] = "\n".join(
        [
            f"- **Overall deductible:** {dollars(inn.deductible_cents)} per person in network"
            + (
                f"; {dollars(oon.deductible_cents)} out of network."
                if oon
                else ". Out-of-network care is not covered."
            ),
            "- **Services covered before you meet the deductible:** "
            + (", ".join(copay_categories) if copay_categories else "None")
            + ". Copays for these services do not count toward the deductible.",
            f"- **Out-of-pocket limit:** {dollars(inn.oop_max_cents)} per person in network"
            + (f"; {dollars(oon.oop_max_cents)} out of network." if oon else "."),
            "- **What counts toward the out-of-pocket limit:** deductible, copays and coinsurance. "
            "Amounts above the allowed amount billed by out-of-network providers do not count.",
            "- **Benefit period:** calendar year; the deductible and out-of-pocket totals reset "
            "on 1 January.",
            f"- **Do you need a referral to see a specialist?** {referral}",
            "- **Does this plan use a provider network?** Yes. "
            + (
                "You pay less with in-network providers."
                if oon
                else "Only in-network providers are covered."
            ),
        ]
    )
    rows = [
        "| Service | In-network cost | Out-of-network cost | Limitations |",
        "|---|---|---|---|",
    ]
    for category in curated.categories:
        benefit = curated.benefit(plan.plan_id, category)
        rows.append(
            f"| {CATEGORY_LABELS[category]} | {_member_cost(benefit, inn)} | {_oon_cost(oon)} "
            f"| {_limitations(benefit)} |"
        )
    sections["What you pay for covered services"] = "\n".join(rows)
    authorized = [
        CATEGORY_LABELS[c]
        for c in curated.categories
        if curated.benefit(plan.plan_id, c).auth_required
    ]
    sections["Prior authorization"] = (
        "Your provider must get approval from the plan before these services, or the claim is "
        "denied: " + ", ".join(authorized) + "."
    )
    exclusions = [e for e in curated.exclusions if e.plan_id == plan.plan_id]
    excluded = (
        "\n".join(f"- {curated.descriptions[e.procedure_code]} ({e.reason})" for e in exclusions)
        if exclusions
        else "- No procedure is excluded by name. Services must still meet the plan's coverage "
        "policies."
    )
    sections["Excluded services"] = (
        excluded
        + "\n- Cosmetic procedures, and services that do not meet a coverage policy's criteria."
    )
    sections["Filing a claim"] = (
        f"In-network providers must file within {plan.filing_window_inn_days} days of the date "
        "of service."
        + (
            f" Out-of-network claims must be filed within {plan.filing_window_oon_days} days."
            if oon
            else ""
        )
        + " Claims filed later are denied."
    )
    return sections


def render_markdown(plan: PlanConfig, sections: dict[str, str]) -> str:
    header = [
        f"# {plan.name} — Summary of Benefits and Coverage",
        "",
        f"Plan ID {plan.plan_id} · {plan.plan_type} · coverage period starting "
        f"{plan.effective_date}. "
        "Fictional plan for the ClaimSense prototype (synthetic data).",
    ]
    body = [f"\n## {title}\n\n{text}" for title, text in sections.items()]
    return "\n".join(header) + "\n" + "\n".join(body) + "\n"


def write_sbcs(out_dir: Path) -> list[str]:
    curated = load_curated()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    chunks = []
    for plan in curated.plans.values():
        sections = render_sbc(plan, curated)
        path = out_dir / f"{plan.plan_id}.md"
        path.write_text(render_markdown(plan, sections), encoding="utf-8")
        written.append(path.name)
        chunks += [
            {
                "plan_id": plan.plan_id,
                "section": title,
                "text": text,
                "source": f"SBC {plan.plan_id}",
            }
            for title, text in sections.items()
        ]
    write_json(out_dir / "chunks.json", {"generator_version": GENERATOR_VERSION, "chunks": chunks})
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=GENERATED_DIR / "sbc")
    args = parser.parse_args()
    print(f"wrote {write_sbcs(args.out)} to {args.out}")


if __name__ == "__main__":
    main()
