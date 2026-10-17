"""Fact sheets (generator v3, Phase 2; SPEC.md).

A v3 claim starts as v2's does (`ScenarioBuilderV2`): lines planned with a state per criterion,
members, providers and plans generated from the seed files, the real rules engine, the context and
the target with the decision derived by the pipeline's own code (D-DEC-1, D-POL-3). What changes is
the note: instead of writing sentences, the builder records a fact per criterion,
with

- its fact status: documented, missing, contradicted, borderline_above, borderline_below or absent;
- the label status that gives (MET, NOT_MET, NOT_DOCUMENTED, NOT_APPLICABLE): v2's (role, state)
  table, a borderline case's threshold check, or a contradiction's correction;
- the sentence to state (both wordings), the values it must carry and where it goes.

The target's evidence is a placeholder per fact (`⟦F3⟧`) until a writer has produced the note
and the verification gate has found the exact quote (Phase 4). A borderline case below the
threshold sets the criteria its config lists (`with_not_met`) to not met as well, before the
target is built, so the label still comes from v2's derivation.

Extra claim-form realism (SPEC.md "Claim form"): office-visit lines on earlier dates up to the drawn
line count, and distractor diagnoses after the claim's own (some pointed to); the rules engine runs
on the final claim, and a claim whose expected rule outcome changes is drawn again (ScenarioError).
"""

import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

from app.domain.contracts import CriterionStatus
from training.generate.notes import draw_slots, fill
from training.generate.scenarios import OFFICE_CODES, ScenarioError
from training.generate.scenarios_v2 import (
    COLON_SEGMENTS,
    STATUS,
    LineV2,
    ProfileV2,
    ScenarioBuilderV2,
    _sets,
)
from training.generate.v3.config import (
    WORDINGS,
    Borderline,
    BorderlineForm,
    borderline_met,
    borderlines,
    config,
    criteria_phrases,
    phrases,
)

PLACEHOLDER = "⟦{}⟧"  # ⟦F3⟧: a fact's evidence until the note is written
PLACEHOLDER_NOTE = "⟦note⟧"
NUMBER = re.compile(r"\d+(?:[./]\d+)*")
DATE_FORMAT = "%m/%d/%Y"


@dataclass
class Fact:
    fact_id: str
    kind: str  # criterion | situation | bypass | condition | negated
    status: (
        str  # documented | missing | contradicted | borderline_above | borderline_below | absent
    )
    label_status: str | None  # MET | NOT_MET | NOT_DOCUMENTED | NOT_APPLICABLE (criteria only)
    criterion_id: str | None = None
    role: str | None = None  # requirement | exclusion | conditional | group
    profile: str | None = None
    lines: list[int] = field(default_factory=list)
    text: dict[str, str] = field(default_factory=dict)  # wording -> the sentence to state
    values: list[str] = field(default_factory=list)  # strings the stated sentence must contain
    placement: dict[str, str] = field(default_factory=dict)
    original: dict[str, str] = field(default_factory=dict)  # contradicted: the copied statement
    marker: str | None = None  # contradicted: the correction marker
    hedge: dict[str, str] = field(default_factory=dict)  # missing: an uncertain mention
    negated: dict[str, str] = field(default_factory=dict)  # absent exclusion: negative statement
    missing_text: str | None = None  # what is missing (writer B: do not mention; verifier)
    forbidden: list[str] = field(default_factory=list)  # sentences a missing fact must not match
    shares_evidence_with: str | None = None
    borderline: dict[str, Any] | None = None
    date_slots: dict[str, int] = field(default_factory=dict)  # slot -> days before the visit
    template: dict[str, str] = field(default_factory=dict)  # unfilled sentences (date slots)
    slots: dict[str, str] = field(default_factory=dict)

    @property
    def stated(self) -> bool:
        """Must the note state this fact (a sentence the gate looks for)?"""
        return bool(self.text) and self.status != "missing"


@dataclass
class Draft:
    """What the builder records while v2 builds the claim: the facts and the choices around them."""

    facts: list[Fact] = field(default_factory=list)
    lead: dict[str, str] = field(default_factory=dict)
    procedures: list[str] = field(default_factory=list)
    office_visits: int = 0
    extra_diagnoses: list[str] = field(default_factory=list)
    wording: str = "A"
    tricky: set[str] = field(default_factory=set)


