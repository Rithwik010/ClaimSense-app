"""Leakage and quality checks for the decision dataset (INSTRUCTIONS.md §9.4). The dataset generator
runs these and refuses to write a dataset that fails; training must not start without them passing.
"""

import json
from collections import Counter
from typing import Any

from pydantic import ValidationError

from app.db.curated import CuratedData
from app.domain.contracts import ContextPackage, IntakeClaim, LineDecision, RulesOutcome, SLMOutput
from app.ml.prompt import lines_to_decide
from training.generate.notes import LEAKAGE


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def check_record(
    inputs: dict[str, Any], messages: list[dict[str, str]], curated: CuratedData
) -> list[str]:
    """Problems with one record (empty when it is clean)."""
    problems = []
    claim = IntakeClaim.model_validate(inputs["claim"])
    rules = RulesOutcome.model_validate(inputs["rules_outcome"])
    context = ContextPackage.model_validate(inputs["context"])
    for text in _strings(inputs["claim"]):
        if LEAKAGE.search(text):
            problems.append(f"leakage word in claim field: {text[:80]!r}")
    try:
        target = SLMOutput.model_validate_json(messages[-1]["content"])
    except ValidationError as error:
        return problems + [
            f"assistant message is not a valid SLMOutput: {error.error_count()} errors"
        ]
    if target != SLMOutput.model_validate(inputs["target"]):
        problems.append("assistant message differs from the stored target")
    known = curated.criteria()
    decide = lines_to_decide(rules)
    if sorted(line.line_no for line in target.lines) != decide or len(target.lines) != len(
        set(decide)
    ):
        problems.append(
            f"target lines {[t.line_no for t in target.lines]} != lines to decide {decide}"
        )
    contexts = {c.line_no: c for c in context.lines}
    for line in target.lines:
        line_context = contexts.get(line.line_no)
        if line_context is None:
            problems.append(f"line {line.line_no} has no context")
            continue
        retrieved = {c.criterion_id for c in line_context.criteria}
        for result in line.criteria:
            if result.criterion_id not in known:
                problems.append(f"unknown criterion {result.criterion_id}")
            if result.criterion_id not in retrieved:
                problems.append(
                    f"criterion {result.criterion_id} was not retrieved for line {line.line_no}"
                )
        if line.benefit_category not in {
            f.benefit_category for f in line_context.candidate_benefits
        }:
            problems.append(
                f"line {line.line_no}: category {line.benefit_category} is not a candidate"
            )
        if line.decision in (LineDecision.DENY, LineDecision.PEND) and not line.reasons:
            problems.append(f"line {line.line_no}: {line.decision.value} without a reason")
        if line.decision == LineDecision.PEND and not line.missing_information:
            problems.append(f"line {line.line_no}: PEND without missing information")
        for reason in line.reasons:
            if reason not in curated.reason_codes:
                problems.append(
                    f"line {line.line_no}: reason {reason} is not in reason_code_map.csv"
                )
    if claim.claim_id != context.claim_id:
        problems.append("claim and context IDs differ")
    return problems


def distribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Class distribution for the data card."""
    decisions: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    for record in records:
        target = json.loads(record["messages"][-1]["content"])
        for line in target["lines"]:
            decisions[line["decision"]] += 1
            reasons.update(line["reasons"])
            categories[line["benefit_category"]] += 1
    meta = [r["metadata"] for r in records]
    return {
        "records": len(records),
        "model_lines": sum(decisions.values()),
        "line_decisions": dict(decisions.most_common()),
        "reasons": dict(reasons.most_common()),
        "benefit_categories": dict(categories.most_common()),
        "claim_decisions": dict(Counter(m["claim_decision"] for m in meta).most_common()),
        "complexity": dict(Counter(m["complexity"] for m in meta).most_common()),
        "scenario_types": dict(Counter(m["scenario_type"] for m in meta).most_common()),
        "policies": dict(Counter(p for m in meta for p in m["policy_ids"]).most_common()),
        "template_sets": dict(Counter(m["template_id"] for m in meta).most_common()),
        "out_of_network": sum(1 for m in meta if m["network"] == "OUT_OF_NETWORK"),
        "lines_denied_by_rules": sum(
            1 for m in meta for label in m["line_labels"] if label["source"] == "RULE"
        ),
    }
