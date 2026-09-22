"""Leakage and quality checks for the decision dataset (INSTRUCTIONS.md §9.4). The dataset generator
runs these and refuses to write a dataset that fails; training must not start without them passing.
"""

import json
from collections import Counter
from typing import Any

from pydantic import ValidationError

from app.db.curated import CuratedData
from app.domain.contracts import (
    ContextPackage,
    CriterionStatus,
    IntakeClaim,
    LineDecision,
    RulesOutcome,
    SLMOutput,
)
from app.ml.prompt import NOT_APPLICABLE, NOT_DOCUMENTED, lines_to_decide
from training.generate.notes import LEAKAGE


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


FIXED_EVIDENCE = {
    CriterionStatus.NOT_DOCUMENTED: NOT_DOCUMENTED,
    CriterionStatus.NOT_APPLICABLE: NOT_APPLICABLE,
}


def _status_problems(line: Any, covering: set[str], notes: str) -> list[str]:
    """Evidence quotes the notes (MET, NOT_MET) or is the fixed text; other policies' criteria are
    NOT_APPLICABLE."""
    problems = []
    for result in line.criteria:
        label = f"line {line.line_no}: {result.criterion_id} {result.status.value}"
        fixed = FIXED_EVIDENCE.get(result.status)
        if fixed is not None and result.evidence != fixed:
            problems.append(f"{label} needs the evidence {fixed!r}")
        if fixed is None and result.evidence not in notes:
            problems.append(f"{label} evidence is not a quote from the notes")
        if result.criterion_id not in covering and result.status is not (
            CriterionStatus.NOT_APPLICABLE
        ):
            problems.append(f"{label}: its policy does not cover the code")
    return problems


def _decision_problems(line: Any, flags: set[str]) -> list[str]:
    """The decision follows from the statuses (prompt decision_v2)."""
    statuses = {result.status for result in line.criteria}
    label = f"line {line.line_no}: {line.decision.value}"
    if line.decision is LineDecision.APPROVE and statuses & {
        CriterionStatus.NOT_MET,
        CriterionStatus.NOT_DOCUMENTED,
    }:
        return [f"{label} with a NOT_MET or NOT_DOCUMENTED criterion"]
    if line.decision is LineDecision.PEND and not (
        CriterionStatus.NOT_DOCUMENTED in statuses or "NCCI_BYPASS" in flags
    ):
        return [f"{label} without a NOT_DOCUMENTED criterion or the NCCI_BYPASS flag"]
    if line.decision is LineDecision.PEND and CriterionStatus.NOT_MET in statuses:
        return [f"{label} with a NOT_MET criterion (should be DENY)"]
    if "DN_CONDITIONAL_EXCLUSION" in line.reasons and CriterionStatus.NOT_MET not in statuses:
        return [f"{label} for an exclusion without a NOT_MET criterion"]
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
        retrieved = [c.criterion_id for c in line_context.criteria]
        listed = [result.criterion_id for result in line.criteria]
        for criterion_id in listed:
            if criterion_id not in known:
                problems.append(f"unknown criterion {criterion_id}")
        if listed != retrieved:
            problems.append(
                f"line {line.line_no}: criteria {listed} are not the retrieved {retrieved} in order"
            )
        covering = {
            c.criterion_id
            for c in line_context.criteria
            if line_context.procedure_code in curated.policies[c.policy_id].procedure_codes
        }
        problems += _status_problems(line, covering, claim.clinical_notes)
        flags = set(line_context.rule_flags)
        problems += _decision_problems(line, flags)
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
    statuses: Counter[str] = Counter()
    for record in records:
        target = json.loads(record["messages"][-1]["content"])
        for line in target["lines"]:
            decisions[line["decision"]] += 1
            statuses.update(c["status"] for c in line["criteria"])
            reasons.update(line["reasons"])
            categories[line["benefit_category"]] += 1
    meta = [r["metadata"] for r in records]
    return {
        "records": len(records),
        "model_lines": sum(decisions.values()),
        "line_decisions": dict(decisions.most_common()),
        "reasons": dict(reasons.most_common()),
        "benefit_categories": dict(categories.most_common()),
        "criterion_statuses": dict(statuses.most_common()),
        "claim_decisions": dict(Counter(m["claim_decision"] for m in meta).most_common()),
        "complexity": dict(Counter(m["complexity"] for m in meta).most_common()),
        "scenario_types": dict(Counter(m["scenario_type"] for m in meta).most_common()),
        "policies": dict(Counter(p for m in meta for p in m["policy_ids"]).most_common()),
        "template_sets": dict(Counter(m["template_id"] for m in meta).most_common()),
        "out_of_network": sum(1 for m in meta if m["network"] == "OUT_OF_NETWORK"),
        "records_with_missed_criteria": sum(1 for m in meta if m.get("criteria_missed")),
        "lines_denied_by_rules": sum(
            1 for m in meta for label in m["line_labels"] if label["source"] == "RULE"
        ),
    }
