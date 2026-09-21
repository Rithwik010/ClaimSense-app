"""Clinical-note templates (templates/clinical_notes.yaml): loading, validation and slot filling."""

import itertools
import random
import re
import string
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from training.generate.codebook import Codebook

TEMPLATES_PATH = Path(__file__).parent / "templates" / "clinical_notes.yaml"
TEMPLATE_SETS = ("A", "B")
MAX_CRITERIA_PER_PROFILE = 3  # RAG_TOP_K: every evaluated criterion must fit in the retrieved set
AUTO_SLOTS = {"units", "procedure"}

# Words that must never appear in claim fields or clinical notes (INSTRUCTIONS.md §9.4).
LEAKAGE = re.compile(
    r"\b(approve|approved|deny|denied|reject|rejected|pend|pended)\b"
    r"|not covered|medically necessary",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CriterionTemplate:
    criterion_id: str
    kind: str  # required | exclusion
    met: dict[str, tuple[str, ...]]
    not_met: dict[str, tuple[str, ...]]
    missing: str
    with_not_met: tuple[str, ...]
    diagnoses_when_not_met: tuple[str, ...]


@dataclass(frozen=True)
class Profile:
    policy_id: str
    profile_id: str
    codes: tuple[str, ...]
    diagnoses: tuple[str, ...]
    diagnoses_all_of: tuple[tuple[str, ...], ...]
    criteria: tuple[str, ...]  # full criterion IDs
    units: dict[str, str]
    pos: tuple[str, ...]
    slots: dict[str, Any]
    lead: dict[str, tuple[str, ...]]
    exclusion_scenarios: bool

    @property
    def key(self) -> str:
        return f"{self.policy_id}/{self.profile_id}"


@dataclass(frozen=True)
class Templates:
    filler: dict[str, tuple[str, ...]]
    plan_line: dict[str, str]
    office_visit: dict[str, tuple[str, ...]]
    distinct: dict[str, dict[str, Any]]
    unrelated: tuple[tuple[str, dict[str, str]], ...]
    criteria: dict[str, CriterionTemplate]
    profiles: dict[str, tuple[Profile, ...]]

    def template_sets(self, policy_id: str) -> set[str]:
        """Template sets available for every profile of a policy."""
        available = set(TEMPLATE_SETS)
        for profile in self.profiles[policy_id]:
            for criterion_id in profile.criteria:
                available &= set(self.criteria[criterion_id].met)
            available &= set(profile.lead)
        return available


def _sets(value: Any) -> dict[str, tuple[str, ...]]:
    return {k: tuple(v) if isinstance(v, list) else (v,) for k, v in (value or {}).items()}


@lru_cache
def load_templates() -> Templates:
    data = yaml.safe_load(TEMPLATES_PATH.read_text(encoding="utf-8"))
    criteria: dict[str, CriterionTemplate] = {}
    profiles: dict[str, tuple[Profile, ...]] = {}
    for policy_id, policy in data["policies"].items():
        for short, c in policy["criteria"].items():
            full = f"{policy_id}.{short}"
            criteria[full] = CriterionTemplate(
                criterion_id=full,
                kind=c["kind"],
                met=_sets(c.get("met")),
                not_met=_sets(c.get("not_met")),
                missing=c["missing"],
                with_not_met=tuple(f"{policy_id}.{x}" for x in c.get("with_not_met", [])),
                diagnoses_when_not_met=tuple(c.get("diagnoses_when_not_met", [])),
            )
        profiles[policy_id] = tuple(
            Profile(
                policy_id=policy_id,
                profile_id=p["id"],
                codes=tuple(p["codes"]),
                diagnoses=tuple(p.get("diagnoses", [])),
                diagnoses_all_of=tuple(tuple(group) for group in p.get("diagnoses_all_of", [])),
                criteria=tuple(f"{policy_id}.{x}" for x in p["criteria"]),
                units={str(k): str(v) for k, v in (p.get("units") or {}).items()},
                pos=tuple(p["pos"]),
                slots=p.get("slots") or {},
                lead=_sets(p.get("lead")),
                exclusion_scenarios=not p.get("no_exclusion_scenarios", False),
            )
            for p in policy["profiles"]
        )
    return Templates(
        filler=_sets(data["filler"]),
        plan_line=data["plan_line"],
        office_visit=_sets(data["office_visit"]),
        distinct=data["distinct_service"],
        unrelated=tuple(
            (u["code"], {"A": u["A"], "B": u["B"]}) for u in data["unrelated_conditions"]
        ),
        criteria=criteria,
        profiles=profiles,
    )


def profile_diagnosis_sets(profile: Profile) -> list[tuple[str, ...]]:
    if profile.diagnoses_all_of:
        return list(itertools.product(*profile.diagnoses_all_of))
    return [(code,) for code in profile.diagnoses]


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def draw_slots(rng: random.Random, spec: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, choice in spec.items():
        if isinstance(choice, str) and re.fullmatch(r"[0-9]+-[0-9]+", choice):
            low, high = (int(x) for x in choice.split("-"))
            values[name] = str(rng.randint(low, high))
        elif isinstance(choice, list):
            picked = rng.choice(choice)
            if isinstance(picked, dict):
                values.update({k: str(v) for k, v in picked.items()})
            else:
                values[name] = str(picked)
        else:
            values[name] = str(choice)
    return values


def fill(template: str, slots: dict[str, str]) -> str:
    return template.format_map(slots)


def validate_templates(templates: Templates, codebook: Codebook) -> list[str]:
    """Every problem found (empty when the templates are consistent with the data)."""
    problems: list[str] = []
    curated = codebook.curated
    known = curated.criteria()

    def check_text(where: str, text: str) -> None:
        if LEAKAGE.search(text):
            problems.append(f"{where}: leakage word in {text!r}")

    for criterion_id, template in templates.criteria.items():
        if criterion_id not in known:
            problems.append(f"{criterion_id}: not a criterion in data/curated")
        if template.kind not in ("required", "exclusion"):
            problems.append(f"{criterion_id}: unknown kind {template.kind}")
        for group in (template.met, template.not_met):
            for sentences in group.values():
                for sentence in sentences:
                    check_text(criterion_id, sentence)
        for code in template.diagnoses_when_not_met:
            if code not in codebook.icd10:
                problems.append(f"{criterion_id}: {code} is not a FY2027 ICD-10-CM code")
    for code, texts in templates.unrelated:
        if code not in codebook.icd10:
            problems.append(f"unrelated condition {code} is not a FY2027 code")
        for text in texts.values():
            check_text(f"unrelated {code}", text)
    for sets in (templates.filler, templates.office_visit):
        for sentences in sets.values():
            for sentence in sentences:
                check_text("shared sentence", sentence)
    for policy_id, profiles in templates.profiles.items():
        policy = curated.policies.get(policy_id)
        if policy is None:
            problems.append(f"{policy_id}: unknown policy")
            continue
        sets = templates.template_sets(policy_id)
        if "B" not in sets or (policy.split == "TRAIN" and "A" not in sets):
            problems.append(f"{policy_id}: template sets {sorted(sets)} do not cover its split")
        for profile in profiles:
            where = profile.key
            if not set(profile.codes) <= set(policy.procedure_codes):
                problems.append(f"{where}: codes outside the policy")
            if not 1 <= len(profile.criteria) <= MAX_CRITERIA_PER_PROFILE:
                problems.append(f"{where}: 1 to {MAX_CRITERIA_PER_PROFILE} criteria allowed")
            if not set(profile.criteria) <= set(templates.criteria):
                problems.append(f"{where}: criteria without templates")
            for combination in profile_diagnosis_sets(profile):
                for dx in combination:
                    if dx not in codebook.icd10:
                        problems.append(f"{where}: {dx} is not a FY2027 ICD-10-CM code")
                for code in profile.codes:
                    if not codebook.supported(code, list(combination)):
                        problems.append(f"{where}: {combination} does not support {code}")
            available = (
                set(profile.slots)
                | AUTO_SLOTS
                | {
                    k
                    for v in profile.slots.values()
                    if isinstance(v, list)
                    for d in v
                    if isinstance(d, dict)
                    for k in d
                }
            )
            sentences = [s for group in profile.lead.values() for s in group]
            for criterion_id in profile.criteria:
                template = templates.criteria[criterion_id]
                for group in (template.met, template.not_met):
                    sentences += [s for group_sentences in group.values() for s in group_sentences]
            for sentence in sentences:
                check_text(where, sentence)
                missing = placeholders(sentence) - available
                if missing:
                    problems.append(f"{where}: slots {sorted(missing)} undefined for {sentence!r}")
    return problems
