"""Where model v2 goes wrong, from its stored answers on the 300 v2 test claims (no model calls).

Reads data/generated/decision_v2/test.jsonl (gold answers), test_inputs.jsonl (claim, rules
outcome, context package) and data/generated/eval/v2/v2data-model-v2.jsonl (the answer the
evaluation used for each claim). Each answer is validated and its line decisions derived exactly as
the pipeline and the evaluation do (`validate_output`, `final_line_decisions`); the script first
checks that this reproduces the stored predictions.

a. Wrong lines by direction (gold -> predicted), by policy and by criterion type, and which
   criterion status was wrong on them.
b. QUICK-tier risk: each claim's tier from `app/review/tiers.py` (the model's output, the
   calculator's total allowed amount for the derived decisions, no low-confidence fields for JSON
   claims), and how many QUICK claims hold a wrong line. Needs the seeded database (the fee schedule
   and the members' plans); the calculator only reads it.
c. Evidence guard (app/ml/evidence.py, D-EVID-1): a MET criterion whose evidence is not found in
   the clinical notes (the evaluation's check: the exact text) becomes NOT_DOCUMENTED, and the
   line decisions are derived again: the "v2 + guard" row. The "v2" row is the answers as they
   were evaluated, before the guard.

Writes docs/results-v2-errors.md and data/generated/eval/v2/v2-errors.json (read by the API's
metrics endpoint).

    uv run python -m scripts.verify.v2_errors
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db import lookups
from app.db.session import get_engine
from app.domain.contracts import (
    ContextPackage,
    IntakeClaim,
    RulesOutcome,
)
from app.ml.evidence import evidence_guard
from app.ml.validate import ValidationResult, validate_output
from app.review.tiers import review_tier
from app.workflow.decisions import final_line_decisions
from app.workflow.pipeline import CalculationError, _calculate
from training.evaluate.model import _decision_metrics, read_jsonl

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "generated" / "decision_v2"
ANSWERS = ROOT / "data" / "generated" / "eval" / "v2" / "v2data-model-v2.jsonl"
OUT_JSON = ROOT / "data" / "generated" / "eval" / "v2" / "v2-errors.json"
REPORT = ROOT / "docs" / "results-v2-errors.md"
WORDS = {"APPROVE": "approve", "PEND": "pend", "DENY": "deny"}


def effective(result: ValidationResult, rules: RulesOutcome, context: ContextPackage) -> dict:
    """Model lines' derived decisions, as the evaluation scores them."""
    return {
        d.line_no: d.decision.value
        for d in final_line_decisions(rules, result, context)
        if d.source != "RULE"
    }


