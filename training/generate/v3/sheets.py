"""Fact sheets as JSON (generator v3, Phase 2; SPEC.md): what every writer works from.

A sheet holds the patient (age and sex), the visit and line dates, the clinic, the lines, the
facts (training.generate.v3.facts), a timeline of dated events, the distractors and the style card,
and the label: v2's line labels and the target with a placeholder per fact (Phase 4 puts the quotes
in).
The inputs to rebuild the record (claim, rules outcome, context, authorizations) travel with it.
"""

import random
import re
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from training.generate.claims import claim_decision
from training.generate.scenarios import Scenario
from training.generate.v3.config import config, phrases
from training.generate.v3.facts import Draft, Fact, fact_to_json, fill_dates

AGO = re.compile(
    r"(\d+)\s*(years?|y|months?|mos?|weeks?|wks?|wk|days?|d)\b[^.;]{0,24}?\bago\b", re.IGNORECASE
)
UNIT_DAYS = {"y": 365, "m": 30, "w": 7, "d": 1}
PROCEDURE_NAMES = {  # prior_procedure report blocks: the procedure the fact reports on
    "POL-PAIN-001.c8": "transforaminal epidural steroid injection",
    "POL-PAIN-002.c5": "diagnostic medial branch block",
    "POL-SURG-002.c3": "colonoscopy",
    "POL-SURG-002.c5": "colonoscopy",
    "POL-WOUND-001.c4": "sharp debridement",
    "POL-DX-001.c6": "sleep study",
    "POL-CAR-001.c6": "echocardiogram",
}
SEX_WORDS = {"F": ("woman", "female", "F", "She", "she"), "M": ("man", "male", "M", "He", "he")}
SEX_DEFAULT = ("patient", "patient", "U", "They", "they")


