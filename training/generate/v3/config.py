"""Generator v3 configuration: config.yaml and the phrase banks (SPEC.md).

Every value the generator uses is read from these files; code never repeats a number the spec
names. Wording keys in the phrase banks are A (plain) or B (shorthand); a key that starts with A
or B (A2, B2, ...) adds sentences to that wording.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from training.generate.common import GENERATED_DIR

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.yaml"
PHRASES_DIR = HERE / "phrases"
OUT_DIR = GENERATED_DIR / "v3"
WORDINGS = ("A", "B")


@lru_cache
def config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@lru_cache
def phrases(name: str) -> dict[str, Any]:
    return yaml.safe_load((PHRASES_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def wordings(value: Any) -> dict[str, tuple[str, ...]]:  # noqa: ANN401
    """{A: (...), B: (...)} from a phrase entry: a mapping of wording keys (A, A2, B, ...) to a
    sentence or a list of sentences."""
    found: dict[str, list[str]] = {}
    for key, sentences in (value or {}).items():
        wording = str(key)[0]
        if wording not in WORDINGS:
            raise ValueError(f"unknown wording key {key!r}")
        items = sentences if isinstance(sentences, list) else [sentences]
        found.setdefault(wording, []).extend(str(s) for s in items)
    return {k: tuple(v) for k, v in found.items()}


@dataclass(frozen=True)
class CriterionPhrases:
    criterion_id: str
    placement: Mapping[str, str]
    met: Mapping[str, tuple[str, ...]]
    not_met: Mapping[str, tuple[str, ...]]
    situation: Mapping[str, tuple[str, ...]]
    uncertain: Mapping[str, tuple[str, ...]]
    negated: Mapping[str, tuple[str, ...]]
    replace: frozenset[str] = frozenset()  # states whose v2 sentences are not used


@dataclass(frozen=True)
class BorderlineForm:
    sentences: Mapping[str, str]  # wording -> sentence
    date_slot: str | None
    derive: Mapping[str, str]  # check slot -> expression over the case's slots
    above: tuple[Mapping[str, Any], ...]
    below: tuple[Mapping[str, Any], ...]
    below_suffix: Mapping[str, str]


@dataclass(frozen=True)
class Borderline:
    criterion_id: str
    source: str
    rule: str  # all | any
    checks: tuple[Mapping[str, Any], ...]
    with_not_met: tuple[str, ...]
    forms: tuple[BorderlineForm, ...]


@lru_cache
def criteria_phrases() -> dict[str, CriterionPhrases]:
    found = {}
    for policy_id, criteria in phrases("criteria")["policies"].items():
        for short, spec in criteria.items():
            criterion_id = f"{policy_id}.{short}"
            found[criterion_id] = CriterionPhrases(
                criterion_id=criterion_id,
                placement=spec.get("placement") or {"section": "hpi"},
                met=wordings(spec.get("met")),
                not_met=wordings(spec.get("not_met")),
                situation=wordings(spec.get("situation")),
                uncertain=wordings(spec.get("uncertain")),
                negated=wordings(spec.get("negated")),
                replace=frozenset(spec.get("replace") or ()),
            )
    return found


@lru_cache
def borderlines() -> dict[str, Borderline]:
    found = {}
    for criterion_id, spec in phrases("criteria")["borderline"].items():
        forms = tuple(
            BorderlineForm(
                sentences={k: v for k, v in form.items() if k in WORDINGS},
                date_slot=form.get("date_slot"),
                derive=form.get("derive") or {},
                above=tuple(form.get("above") or ()),
                below=tuple(form.get("below") or ()),
                below_suffix=form.get("below_suffix") or {},
            )
            for form in spec["forms"]
        )
        found[criterion_id] = Borderline(
            criterion_id=criterion_id,
            source=spec["source"],
            rule=spec["rule"],
            checks=tuple(spec["checks"]),
            with_not_met=tuple(spec.get("with_not_met") or ()),
            forms=forms,
        )
    return found


OPS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
}


def derived_values(form: BorderlineForm, case: Mapping[str, Any]) -> dict[str, float]:
    """The check slots of a case: its own slots, plus those `derive` computes from them
    (`weeks*7`, or a date slot's days before the visit, `<slot>_days`)."""
    values: dict[str, float] = {k: float(v) for k, v in case.items() if _number(v)}
    for slot, expression in form.derive.items():
        found = re.fullmatch(r"(\w+)\*(\d+)", expression)
        if found:
            values[slot] = float(case[found.group(1)]) * int(found.group(2))
        else:
            values[slot] = float(case[expression])
    return values


def borderline_met(borderline: Borderline, form: BorderlineForm, case: Mapping[str, Any]) -> bool:
    """The status a case gives, from the policy threshold: True for MET."""
    values = derived_values(form, case)
    results = [OPS[c["op"]](values[c["slot"]], float(c["value"])) for c in borderline.checks]
    return all(results) if borderline.rule == "all" else any(results)


def _number(value: Any) -> bool:  # noqa: ANN401
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def leakage_patterns() -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in config()["leakage"]["patterns"]]


def leaks(text: str) -> list[str]:
    """Every outcome word or ID the leakage scan finds in `text`."""
    found = []
    for pattern in leakage_patterns():
        found += [m.group(0) for m in pattern.finditer(text)]
    return found
