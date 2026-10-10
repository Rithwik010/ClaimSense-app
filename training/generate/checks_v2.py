"""Checks for the v2 decision dataset (Part 2 step 4). The generator runs them and refuses to write
a dataset that fails any; training must not start without them passing.

Per record (every line the answer decides):

- leakage: no answer words in the claim fields or the notes (INSTRUCTIONS.md §9.4);
- target: parses as `SLMOutput`; every rules-passed line answered once; benefit category is a
  candidate;
- V1a check 1 (adapted): the line's diagnoses satisfy its billing article as R15 reads it
  (D-RULE-4), which the engine re-run below also proves;
- V1a check 2 (adapted): the decision is what the pipeline derives from the statuses (D-DEC-1,
  D-POL-3), with no change, and DENY and PEND carry their reasons and missing information;
- V1a check 3: MET and NOT_MET evidence appears word for word in the notes; NOT_DOCUMENTED and
  NOT_APPLICABLE use the fixed texts;
- V1a check 4 (adapted): the line's criteria are exactly what the v2 exact lookup returns, in
  order, each labelled once;
- V1a check 5 (adapted to the types, D-ESI-6, D-GEN-3): no requirement is NOT_APPLICABLE and no
  exclusion is MET;
- rules parity: the engine (RULES_VERSION) on the claim with the generated reference data and the
  record's authorizations gives exactly the stored rules outcome, and the claim passes Groups A and
  B (D-GEN-5);
- the prompt is what decision_v3 renders from the stored inputs.

Across records: no two records share a user message, and no test note appears in train or
validation.
"""

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from app.db.curated import CuratedData
from app.domain.contracts import (
    ContextPackage,
    CriterionStatus,
    IntakeClaim,
    LineDecision,
    RuleOutcomeValue,
    RulesOutcome,
    SLMOutput,
)
from app.ml.derive import derive_line
from app.ml.prompt import NOT_APPLICABLE, NOT_DOCUMENTED, lines_to_decide
from training.generate.checks import _strings
from training.generate.notes import LEAKAGE

FIXED = {
    CriterionStatus.NOT_DOCUMENTED: NOT_DOCUMENTED,
    CriterionStatus.NOT_APPLICABLE: NOT_APPLICABLE,
}


