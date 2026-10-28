"""R21, the yearly visit limit (D-RULE-10): what it changes on the generated data and the demo.

- **Datasets** (decision v1 and v2: `<split>_inputs.jsonl`; a v3 `sheets.jsonl`): Group C, as
  scripts/verify/rules_parity.py `engine_view` runs it, on every claim with the generated
  reference's visit usage, against the same claim without R21 (no plan has a visit limit, which is
  rules 2.1.0). Counts the claims with a therapy line, the claims and lines R21 changes, and lists
  each change.
- **Demo claims** (demo/claims/, with 08 and 09 from their corpus claims as
  scripts/demo/build_claims.py writes them): the whole engine in the demo's order (each claim on
  file for the next, as the duplicate check reads them; 01's approved visit counted for its
  member, as finalization does), with the reference `make demo-reset` seeds and
  demo/authorizations.jsonl, without R21 and with it.

Report only: no data, dataset or golden file is changed. Needs data/raw/ (code tables).

    uv run python -m scripts.verify.visit_limit_impact \\
        --generated ../ClaimSense/data/generated \\
        [--v3 ../claimsense-v3/data/generated/v3/pilot/sheets.jsonl] [--out <file.json>]
"""

import argparse
import json
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.db.curated import load_curated, rule_codes
from app.db.rules_reference import build_reference, load_code_tables
from app.domain.contracts import IntakeClaim, RulesOutcome
from app.rules.engine import evaluate
from app.rules.line_edits import check_line_edits
from app.rules.reference import RulesReference
from scripts.demo.build_claims import CLAIMS, broken_check_digit

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
CONFIDENCE_MIN = 0.85  # settings extraction_confidence_min


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def reference(
    generated: Path,
    extra_authorizations: Iterable[Mapping[str, Any]] = (),
    existing_claims: Iterable[Mapping[str, Any]] = (),
    visit_usage: Iterable[Mapping[str, Any]] | None = None,
) -> RulesReference:
    folder = generated / "reference"
    curated = load_curated()
    return build_reference(
        curated,
        load_code_tables(rule_codes(curated)),
        read_jsonl(folder / "members.jsonl"),
        read_jsonl(folder / "providers.jsonl"),
        read_jsonl(folder / "provider_networks.jsonl"),
        [*read_jsonl(folder / "authorizations.jsonl"), *extra_authorizations],
        existing_claims,
        read_jsonl(folder / "visit_usage.jsonl") if visit_usage is None else visit_usage,
    )


def without_r21(ref: RulesReference) -> RulesReference:
    """The same reference with no visit limit on any plan: R21 never fires (rules 2.1.0)."""
    return replace(
        ref, plans={plan_id: replace(p, visit_limits={}) for plan_id, p in ref.plans.items()}
    )


def therapy(claim: IntakeClaim, ref: RulesReference) -> bool:
    return any(
        "REHAB_THERAPY" in ref.benefit_categories.get(line.procedure_code, ())
        for line in claim.service_lines
    )


def group_c(claim: IntakeClaim, ref: RulesReference) -> list[tuple[int, str, list[str]]]:
    member = ref.members[claim.member_id]
    _, lines = check_line_edits(claim, ref.plans[member.plan_id], ref)
    return [(line.line_no, line.outcome, list(line.reason_codes)) for line in lines]


def dataset_impact(
    name: str, claims: list[dict[str, Any]], after: RulesReference
) -> dict[str, Any]:
    before = without_r21(after)
    changes = []
    therapy_claims = 0
    for data in claims:
        claim = IntakeClaim.model_validate(data)
        if claim.member_id not in after.members:
            continue
        therapy_claims += therapy(claim, after)
        old, new = group_c(claim, before), group_c(claim, after)
        if old != new:
            changes.append(
                {
                    "claim_id": claim.claim_id,
                    "member_id": claim.member_id,
                    "lines": [
                        {"line_no": o[0], "before": o[1:], "after": n[1:]}
                        for o, n in zip(old, new, strict=True)
                        if o != n
                    ],
                }
            )
    return {
        "dataset": name,
        "claims": len(claims),
        "claims_with_a_therapy_line": therapy_claims,
        "claims_changed": len(changes),
        "lines_changed": sum(len(c["lines"]) for c in changes),
        "changes": changes,
    }