def _choose(rng: random.Random, weights: Mapping[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def age_on(birth: date | str, day: date) -> int:
    born = birth if isinstance(birth, date) else date.fromisoformat(birth)
    return day.year - born.year - ((day.month, day.day) < (born.month, born.day))


def encounter_date(scenario: Scenario) -> date:
    """The note's visit: the first line with a policy, else the last line."""
    lines = scenario.claim.service_lines
    for line, label in zip(lines, scenario.line_labels, strict=True):
        if (
            label.get("source") == "MODEL"
            and scenario.context.lines
            and any(c.line_no == line.line_no and c.criteria for c in scenario.context.lines)
        ):
            return line.date_of_service
    return max(line.date_of_service for line in lines)


def _event_days(fact: Fact) -> int | None:
    """Days before the visit of the event a fact reports ("... 4 months ago"), if it says."""
    found = AGO.search(fact.text.get("A") or next(iter(fact.text.values()), ""))
    if not found:
        return None
    return int(found.group(1)) * UNIT_DAYS[found.group(2)[0].lower()]


def timeline(facts: Sequence[Fact], visit: date, rng: random.Random) -> list[dict[str, str]]:
    events = []
    for fact in facts:
        if fact.placement.get("report") == "prior_procedure" and fact.criterion_id:
            days = _event_days(fact) or rng.randint(20, 120)
            events.append(
                {
                    "date": (visit - timedelta(days=days)).isoformat(),
                    "event": PROCEDURE_NAMES.get(fact.criterion_id, "prior procedure"),
                    "fact_id": fact.fact_id,
                }
            )
        for slot, days in fact.date_slots.items():
            events.append(
                {
                    "date": (visit - timedelta(days=days)).isoformat(),
                    "event": f"symptom onset ({slot})",
                    "fact_id": fact.fact_id,
                }
            )
    return sorted(events, key=lambda e: e["date"])


def distractors(
    rng: random.Random, clinic: str, extra_diagnoses: Sequence[str], claim_codes: Sequence[str]
) -> dict[str, Any]:
    """Conditions (the claim's extra diagnoses first), medications, allergies, social history, a
    past episode and the review-of-systems lines, without the clinic's excluded topics."""
    sec, tricky = phrases("sections"), config()["tricky"]
    exclude = set(sec["clinics"].get(clinic, {}).get("exclude", ()))

    def allowed(items: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return [i for i in items if not set(i.get("topics", ())) & exclude]

    conditions = [c for c in sec["conditions"] if c["code"] in extra_diagnoses]
    more = [
        c
        for c in allowed(sec["conditions"])
        if c["code"] not in extra_diagnoses and c["code"] not in claim_codes
    ]
    low, high = tricky["distractor_conditions"]["min"], tricky["distractor_conditions"]["max"]
    want = max(len(conditions), rng.randint(low, high))
    conditions += rng.sample(more, min(len(more), want - len(conditions)))
    low, high = tricky["distractor_medications"]["min"], tricky["distractor_medications"]["max"]
    meds_pool = allowed(sec["medications"])
    medications = rng.sample(meds_pool, min(len(meds_pool), rng.randint(low, high)))
    past = None
    if rng.random() < tricky["past_vs_current"]:
        options = allowed(sec["past_vs_current"])
        if options:
            low_year, high_year = (int(x) for x in sec["past_years"].split("-"))
            past = {"item": rng.choice(options), "year": str(rng.randint(low_year, high_year))}
    return {
        "conditions": [{"code": c["code"], "text": list(c["text"])} for c in conditions],
        "medications": [list(m["text"]) for m in medications],
        "allergies": list(rng.choice(allowed(sec["allergies"]))["text"]),
        "social": _social(rng, allowed(sec["social"])),
        "past": (
            {"text": list(past["item"]["text"]), "year": past["year"]} if past is not None else None
        ),
        "ros": [list(r["text"]) for r in allowed(sec["ros"])],
    }


def _social(rng: random.Random, items: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    """One item of two or three kinds (habits, occupation, living), never two of a kind."""
    kinds = sorted({i["kind"] for i in items})
    chosen = rng.sample(kinds, min(len(kinds), rng.choice((2, 3))))
    return [list(rng.choice([i for i in items if i["kind"] == k])["text"]) for k in chosen]


def style_card(rng: random.Random, wording: str, writer: str) -> dict[str, Any]:
    cards = config()["style_cards"]
    length = config()["note"]["length_words"]
    habits = dict(cards["author_habits"])
    if wording == "B":
        habit = rng.choice(["terse_abbreviated", "terse_abbreviated", "templated_ehr"])
    else:
        habit = _choose(rng, {k: v for k, v in habits.items() if k != "terse_abbreviated"})
    bucket = _choose(rng, cards["length_buckets"])
    if rng.random() < length["long_tail_share"]:
        bucket = "long"
    ranges = {
        "short": (length["min"], 300),
        "medium": (300, length["long_tail_min"]),
        "long": (length["long_tail_min"], length["max"]),
    }
    low, high = ranges[bucket]
    if bucket == "medium":  # peaked at the configured median
        target = round(rng.triangular(low, high, length["target_median"]))
    else:
        target = rng.randint(low, high)
    card = {
        "habit": habit,
        "wording": wording,
        "length_bucket": bucket,
        "target_words": target,
        "copy_forward": rng.random() < config()["tricky"]["copy_forward"],
    }
    if writer == "C":
        card["format"] = rng.choice(cards["writer_c_formats"])
    return card


def fact_sheet(
    scenario: Scenario,
    draft: Draft,
    lookups: Any,  # noqa: ANN401
    *,
    sheet_id: str,
    split: str,
    writer: str,
    seed: str,
    unseen_policy: bool,
) -> dict[str, Any]:
    """The sheet for one built scenario (the builder's draft holds its facts)."""
    rng = random.Random(seed)
    visit = encounter_date(scenario)
    facts = list(draft.facts)
    fill_dates(facts, visit)
    clinic = scenario.provider["provider_type"]
    sec = phrases("sections")
    clinic_spec = sec["clinics"].get(clinic) or sec["clinics"]["PRIMARY_CARE"]
    claim = scenario.claim
    sex = SEX_WORDS.get(claim.patient.sex.value, SEX_DEFAULT)
    lines = []
    outcomes = {o.line_no: o for o in scenario.rules.line_outcomes}
    labels = {label["line_no"]: label for label in scenario.line_labels}
    for line in claim.service_lines:
        outcome = outcomes[line.line_no]
        lines.append(
            {
                "line_no": line.line_no,
                "date": line.date_of_service.isoformat(),
                "procedure_code": line.procedure_code,
                "description": lookups.procedure_descriptions.get(line.procedure_code, ""),
                "units": line.units,
                "modifiers": list(line.modifiers),
                "diagnoses": [
                    {
                        "code": claim.diagnoses["ABCDEFGHIJKL".index(p)],
                        "description": lookups.icd10_descriptions.get(
                            claim.diagnoses["ABCDEFGHIJKL".index(p)], ""
                        ),
                    }
                    for p in line.diagnosis_pointers
                ],
                "rule_outcome": outcome.outcome,
                "rule_reasons": list(outcome.reason_codes),
                "flags": list(outcome.flags),
                "label": labels[line.line_no],
            }
        )
    wording = draft.wording
    return {
        "sheet_id": sheet_id,
        "claim_id": claim.claim_id,
        "split": split,
        "writer": writer,
        "seed": seed,
        "generator_version": config()["version"],
        "scenario_type": scenario.scenario_type,
        "policy_ids": scenario.policy_ids,
        "profiles": scenario.profile_keys,
        "unseen_policy": unseen_policy,
        "patient": {
            "age": age_on(claim.patient.date_of_birth, visit),
            "sex": claim.patient.sex.value,
            "sex_words": list(sex),
        },
        "visit_date": visit.isoformat(),
        "received_date": claim.received_date.isoformat(),
        "clinic": {
            "provider_type": clinic,
            "name": rng.choice(clinic_spec["names"]),
            "visit": rng.choice(clinic_spec["visits"]),
        },
        "lead": dict(draft.lead),
        "procedures": list(dict.fromkeys(draft.procedures)),
        "office_visits": [
            {"line_no": line["line_no"], "date": line["date"]}
            for line in lines
            if line["procedure_code"].startswith("992")
        ],
        "diagnoses": [
            {"code": code, "description": lookups.icd10_descriptions.get(code, "")}
            for code in claim.diagnoses
        ],
        "lines": lines,
        "facts": [fact_to_json(f) for f in facts],
        "timeline": timeline(facts, visit, rng),
        "distractors": distractors(rng, clinic, draft.extra_diagnoses, claim.diagnoses),
        "style": style_card(rng, wording, writer),
        "tricky": sorted(draft.tricky),
        "label": {
            "line_labels": scenario.line_labels,
            "claim_decision": claim_decision(scenario.line_labels),
            "complexity": scenario.target.complexity.value if scenario.target else None,
            "target": scenario.target.model_dump(mode="json") if scenario.target else None,
        },
        "inputs": {
            "claim": claim.model_dump(mode="json"),
            "rules_outcome": scenario.rules.model_dump(mode="json"),
            "context": scenario.context.model_dump(mode="json"),
            "authorizations": [
                {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in a.items()}
                for a in scenario.authorizations
            ],
        },
    }
