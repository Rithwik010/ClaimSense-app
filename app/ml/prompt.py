"""Decision prompt rendering (INSTRUCTIONS.md §8.5). Used for inference and for the training data,
so the model always sees the same text.

The system message is the versioned file `prompts/<version>.txt`. The user message has the sections
CLAIM, RULES_RESULT, PLAN_BENEFITS and COVERAGE_CRITERIA, then LINES TO DECIDE. Descriptions and
the codes each policy covers are looked up by the caller (database in the pipeline, curated files
in the generators). No money appears in the prompt (H1).

decision_v2 (model v1) is rendered byte for byte as it was trained. decision_v3 (model v2, policy
set v2) also shows each criterion's type and group (no source), words the NCCI_BYPASS flag by the
modifier that allowed it (D-RULE-8), and explains the flags NCS_WITHOUT_EMG, FACET_TWO_REGIONS
and EXTENDED_TESTING (D-RULE-6).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.domain.contracts import (
    ContextPackage,
    IntakeClaim,
    LineRuleOutcome,
    RetrievedCriterion,
    RulesOutcome,
)

PROMPT_VERSION = "decision_v2"  # model v1; decision_v1: criteria as met true/false (superseded)
PROMPT_V3 = "decision_v3"  # model v2 (Part 2 step 2)
PROMPT_VERSIONS = (PROMPT_VERSION, PROMPT_V3)
PROMPTS_DIR = Path(__file__).parent / "prompts"
NOT_DOCUMENTED = "Not documented in the clinical notes."
NOT_APPLICABLE = "Does not apply to this service."

# decision_v3: what the notes must show for an NCCI_BYPASS line, by the modifier's place in the
# NCCI Policy Manual (data/curated/ncci_ptp_modifiers.csv; plain-language wording, no CPT text).
BYPASS_PHRASES = {
    "DISTINCT": "a separate, distinct service (another session, site or organ, or a separate "
    "lesion or injury)",
    "SEPARATE_EM": "a significant, separately identifiable evaluation and management service, "
    "beyond the usual care of the procedure",
    "SURGERY_DECISION": "that the visit led to the decision for surgery",
    "SITES": "that the services were at different anatomic sites",
    "OTHER": "the situation the modifier reports",
}
FLAG_NOTES = {
    "NCS_WITHOUT_EMG": "a nerve conduction study with no needle EMG on the claim: the criterion "
    "for a nerve conduction study done alone applies",
    "FACET_TWO_REGIONS": "facet procedures in two spinal regions on one date: a note for the "
    "reviewer",
    "EXTENDED_TESTING": "more than 8 hours of testing on the claim: a note for the reviewer",
}


def bypass_phrase_keys(placements: Mapping[str, tuple[str, frozenset[str]]]) -> dict[str, str]:
    """Modifier -> BYPASS_PHRASES key, from each NCCI PTP-associated modifier's placement and the
    paired code's global periods (25: 000, 010, XXX; 57: 090)."""
    keys = {}
    for modifier, (placement, global_days) in placements.items():
        if placement == "NOT_EM":
            keys[modifier] = "DISTINCT"
        elif placement == "DIFFERENT_SITES":
            keys[modifier] = "SITES"
        elif placement == "EM_WITH_PROCEDURE" and "090" in global_days:
            keys[modifier] = "SURGERY_DECISION"
        elif placement == "EM_WITH_PROCEDURE" and global_days:
            keys[modifier] = "SEPARATE_EM"
        else:
            keys[modifier] = "OTHER"
    return keys


@dataclass(frozen=True)
class PromptLookups:
    icd10_descriptions: dict[str, str]
    procedure_descriptions: dict[str, str]
    policy_codes: dict[str, list[str]]  # policy ID -> procedure codes it covers
    bypass_keys: dict[str, str] = field(default_factory=dict)  # decision_v3: bypass_phrase_keys


def system_prompt(version: str = PROMPT_VERSION) -> str:
    if version not in PROMPT_VERSIONS:
        raise ValueError(f"unknown prompt version {version!r}")
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


def _bypass_note(claim: IntakeClaim, line_no: int, lookups: PromptLookups) -> str:
    """decision_v3: the modifiers on the line and the other lines of its date that allow a bypass,
    and what the notes must show for each."""
    line = claim.service_lines[line_no - 1]
    same_day = [x for x in claim.service_lines if x.date_of_service == line.date_of_service]
    found = sorted(
        {m for x in same_day for m in x.modifiers if m in lookups.bypass_keys},
        key=lambda m: (m not in line.modifiers, m),
    )
    if not found:
        return "check that the notes show what the bypass modifier reports"
    by_key: dict[str, list[str]] = {}
    for modifier in found:
        by_key.setdefault(lookups.bypass_keys[modifier], []).append(modifier)
    return "; ".join(
        f"modifier {', '.join(mods)}: check that the notes show {BYPASS_PHRASES[key]}"
        for key, mods in by_key.items()
    )


def _rule_line_v3(outcome: LineRuleOutcome, claim: IntakeClaim, lookups: PromptLookups) -> str:
    if outcome.outcome == "DENY":
        return _rule_line(outcome)
    notes = [
        f"flag NCCI_BYPASS ({_bypass_note(claim, outcome.line_no, lookups)})"
        if flag == "NCCI_BYPASS"
        else f"flag {flag} ({FLAG_NOTES[flag]})"
        if flag in FLAG_NOTES
        else f"flag {flag}"
        for flag in outcome.flags
    ]
    return f"Line {outcome.line_no}: PASS" + (f", {', '.join(notes)}" if notes else "")


def _criterion_v3(criterion: RetrievedCriterion) -> str:
    kind = criterion.criterion_type or "requirement"
    label = f"{kind}; indication group" if criterion.group else kind
    return f"    [{criterion.criterion_id}] ({label}) {criterion.text}"


def render_user_message(
    claim: IntakeClaim,
    rules: RulesOutcome,
    context: ContextPackage,
    lookups: PromptLookups,
    version: str = PROMPT_VERSION,
) -> str:
    """The user message for `version` (decision_v2 unchanged for model v1; decision_v3)."""
    v3 = version == PROMPT_V3
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
    parts += [
        _rule_line_v3(outcome, claim, lookups) if v3 else _rule_line(outcome)
        for outcome in rules.line_outcomes
    ]
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
        policies: dict[str, list] = {}  # retrieval order, grouped under one header per policy
        for criterion in line_context.criteria:
            policies.setdefault(criterion.policy_id, []).append(criterion)
        for policy_id, criteria in policies.items():
            codes = ", ".join(lookups.policy_codes.get(policy_id, []))
            parts.append(f"  Policy {policy_id} {criteria[0].policy_title} (covers {codes}):")
            parts += [
                _criterion_v3(c) if v3 else f"    [{c.criterion_id}] {c.text} ({c.source})"
                for c in criteria
            ]
    parts.append("")
    parts.append(f"LINES TO DECIDE: {', '.join(str(n) for n in lines_to_decide(rules))}")
    return "\n".join(parts)