def analyse(session: Session) -> dict[str, Any]:
    records = read_jsonl(DATASET / "test.jsonl")
    inputs = {r["record_id"]: r for r in read_jsonl(DATASET / "test_inputs.jsonl")}
    answers = {a["record_id"]: a for a in read_jsonl(ANSWERS)}
    high_dollar = get_settings().review_high_dollar_cents
    gold_all, pred_all, guard_all = [], [], []
    wrong_lines: list[dict[str, Any]] = []
    tiers: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # claims, with a wrong line, wrong
    lines_by_policy: Counter = Counter()
    guard_changed = 0
    mismatches = 0
    for record in records:
        rid = record["metadata"]["record_id"]
        given, answer = inputs[rid], answers[rid]
        rules = RulesOutcome.model_validate(given["rules_outcome"])
        context = ContextPackage.model_validate(given["context"])
        claim = IntakeClaim.model_validate(given["claim"])
        target = json.loads(record["messages"][-1]["content"])
        result = validate_output(answer["output"], rules, context)
        predicted = effective(result, rules, context)
        guard_result, notes = evidence_guard(result, claim.clinical_notes)
        guard_changed += len(notes)
        guard_predicted = effective(guard_result, rules, context)
        stored = {line["line_no"]: line["predicted"] for line in answer["lines"]}
        gold_lines = {line["line_no"]: line for line in target["lines"]}
        answered = {line.line_no: line for line in (result.output.lines if result.output else [])}
        shown = {line.line_no: line for line in context.lines}
        wrong_here = 0
        for n, gold in gold_lines.items():
            pred = predicted.get(n, "PEND")
            mismatches += pred != stored[n]
            gold_all.append(gold["decision"])
            pred_all.append(pred)
            guard_all.append(guard_predicted.get(n, "PEND"))
            ctx = shown[n]
            policies = sorted({c.policy_id for c in ctx.criteria}) or ["(no criteria)"]
            for policy in policies:
                lines_by_policy[policy] += 1
            if pred == gold["decision"]:
                continue
            wrong_here += 1
            by_id = {c.criterion_id: c for c in ctx.criteria}
            statuses = (
                {c.criterion_id: c.status.value for c in answered[n].criteria}
                if n in answered
                else {}
            )
            wrong_criteria = [
                {
                    "criterion_id": c["criterion_id"],
                    "policy_id": by_id[c["criterion_id"]].policy_id,
                    "type": (by_id[c["criterion_id"]].criterion_type or "untyped")
                    + (" (indication group)" if by_id[c["criterion_id"]].group else ""),
                    "gold": c["status"],
                    "predicted": statuses.get(c["criterion_id"], "missing"),
                }
                for c in gold["criteria"]
                if statuses.get(c["criterion_id"], "missing") != c["status"]
            ]
            wrong_lines.append(
                {
                    "record_id": rid,
                    "line_no": n,
                    "gold": gold["decision"],
                    "predicted": pred,
                    "valid_output": result.valid,
                    "policies": policies,
                    "wrong_criteria": wrong_criteria,
                }
            )
        decisions = final_line_decisions(rules, result, context)
        member = lookups.get_member(session, claim.member_id)
        try:
            calculation = _calculate(session, claim, member, context.network, decisions)
            tier = review_tier(result, calculation.amounts.totals.allowed_cents, [], high_dollar)
        except CalculationError:
            tier = "FULL (calculation failed)"
        tier = getattr(tier, "value", tier)
        tiers[tier][0] += 1
        tiers[tier][1] += wrong_here > 0
        tiers[tier][2] += wrong_here
    if mismatches:
        raise SystemExit(f"{mismatches} lines differ from the stored predictions: not reproduced")
    return summarize(
        gold_all, pred_all, guard_all, wrong_lines, tiers, lines_by_policy, guard_changed
    )


def wrong_approvals(gold: list[str], predicted: list[str]) -> int:
    return sum(g != "APPROVE" and p == "APPROVE" for g, p in zip(gold, predicted, strict=True))


def summarize(gold, pred, guard, wrong_lines, tiers, lines_by_policy, guard_changed) -> dict:  # noqa: ANN001
    base, with_guard = _decision_metrics(gold, pred), _decision_metrics(gold, guard)
    direction = Counter(f"{w['gold']}->{w['predicted']}" for w in wrong_lines)
    by_policy: dict[str, Counter] = defaultdict(Counter)
    for w in wrong_lines:
        for policy in w["policies"]:
            by_policy[policy][f"{w['gold']}->{w['predicted']}"] += 1
    by_type: Counter = Counter()
    statuses: Counter = Counter()
    for w in wrong_lines:
        for c in w["wrong_criteria"]:
            by_type[c["type"]] += 1
            statuses[f"{c['gold']}->{c['predicted']}"] += 1
    rows = []
    for name, decided in (("v2", pred), ("v2 + guard", guard)):
        metrics = _decision_metrics(gold, decided)
        rows.append(
            {
                "model": name,
                "line_accuracy": metrics["accuracy"],
                "macro_f1": metrics["macro_f1"],
                "deny_precision": metrics["per_class"]["DENY"]["precision"],
                "wrong_approvals": wrong_approvals(gold, decided),
                "wrong_denials": sum(
                    g != "DENY" and p == "DENY" for g, p in zip(gold, decided, strict=True)
                ),
            }
        )
    return {
        "lines": len(gold),
        "wrong_lines": len(wrong_lines),
        "invalid_output_lines": sum(not w["valid_output"] for w in wrong_lines),
        "direction": dict(direction.most_common()),
        "by_policy": {
            p: {"lines": lines_by_policy[p], "wrong": sum(c.values()), "directions": dict(c)}
            for p, c in sorted(by_policy.items(), key=lambda kv: -sum(kv[1].values()))
        },
        "wrong_criteria_by_type": dict(by_type.most_common()),
        "wrong_criterion_statuses": dict(statuses.most_common()),
        "tiers": {
            t: {"claims": c, "with_wrong_line": w, "wrong_lines": n}
            for t, (c, w, n) in sorted(tiers.items())
        },
        "guard": {
            "met_criteria_changed": guard_changed,
            "rows": rows,
            "macro_f1_change": round(with_guard["macro_f1"] - base["macro_f1"], 4),
        },
        "wrong": wrong_lines,
    }