class ScenarioBuilderV3(ScenarioBuilderV2):
    """v2's builder with fact sheets in place of notes (see the module docstring)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(*args, **kwargs)
        self.cfg = config()
        self.cp = criteria_phrases()
        self.bl = borderlines()
        self.sections = phrases("sections")
        self.draft = Draft()
        self.member: dict[str, Any] = {}
        self.provider: dict[str, Any] = {}

    # --- what v2 picks, kept for the fact sheet ------------------------------------------------

    def _pick_member(self, plans: set[str], min_age: int, first_day: date) -> dict[str, Any]:
        self.member = super()._pick_member(plans, min_age, first_day)
        return self.member

    def _pick_provider(self, types: set[str], plan_id: str, in_network: bool) -> dict[str, Any]:
        found = super()._pick_provider(types, plan_id, in_network)
        if not self.provider:  # the billing provider is picked first; a referring one later
            self.provider = found
        return found

    # --- claim form ----------------------------------------------------------------------------

    def _plan(self, scenario_type: str):  # type: ignore[no-untyped-def]  # noqa: ANN202
        self.provider = {}
        lines, types, plans = super()._plan(scenario_type)
        form = self.cfg["claim_form"]
        weights = form["lines_per_claim"]
        target = self.rng.choices([int(k) for k in weights], weights=list(weights.values()))[0]
        extra = min(max(0, target - len(lines)), form["max_lines"] - len(lines))
        office_types = set(self.cur.scope[OFFICE_CODES[0]].provider_types)
        line_types = (
            set(types)
            if types
            else set.intersection(
                *(set(self.cur.scope[line.code].provider_types) for line in lines)
            )
        )
        if extra and office_types & line_types:
            shift = max(form["extra_visit_days"][:extra])
            for line in lines:  # the visits come first, so every date stays in the window
                line.day_offset += shift
            for days in sorted(form["extra_visit_days"][:extra], reverse=True):
                lines.insert(
                    0,
                    LineV2(
                        code=self.rng.choice(OFFICE_CODES), profile=None, day_offset=shift - days
                    ),
                )
        return lines, types, plans

    def _diagnoses_v2(self, planned: list[LineV2]) -> tuple[list[str], list[list[str]]]:
        diagnoses, pointers = super()._diagnoses_v2(planned)
        form = self.cfg["claim_form"]
        weights = form["extra_diagnoses"]
        count = self.rng.choices([int(k) for k in weights], weights=list(weights.values()))[0]
        allowed = [
            c["code"]
            for c in self.sections["conditions"]
            if c["code"] not in diagnoses and not set(c["topics"]) & self._excluded_topics()
        ]
        extra = self.rng.sample(
            allowed, min(count, len(allowed), form["max_diagnoses"] - len(diagnoses))
        )
        for code in extra:
            diagnoses.append(code)
            letter = "ABCDEFGHIJKL"[diagnoses.index(code)]
            if self.rng.random() < form["extra_pointer_share"]:
                options = [
                    i
                    for i, line in enumerate(planned)
                    if line.profile is not None and len(pointers[i]) < form["max_pointers_per_line"]
                ]
                if options:
                    pointers[self.rng.choice(options)].append(letter)
        self.draft.extra_diagnoses = extra
        self._dx_by_line = {
            i: [diagnoses["ABCDEFGHIJKL".index(p)] for p in letters]
            for i, letters in enumerate(pointers)
        }
        return diagnoses, pointers

    def _align_side(self, key: str, slots: dict[str, str], planned: list[LineV2]) -> None:
        """A side slot (right/left, R/L) takes the side the line's diagnosis names, so the note
        and the claim agree (v2 drew it at random)."""
        options = next(
            (
                p.slots.get("side")
                for line in planned
                if line.profile and (p := line.profile).key == key
            ),
            None,
        )
        if "side" not in slots or not isinstance(options, list):
            return
        sides = set()
        for i, line in enumerate(planned):
            if line.profile and line.profile.key == key:
                for code in getattr(self, "_dx_by_line", {}).get(i, []):
                    text = self.cb.icd10.get(code, "").lower()
                    sides |= {s for s in ("right", "left") if f"{s} " in text or text.endswith(s)}
        if len(sides) == 1:
            side = sides.pop()
            letter = {"right": "R", "left": "L"}[side]
            slots["side"] = (
                side if side in options else (letter if letter in options else slots["side"])
            )

    def _excluded_topics(self) -> set[str]:
        clinic = self.sections["clinics"].get(self.provider.get("provider_type", ""), {})
        return set(clinic.get("exclude", ()))

    # --- facts in place of notes -----------------------------------------------------------------

    def _wording(self, options: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
        prefer = self.draft.wording
        if prefer in options:
            return options[prefer]
        return next(iter(options.values()))

    def _pool(self, criterion_id: str, state: str) -> dict[str, tuple[str, ...]]:
        """v2's sentences for a state plus v3's extra wordings."""
        v3_phrases = self.cp.get(criterion_id)
        v2 = getattr(self.t2.criteria[criterion_id], state)
        if v3_phrases and state in v3_phrases.replace:
            v2 = {}
        v3 = getattr(v3_phrases, state) if v3_phrases else {}
        return {
            w: tuple(v2.get(w, ())) + tuple(v3.get(w, ()))
            for w in WORDINGS
            if v2.get(w) or v3.get(w)
        }

    def _both(
        self, options: Mapping[str, tuple[str, ...]], slots: Mapping[str, str]
    ) -> dict[str, str]:
        """One sentence per wording (the same choice index where both wordings have it)."""
        found = {}
        for wording, sentences in options.items():
            found[wording] = fill(self.rng.choice(sentences), dict(slots))
        return found

    def _notes_v2(self, planned: list[LineV2]) -> tuple[str, dict[tuple[str, str], str]]:
        rng, t = self.rng, self.t2
        self.draft = Draft(
            wording=self.template_set if self.template_set in WORDINGS else "A",
            extra_diagnoses=self.draft.extra_diagnoses,
        )
        self._borderline_choice: dict[str, bool] = {}
        draft = self.draft
        evidence: dict[tuple[str, str], str] = {}
        states_by_profile: dict[str, dict[str, str]] = {}
        lines_by_profile: dict[str, list[int]] = {}
        profiles: dict[str, ProfileV2] = {}
        for n, line in enumerate(planned, start=1):
            if line.profile:
                states_by_profile.setdefault(line.profile.key, {}).update(line.states)
                lines_by_profile.setdefault(line.profile.key, []).append(n)
                profiles[line.profile.key] = line.profile
        conditions_done: set[str] = set()
        for n, line in enumerate(planned, start=1):
            if line.unrelated and line.unrelated[0] not in conditions_done:
                conditions_done.add(line.unrelated[0])
                texts = {w: s for w, s in line.unrelated[1].items() if w in WORDINGS}
                draft.facts.append(
                    Fact(
                        fact_id=self._next_id(),
                        kind="condition",
                        status="documented",
                        label_status=None,
                        lines=[n],
                        text=texts,
                        values=_numbers(texts.get("A", "")),
                        placement={"section": "hpi"},
                    )
                )
            if line.profile is None:
                draft.office_visits += 1
        for key, profile in profiles.items():
            slots = draw_slots(rng, profile.slots)
            self._align_side(key, slots, planned)
            line = next(x for x in planned if x.profile and x.profile.key == key)
            slots["units"] = str(line.units)
            if not draft.lead:
                draft.lead = self._both(profile.lead, slots)
            states = states_by_profile[key]
            self._apply_borderline_relations(planned, key, states)
            for criterion_id, state in states.items():
                for fact in self._criterion_facts(
                    criterion_id, state, slots, key, lines_by_profile[key]
                ):
                    fact.fact_id = self._next_id()
                    draft.facts.append(fact)
                    if fact.kind == "criterion" and fact.label_status in ("MET", "NOT_MET"):
                        if fact.text or fact.template:
                            evidence[(key, criterion_id)] = PLACEHOLDER.format(fact.fact_id)
            for criterion_id, state in states.items():  # criteria failing together share it
                if state == "not_met" and (key, criterion_id) not in evidence:
                    trigger = next(
                        (
                            c
                            for c in states
                            if (
                                criterion_id in t.criteria[c].with_not_met
                                or criterion_id in self._borderline_partners(c)
                            )
                            and states[c] == "not_met"
                            and (key, c) in evidence
                        ),
                        None,
                    )
                    if trigger is None:
                        raise ScenarioError(f"{criterion_id}: not met with no sentence")
                    evidence[(key, criterion_id)] = evidence[(key, trigger)]
                    shared = next(
                        f
                        for f in draft.facts
                        if f.criterion_id == criterion_id and f.profile == key
                    )
                    shared.shares_evidence_with = evidence[(key, trigger)].strip("⟦⟧")
        for n, line in enumerate(planned, start=1):
            if line.bypass is None:
                continue
            key, state = line.bypass
            slots = {}
            if line.profile:
                slots = draw_slots(rng, line.profile.slots)
            slots.setdefault("site2", "left lower leg")
            slots["problem"] = rng.choice(t.problems)
            segments = rng.sample(COLON_SEGMENTS, 2)
            slots.update(
                {"size": str(rng.randint(6, 15)), "seg1": segments[0], "seg2": segments[1]}
            )
            spec = t.distinct[key] if key in t.distinct else t.bypass[key]
            if state == "met":
                texts = self._both(_sets(spec["met"]), slots)
                draft.facts.append(
                    Fact(
                        fact_id=self._next_id(),
                        kind="bypass",
                        status="documented",
                        label_status=None,
                        lines=[n],
                        text=texts,
                        values=_numbers(texts.get("A", next(iter(texts.values())))),
                        placement={"section": "plan" if key in t.distinct else "assessment"},
                    )
                )
            else:
                draft.facts.append(
                    Fact(
                        fact_id=self._next_id(),
                        kind="bypass",
                        status="missing",
                        label_status=None,
                        lines=[n],
                        missing_text=spec["missing"],
                        forbidden=list(_sets(spec["met"]).get("A", ())),
                    )
                )
        draft.procedures = [
            self.cur.descriptions[line.code]
            for line in planned
            if line.profile and not line.expect_reasons
        ]
        return PLACEHOLDER_NOTE, evidence

    def _next_id(self) -> str:
        return f"F{len(self.draft.facts) + 1}"

    def _borderline_partners(self, criterion_id: str) -> tuple[str, ...]:
        found = self.bl.get(criterion_id)
        return found.with_not_met if found else ()

    def _apply_borderline_relations(
        self, planned: list[LineV2], key: str, states: dict[str, str]
    ) -> None:
        """Decide now which criteria are stated as borderline-below cases, and set the criteria
        their config lists to not met too (before v2 builds the target from the states)."""
        for criterion_id, state in list(states.items()):
            borderline = self.bl.get(criterion_id)
            if borderline is None or state not in ("met", "not_met"):
                continue
            chosen = self.rng.random() < self.cfg["tricky"]["borderline"]
            self._borderline_choice[f"{key}|{criterion_id}"] = chosen
            if chosen and state == "not_met":
                for partner in borderline.with_not_met:
                    if partner in states:
                        states[partner] = "not_met"
                        for line in planned:
                            if line.profile and line.profile.key == key and partner in line.states:
                                line.states[partner] = "not_met"

    def _criterion_facts(
        self,
        criterion_id: str,
        state: str,
        slots: Mapping[str, str],
        key: str,
        line_numbers: list[int],
    ) -> list[Fact]:
        """The facts for one criterion of a profile (IDs are given by the caller): the criterion's
        own fact, after the situation sentence of a conditional that is in its situation but
        missing what it needs."""
        rng, tricky = self.rng, self.cfg["tricky"]
        role = self.kinds[criterion_id].role
        label = STATUS[(role, state)].value
        phrases_v3 = self.cp.get(criterion_id)
        placement = dict(phrases_v3.placement) if phrases_v3 else {"section": "hpi"}
        base = dict(
            fact_id="",
            kind="criterion",
            criterion_id=criterion_id,
            role=role,
            profile=key,
            lines=list(line_numbers),
            placement=placement,
            slots=dict(slots),
        )
        if state == "absent":
            negated = phrases_v3.negated if phrases_v3 else {}
            fact = Fact(status="absent", label_status=label, **base)
            if role == "exclusion" and negated and rng.random() < tricky["negated_exclusion"]:
                fact.negated = self._both(negated, slots)
                self.draft.tricky.add("negation")
            if role == "exclusion":
                fact.forbidden = list(self._pool(criterion_id, "not_met").get("A", ()))
            return [fact]
        if state == "missing":
            found: list[Fact] = []
            situation = self._pool(criterion_id, "situation")
            if situation:  # a conditional in its situation without what it needs
                texts = self._both(situation, slots)
                found.append(
                    Fact(
                        fact_id="",
                        kind="situation",
                        status="documented",
                        label_status=None,
                        criterion_id=criterion_id,
                        profile=key,
                        lines=list(line_numbers),
                        text=texts,
                        values=_numbers(texts.get("A", next(iter(texts.values())))),
                        placement=placement,
                    )
                )
            fact = Fact(status="missing", label_status=label, **base)
            fact.missing_text = self.t2.criteria[criterion_id].missing
            fact.forbidden = list(self._pool(criterion_id, "met").get("A", ())) + list(
                self._pool(criterion_id, "not_met").get("A", ())
            )
            uncertain = phrases_v3.uncertain if phrases_v3 else {}
            if uncertain and rng.random() < tricky["uncertain_for_missing"]:
                fact.hedge = self._both(uncertain, slots)
                self.draft.tricky.add("uncertainty")
            return [*found, fact]
        pool = self._pool(criterion_id, state)
        if not pool:
            # not met with no sentence of its own: its evidence is a partner's (with_not_met)
            return [Fact(status="documented", label_status=label, **base)]
        borderline = self.bl.get(criterion_id)
        if borderline and self._borderline_choice.get(f"{key}|{criterion_id}"):
            return [self._borderline_fact(borderline, state, slots, base, label)]
        opposite = self._pool(criterion_id, "not_met" if state == "met" else "met")
        if role != "exclusion" and opposite and rng.random() < tricky["contradicted"]:
            fact = Fact(status="contradicted", label_status=label, **base)
            fact.text = self._both(pool, slots)
            fact.original = self._both(opposite, slots)
            fact.marker = rng.choice(tricky["correction_markers"])
            fact.values = _numbers(fact.text.get("A", next(iter(fact.text.values()))))
            self.draft.tricky.add("contradiction")
            return [fact]
        fact = Fact(status="documented", label_status=label, **base)
        fact.text = self._both(pool, slots)
        fact.values = _numbers(fact.text.get("A", next(iter(fact.text.values()))))
        return [fact]

    def _borderline_fact(
        self,
        borderline: Borderline,
        state: str,
        slots: Mapping[str, str],
        base: dict[str, Any],
        label: str,
    ) -> Fact:
        rng = self.rng
        side = "above" if state == "met" else "below"
        forms = [f for f in borderline.forms if getattr(f, side)]
        form: BorderlineForm = rng.choice(forms)
        case = dict(rng.choice(getattr(form, side)))
        met = borderline_met(borderline, form, case)
        if met != (state == "met"):  # the config would contradict the state: never written
            raise AssertionError(f"{borderline.criterion_id}: case {case} gives MET={met}")
        filled = {k: str(v) for k, v in {**slots, **case}.items()}
        date_slots = {}
        if form.date_slot:
            date_slots[form.date_slot] = int(case[f"{form.date_slot}_days"])
        templates = {}
        for wording, sentence in form.sentences.items():
            text = sentence + (form.below_suffix.get(wording, "") if side == "below" else "")
            templates[wording] = text
        fact = Fact(status=f"borderline_{side}", label_status=label, **base)
        fact.template = templates
        fact.slots = filled
        fact.date_slots = date_slots
        fact.borderline = {
            "criterion_id": borderline.criterion_id,
            "source": borderline.source,
            "rule": borderline.rule,
            "checks": [dict(c) for c in borderline.checks],
            "case": case,
            "met": met,
        }
        if not date_slots:
            fact.text = {w: fill(s, filled) for w, s in templates.items()}
            fact.values = [str(case[k]) for k in case if not k.endswith("_days")]
        self.draft.tricky.add("borderline")
        return fact


def _numbers(text: str) -> list[str]:
    return list(dict.fromkeys(NUMBER.findall(text)))


def fill_dates(facts: Sequence[Fact], visit: date) -> None:
    """Facts whose sentence holds a date slot: render the date from the visit date."""
    for fact in facts:
        if not fact.date_slots:
            continue
        values = dict(fact.slots)
        rendered = []
        for slot, days in fact.date_slots.items():
            values[slot] = (visit - timedelta(days=days)).strftime(DATE_FORMAT)
            rendered.append(values[slot])
        fact.text = {w: fill(s, values) for w, s in fact.template.items()}
        fact.values = rendered


def label_statuses(facts: Sequence[Fact]) -> dict[str, str]:
    return {f.fact_id: f.label_status for f in facts if f.label_status}


def fact_to_json(fact: Fact) -> dict[str, Any]:
    data = asdict(fact)
    return {k: v for k, v in data.items() if v not in (None, [], {}, "")} | {
        "fact_id": fact.fact_id,
        "status": fact.status,
    }


def fact_from_json(data: Mapping[str, Any]) -> Fact:
    fields = Fact.__dataclass_fields__
    return Fact(**{k: v for k, v in data.items() if k in fields})


CRITERION_STATUSES = {s.value for s in CriterionStatus}


def new_rng(seed: int | str) -> random.Random:
    return random.Random(seed)