def demo_claims(generated: Path) -> list[tuple[str, dict[str, Any], dict[str, float]]]:
    """The nine demo claims in order: (file, claim, field confidences)."""
    corpus = {r["claim"]["claim_id"]: r for r in read_jsonl(generated / "claims" / "claims.jsonl")}
    found = []
    for number, (name, (source, kind)) in enumerate(CLAIMS.items(), start=1):
        path = DEMO / "claims" / f"{name}.json"
        if path.exists():
            claim = json.loads(path.read_text(encoding="utf-8"))
        else:  # a scanned form: its corpus claim, as build_claims renders it
            claim = dict(corpus[source]["claim"], claim_id=f"CLM-DEMO-{number:02d}")
        confidences: dict[str, float] = {}
        if kind == "scan-npi-typo":
            claim["billing_npi"] = broken_check_digit(claim["billing_npi"])
            confidences["billing_npi"] = 0.0  # read at confidence 0 (build_claims, 09)
        found.append((name, claim, confidences))
    return found


def summary(outcome: RulesOutcome) -> dict[str, Any]:
    failed = [
        f"{r.rule_id}:{r.reason_code}" + (f"@{r.line_no}" if r.line_no else "")
        for r in outcome.rule_results
        if not r.passed
    ]
    return {
        "claim_outcome": outcome.claim_outcome.value,
        "lines": [(o.line_no, o.outcome, list(o.reason_codes)) for o in outcome.line_outcomes],
        "failed_rules": failed,
    }


def demo_impact(generated: Path) -> list[dict[str, Any]]:
    authorizations = read_jsonl(DEMO / "authorizations.jsonl")
    usage = read_jsonl(generated / "reference" / "visit_usage.jsonl")
    on_file: list[dict[str, Any]] = []
    rows = []
    for name, claim, confidences in demo_claims(generated):
        after_ref = reference(generated, authorizations, on_file, usage)
        before = evaluate(claim, confidences, without_r21(after_ref), confidence_min=CONFIDENCE_MIN)
        after = evaluate(claim, confidences, after_ref, confidence_min=CONFIDENCE_MIN)
        rows.append(
            {
                "demo_claim": name,
                "claim_id": claim["claim_id"],
                "member_id": claim["member_id"],
                "codes": [line["procedure_code"] for line in claim["service_lines"]],
                "visits_used": {
                    u["benefit_category"]: u["visits_used"]
                    for u in usage
                    if u["member_id"] == claim["member_id"]
                },
                "before": summary(before),
                "after": summary(after),
                "unchanged": summary(before) == summary(after),
            }
        )
        status = "REJECTED" if after.claim_outcome.value == "REJECT" else "FINAL"
        on_file += [
            {
                "claim_id": claim["claim_id"],
                "member_id": claim["member_id"],
                "billing_npi": claim["billing_npi"],
                "date_of_service": line["date_of_service"],
                "procedure_code": line["procedure_code"],
                "status": status,
            }
            for line in claim["service_lines"]
        ]
        if name.startswith("01-"):  # finalized with its line approved: one therapy visit (D-REV-8)
            usage = [
                dict(u, visits_used=u["visits_used"] + 1)
                if u["member_id"] == claim["member_id"]
                else u
                for u in usage
            ]
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--generated", type=Path, required=True, help="a data/generated folder")
    parser.add_argument("--v3", type=Path, help="a v3 sheets.jsonl")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    full = reference(args.generated)
    datasets = []
    for name in ("decision", "decision_v2"):
        folder = args.generated / name
        claims = [
            row["claim"]
            for split in ("train", "validation", "test")
            for row in read_jsonl(folder / f"{split}_inputs.jsonl")
        ]
        datasets.append(dataset_impact(name, claims, full))
    if args.v3:
        datasets.append(
            dataset_impact(
                f"v3 ({args.v3.parent.name})",
                [s["inputs"]["claim"] for s in read_jsonl(args.v3)],
                full,
            )
        )
    report = {"datasets": datasets, "demo_claims": demo_impact(args.generated)}

    for d in datasets:
        print(
            f"{d['dataset']}: {d['claims']} claims, {d['claims_with_a_therapy_line']} with a "
            f"therapy line, {d['claims_changed']} changed ({d['lines_changed']} lines)"
        )
        for change in d["changes"]:
            print(f"  {change['claim_id']} ({change['member_id']}): {change['lines']}")
    for row in report["demo_claims"]:
        print(
            f"{row['demo_claim']}: {row['after']['claim_outcome']} "
            f"{'unchanged' if row['unchanged'] else 'CHANGED'}; lines {row['after']['lines']}; "
            f"visits used {row['visits_used'] or '-'}"
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