def check_record_v2(
    inputs: Mapping[str, Any],
    messages: Sequence[Mapping[str, str]],
    curated: CuratedData,
    *,
    lookup: Callable[[str, str, Any], list[Any]],
    engine: Callable[[IntakeClaim, list[dict[str, Any]]], RulesOutcome],
    supported: Callable[[IntakeClaim, int], bool],
    render: Callable[[IntakeClaim, RulesOutcome, ContextPackage], str],
) -> list[str]:
    """`lookup(plan_id, code, day)` is the v2 exact lookup for the record's split; `engine` runs
    the rules with the record's authorizations; `supported(claim, line_index)` is R15's check;
    `render` is decision_v3's user message."""
    problems: list[str] = []
    claim = IntakeClaim.model_validate(inputs["claim"])
    rules = RulesOutcome.model_validate(inputs["rules_outcome"])
    context = ContextPackage.model_validate(inputs["context"])
    leaked = [s for s in _strings(inputs["claim"]) if LEAKAGE.search(s)]
    problems += [f"answer word in the claim: {s[:60]!r}" for s in leaked]
    try:
        target = SLMOutput.model_validate_json(messages[2]["content"])
    except ValidationError as exc:
        return problems + [f"target does not parse: {exc.errors()[0]['msg']}"]
    if target.model_dump(mode="json") != inputs["target"]:
        problems.append("target differs from the stored inputs")

    engine_rules = engine(claim, list(inputs.get("authorizations", [])))
    if engine_rules != rules:
        problems.append("rules parity: the engine's outcome differs from the stored one")
    if rules.claim_outcome is not RuleOutcomeValue.PASS:
        problems.append(f"claim outcome {rules.claim_outcome.value}: Groups A and B must pass")
    if render(claim, rules, context) != messages[1]["content"]:
        problems.append("the prompt is not what decision_v3 renders from the inputs")

    expected = lines_to_decide(rules)
    answered = Counter(line.line_no for line in target.lines)
    if sorted(answered) != expected or any(n > 1 for n in answered.values()):
        problems.append(f"answered lines {sorted(answered)} != lines to decide {expected}")
    by_line = {c.line_no: c for c in context.lines}
    flags = {o.line_no: o.flags for o in rules.line_outcomes}
    notes = claim.clinical_notes
    for line in target.lines:
        label = f"line {line.line_no}"
        line_context = by_line.get(line.line_no)
        if line_context is None:
            problems.append(f"{label}: no context")
            continue
        service = claim.service_lines[line.line_no - 1]
        if not supported(claim, line.line_no - 1):
            problems.append(f"{label}: diagnoses fail R15 (check 1)")
        shown = [
            c.criterion_id
            for c in lookup(context.plan_id, service.procedure_code, service.date_of_service)
        ]
        retrieved = [c.criterion_id for c in line_context.criteria]
        if retrieved != shown:
            problems.append(
                f"{label}: context criteria {retrieved} != exact lookup {shown} (check 4)"
            )
        if [r.criterion_id for r in line.criteria] != retrieved:
            problems.append(f"{label}: labelled criteria differ from the retrieved ones (check 4)")
        candidates = {f.benefit_category for f in line_context.candidate_benefits}
        if line.benefit_category not in candidates:
            problems.append(f"{label}: benefit category {line.benefit_category} not a candidate")
        types = {c.criterion_id: c.criterion_type for c in line_context.criteria}
        for result in line.criteria:
            name = f"{label}: {result.criterion_id} {result.status.value}"
            fixed = FIXED.get(result.status)
            if fixed is not None and result.evidence != fixed:
                problems.append(f"{name} needs the evidence {fixed!r} (check 3)")
            if fixed is None and result.evidence not in notes:
                problems.append(f"{name} evidence is not a quote from the notes (check 3)")
            kind = types.get(result.criterion_id)
            if kind == "requirement" and result.status is CriterionStatus.NOT_APPLICABLE:
                problems.append(f"{name}: a requirement is never NOT_APPLICABLE (check 5)")
            if kind == "exclusion" and result.status is CriterionStatus.MET:
                problems.append(f"{name}: an exclusion is never MET (check 5)")
        derived = derive_line(line, line_context.criteria, flags[line.line_no])
        if derived.decision is not line.decision or derived.changed:
            problems.append(f"{label}: decision {line.decision.value} != derived (check 2)")
        if line.decision is not LineDecision.APPROVE and not line.reasons:
            problems.append(f"{label}: {line.decision.value} without a reason (check 2)")
        if line.decision is LineDecision.PEND and not line.missing_information:
            problems.append(f"{label}: PEND without missing information (check 2)")
        if line.decision is LineDecision.APPROVE and (line.reasons or line.missing_information):
            problems.append(f"{label}: APPROVE with reasons or missing information (check 2)")
    return problems


def duplicate_problems(splits: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[str]:
    """No user message twice anywhere; no test note in train or validation."""
    problems = []
    seen: dict[str, str] = {}
    for records in splits.values():
        for record in records:
            user = record["messages"][1]["content"]
            if user in seen:
                problems.append(
                    f"{record['metadata']['record_id']}: same user message as {seen[user]}"
                )
            seen[user] = record["metadata"]["record_id"]
    training_notes = {
        _notes(record) for split in ("train", "validation") for record in splits.get(split, [])
    }
    shared = sum(1 for record in splits.get("test", []) if _notes(record) in training_notes)
    if shared:
        problems.append(f"{shared} test notes also appear in train or validation")
    return problems


def _notes(record: Mapping[str, Any]) -> str:
    text = record["messages"][1]["content"]
    start = text.index("Clinical notes:")
    return text[start : text.index("\nRULES_RESULT", start)]