def report(r: dict[str, Any]) -> str:
    def arrow(key: str) -> str:
        gold, predicted = key.split("->")
        return f"{WORDS.get(gold, gold)} predicted as {WORDS.get(predicted, predicted)}"

    out = [
        "# Where model v2 goes wrong (v2 test set)",
        "",
        "Generated by `scripts/verify/v2_errors.py` from the stored answers of the v2 evaluation;",
        "do not edit by hand. Line decisions are derived as the pipeline derives them (D-DEC-1).",
        "",
        f"{r['wrong_lines']} of {r['lines']} model lines are wrong"
        f" ({r['invalid_output_lines']} of them from an invalid answer).",
        "",
        "| Gold decision -> predicted | Lines |",
        "|---|---|",
        *[f"| {arrow(k)} | {v} |" for k, v in r["direction"].items()],
        "",
        "## By policy",
        "",
        "| Policy | Lines | Wrong | Directions |",
        "|---|---|---|---|",
        *[
            f"| {p} | {v['lines']} | {v['wrong']} | "
            + ", ".join(f"{arrow(k)} {n}" for k, n in v["directions"].items())
            + " |"
            for p, v in r["by_policy"].items()
        ],
        "",
        "## Criterion statuses that were wrong on the wrong lines",
        "",
        "| Criterion type | Wrong statuses |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in r["wrong_criteria_by_type"].items()],
        "",
        "| Gold status -> predicted | Criteria |",
        "|---|---|",
        *[f"| {k.replace('->', ' -> ')} | {v} |" for k, v in r["wrong_criterion_statuses"].items()],
        "",
        "## QUICK-tier risk",
        "",
        "Tier from `app/review/tiers.py` with the calculator's total allowed amount",
        "(JSON claims: no low-confidence fields).",
        "",
        "| Tier | Claims | Claims with a wrong line | Wrong lines |",
        "|---|---|---|---|",
        *[
            f"| {t} | {v['claims']} | {v['with_wrong_line']} | {v['wrong_lines']} |"
            for t, v in r["tiers"].items()
        ],
        "",
        "## Evidence guard",
        "",
        f"A MET criterion whose evidence is not in the notes (exact text) becomes NOT_DOCUMENTED:"
        f" {r['guard']['met_criteria_changed']} criteria changed.",
        "",
        "| Model | Line accuracy | Macro-F1 | DENY precision | Wrong approvals | Wrong denials |",
        "|---|---|---|---|---|---|",
        *[
            f"| {row['model']} | {row['line_accuracy']} | {row['macro_f1']} |"
            f" {row['deny_precision']} | {row['wrong_approvals']} | {row['wrong_denials']} |"
            for row in r["guard"]["rows"]
        ],
        "",
    ]
    return "\n".join(out)


def main() -> None:
    with Session(get_engine()) as session:
        result = analyse(session)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(report(result), encoding="utf-8")
    print(report(result))


if __name__ == "__main__":
    main()
