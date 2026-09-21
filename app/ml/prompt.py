"""Decision prompt rendering (INSTRUCTIONS.md §8.5). Used for inference and for the training data,
so the model always sees the same text.

The system message is the versioned file `prompts/<version>.txt`. The user message has the sections
CLAIM, RULES_RESULT, PLAN_BENEFITS and COVERAGE_CRITERIA, then LINES TO DECIDE. Descriptions and
the codes each policy covers are looked up by the caller (database in the pipeline, curated files
in the generators). No money appears in the prompt (H1).
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.domain.contracts import (
    ContextPackage,
    IntakeClaim,
    LineRuleOutcome,
    RulesOutcome,
)

PROMPT_VERSION = "decision_v1"
PROMPTS_DIR = Path(__file__).parent / "prompts"
NOT_DOCUMENTED = "Not documented in the clinical notes."


@dataclass(frozen=True)
class PromptLookups:
    icd10_descriptions: dict[str, str]
    procedure_descriptions: dict[str, str]
    policy_codes: dict[str, list[str]]  # policy ID -> procedure codes it covers


def system_prompt(version: str = PROMPT_VERSION) -> str:
    return (PROMPTS_DIR / f"{version}.txt").read_text(encoding="utf-8").strip()


def format_icd10(code: str) -> str:
    return f"{code[:3]}.{code[3:]}" if len(code) > 3 else code


def age_on(date_of_birth: date, day: date) -> int:
    return (
        day.year
        - date_of_birth.year
        - ((day.month, day.day) < (date_of_birth.month, date_of_birth.day))
    )


def lines_to_decide(rules: RulesOutcome) -> list[int]:
    return [outcome.line_no for outcome in rules.line_outcomes if outcome.outcome == "PASS"]


def _rule_line(outcome: LineRuleOutcome) -> str:
    if outcome.outcome == "DENY":
        reasons = ", ".join(outcome.reason_codes)
        return f"Line {outcome.line_no}: DENIED by rule ({reasons}); do not decide this line"
    if "NCCI_BYPASS" in outcome.flags:
        return (
            f"Line {outcome.line_no}: PASS, flag NCCI_BYPASS (a bypass modifier was used; check "
            "that the notes show a separate, distinct service)"
        )
    return f"Line {outcome.line_no}: PASS"


def render_user_message(
    claim: IntakeClaim, rules: RulesOutcome, context: ContextPackage, lookups: PromptLookups
) -> str:
    first_day = min(line.date_of_service for line in claim.service_lines)
    patient = claim.patient
    parts = [
        "CLAIM",
        f"Claim ID: {claim.claim_id}",
        f"Patient: {age_on(patient.date_of_birth, first_day)}-year-old, sex {patient.sex.value}",
        f"Plan: {context.plan_id} ({context.plan_type}); provider network: {context.network.value}",
        "Diagnoses:",
    ]
    for pointer, code in zip("ABCDEFGHIJKL", claim.diagnoses, strict=False):
        description = lookups.icd10_descriptions.get(code, "")
        parts.append(f"  {pointer}. {format_icd10(code)} {description}".rstrip())
    parts.append("Service lines:")
    for line in claim.service_lines:
        description = lookups.procedure_descriptions.get(line.procedure_code, "")
        modifiers = " ".join(line.modifiers) or "none"
        parts.append(
            f"  {line.line_no}. {line.date_of_service.isoformat()} | POS {line.place_of_service} | "
            f"{line.procedure_code} {description} | modifiers: {modifiers} | units {line.units} | "
            f"diagnoses: {''.join(line.diagnosis_pointers)}"
        )
    parts += ["Clinical notes:", f"  {claim.clinical_notes or '(none)'}", ""]

    parts.append("RULES_RESULT")
    flags = f" (claim flags: {', '.join(rules.flags)})" if rules.flags else ""
    parts.append(f"Claim outcome: {rules.claim_outcome.value}{flags}")
    parts += [_rule_line(outcome) for outcome in rules.line_outcomes]
    parts.append("")

    parts.append("PLAN_BENEFITS")
    parts.append(f"Excluded procedure codes: {', '.join(context.excluded_codes) or 'none'}")
    for line_context in context.lines:
        parts.append(
            f"Line {line_context.line_no} ({line_context.procedure_code}) candidate categories:"
        )
        for fact in line_context.candidate_benefits:
            limit = (
                f"visit limit {fact.visit_limit} per year, {fact.visits_used} used"
                if fact.visit_limit
                else "no visit limit"
            )
            parts.append(
                f"  - {fact.benefit_category}: {'covered' if fact.covered else 'not a benefit'}; "
                f"prior authorization {'required' if fact.auth_required else 'not required'}; "
                f"{limit}; cost share {fact.cost_share_rule.value}"
            )
    parts.append("")

    parts.append("COVERAGE_CRITERIA")
    for line_context in context.lines:
        parts.append(f"Line {line_context.line_no} ({line_context.procedure_code}):")
        if not line_context.criteria:
            parts.append("  No criteria retrieved.")
        for criterion in line_context.criteria:
            codes = ", ".join(lookups.policy_codes.get(criterion.policy_id, []))
            parts.append(
                f"  [{criterion.criterion_id}] {criterion.policy_title} "
                f"(policy {criterion.policy_id}, "
                f"covers {codes}): {criterion.text} Source: {criterion.source}"
            )
    parts.append("")
    parts.append(f"LINES TO DECIDE: {', '.join(str(n) for n in lines_to_decide(rules))}")
    return "\n".join(parts)
