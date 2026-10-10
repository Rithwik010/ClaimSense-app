"""Scenario engine v2 (generator v2): policy set v2, rules 2.1.0, prompt decision_v3.

Ground truth first, as in v1 (INSTRUCTIONS.md §9.4): a scenario fixes, for every criterion shown on
a line's code, its state (met, not met, missing, absent), whether a bypass modifier is documented,
and the rule outcome it expects; then the notes, the claim, the rules outcome, the context and the
target.
What changes from v1:

- Criteria: the exact v2 lookup (D-RAG-2) shows every criterion of the line's code, so every one
  gets a state, by its type (D-ESI-6, D-POL-3): a requirement is met unless the scenario says
  otherwise (D-GEN-1: an APPROVE note has MET evidence for each); an exclusion is never MET
  (D-GEN-3); a conditional is NOT_APPLICABLE unless the profile (or a rule flag) puts the patient in
  its situation; one indication-group member is the patient's indication.
- Labels: the statuses follow from the states, and the line decision is derived from the statuses
  by the pipeline's own code (`app.ml.derive`, D-DEC-1), keeping a PEND for undocumented bypasses.
- Rules: the real engine (`app.rules.engine.evaluate`, RULES_VERSION) runs on every claim with the
  generated reference data plus the claim's own authorizations, so every claim passes Groups A and
  B (D-GEN-5) and its Group C outcome is the engine's (parity by construction). Diagnosis
  mismatches are R15 rule denials, never criterion labels (D-DX-1, D-GEN-2).
- Notes: wording sets A and B laid out in note styles A (plain), B (shorthand) and C (sections)
  for training, and D (a numbered list mixing both wordings sentence by sentence) only in the test
  split.
- New situations: modifiers 25, 57, 59 and X, and anatomic sites (D-RULE-8); the flags
  NCS_WITHOUT_EMG, FACET_TWO_REGIONS and EXTENDED_TESTING (D-RULE-6); the mycotic-nail path of foot
  care; 93241 under POL-CAR-002.c5 (D-V2-4). Add-on level codes stay out of scope (rule-only).
"""

import dataclasses
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.calculator.money import apply_bps
from app.db.curated import CoveragePolicy, Criterion, load_curated, rule_codes
from app.db.rules_reference import build_reference, load_code_tables
from app.domain.contracts import (
    BenefitFact,
    ContextPackage,
    CostShareRule,
    CriterionResult,
    CriterionStatus,
    IntakeClaim,
    LineContext,
    LineDecision,
    Network,
    RuleOutcomeValue,
    RulesOutcome,
    SLMLine,
    SLMOutput,
)
from app.ml.derive import (
    DENY_CRITERION,
    DENY_EXCLUSION,
    NO_INDICATION,
    PEND_MISSING,
    derive_line,
    implied_decision,
)
from app.ml.prompt import NOT_APPLICABLE, NOT_DOCUMENTED
from app.rules.engine import evaluate
from app.rules.reference import AuthorizationRef, RulesReference
from training.generate.codebook import Codebook, load_codebook
from training.generate.common import DEFAULT_SEED, DOS_END, DOS_START
from training.generate.notes import LEAKAGE, draw_slots, fill
from training.generate.reference import ReferenceData, generate_reference
from training.generate.scenarios import (
    MIN_AGE,
    OFFICE_CODES,
    OON_PLANS,
    Scenario,
    ScenarioBuilder,
    ScenarioError,
)

GENERATOR_VERSION = "scenarios-v3"  # v3: policy set v2, rules 2.x engine, derived labels
POLICY_SET = "v2"
TEMPLATES_V1 = Path(__file__).parent / "templates" / "clinical_notes.yaml"
TEMPLATES_V2 = Path(__file__).parent / "templates" / "clinical_notes_v2.yaml"
# Policies never seen in training (D-POL-2's v2 data). POL-DX-002 is trained on in v2 because its
# nerve-conduction criterion and the NCS_WITHOUT_EMG flag must be learned (D-RULE-6); POL-IMG-001
# is held out in its place (D-GEN-6).
TEST_ONLY_POLICIES = frozenset({"POL-DX-001", "POL-IMG-001", "POL-IMG-002", "POL-SURG-003"})
TRAIN_STYLES = ("A", "B", "C")
TEST_ONLY_STYLE = "D"  # a numbered list mixing wordings A and B by sentence; test split only
WORDINGS = ("A", "B")
CONFIDENCE_MIN = 0.85
TWO_POLICY_PAIRS = (  # D-GEN-4: pairs whose notes are clinically consistent (no ESI + facet pair)
    ("POL-CAR-001", "POL-CAR-002", "CARDIOLOGY"),
    ("POL-WOUND-001", "POL-FOOT-001", "PODIATRY"),
    ("POL-SURG-001", "POL-SURG-004", "OPHTHALMOLOGY"),
    ("POL-IMG-001", "POL-IMG-002", "RADIOLOGY"),
)
DISTINCT_PAIRS = {  # 59 or X modifiers: (policy, column 1, column 2)
    "wound": ("POL-WOUND-001", "11042", "97597"),
    "colon": ("POL-SURG-002", "45385", "45380"),
}
DISTINCT_MODIFIERS = ("59", "XS", "XU")
SIDES = ("RT", "LT")
EXCLUDED_EXTRAS = (  # plan, excluded code, profile key (plan exclusions, R13)
    ("PLN-PPO-SILVER", "64635", "POL-PAIN-002/lumbar_facet"),
    ("PLN-EPO", "97140", "POL-REHAB-001/treatment"),
    ("PLN-HMO", "95044", "POL-DX-003/contact"),
)
COLON_SEGMENTS = ("sigmoid colon", "descending colon", "transverse colon", "ascending colon")
SCENARIO_TYPES = (
    "approve_single",
    "deny_criterion",
    "deny_exclusion",
    "pend_missing",
    "office_visit",
    "office_plus_procedure",
    "office_same_day",
    "same_profile_multi",
    "two_policy",
    "ncci_bypass",
    "rule_denied_line",
    "ncs_without_emg",
    "facet_two_regions",
    "extended_testing",
)
MODES = ("approve", "pend", "deny_criterion", "deny_exclusion")
MODE_WEIGHTS = (50, 22, 16, 12)


# --- Templates -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class CriterionNotes:
    criterion_id: str
    met: Mapping[str, tuple[str, ...]]
    not_met: Mapping[str, tuple[str, ...]]
    situation: Mapping[str, tuple[str, ...]]
    missing: str
    with_not_met: tuple[str, ...]
    diagnoses_when_not_met: tuple[str, ...]


@dataclass(frozen=True)
class ProfileV2:
    policy_id: str
    profile_id: str
    codes: tuple[str, ...]
    diagnoses: tuple[str, ...]
    diagnoses_all_of: tuple[tuple[str, ...], ...]
    units: Mapping[str, str]
    pos: tuple[str, ...]
    slots: Mapping[str, Any]
    lead: Mapping[str, tuple[str, ...]]
    indication: str | None  # full criterion ID
    conditionals: tuple[str, ...]  # full criterion IDs in their situation
    flag_conditionals: Mapping[str, str]  # full criterion ID -> rule flag that puts it there
    flag_states: Mapping[str, str]  # a flag conditional's usual state in this profile (default met)
    exclusions: tuple[str, ...]
    modifiers: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.policy_id}/{self.profile_id}"

    def diagnosis_sets(self) -> list[tuple[str, ...]]:
        if self.diagnoses_all_of:
            return [tuple(combo) for combo in _product(self.diagnoses_all_of)]
        return [(code,) for code in self.diagnoses]


def _product(groups: tuple[tuple[str, ...], ...]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for group in groups:
        out = [prefix + [code] for prefix in out for code in group]
    return out


@dataclass(frozen=True)
class TemplatesV2:
    criteria: Mapping[str, CriterionNotes]
    profiles: Mapping[str, tuple[ProfileV2, ...]]
    filler: Mapping[str, tuple[str, ...]]
    plan_line: Mapping[str, str]
    office_visit: Mapping[str, tuple[str, ...]]
    distinct: Mapping[str, Mapping[str, Any]]
    bypass: Mapping[str, Mapping[str, Any]]
    problems: tuple[str, ...]
    unrelated: tuple[tuple[str, Mapping[str, str]], ...]


def _sets(value: Any) -> dict[str, tuple[str, ...]]:
    return {k: tuple(v) if isinstance(v, list) else (v,) for k, v in (value or {}).items()}


@lru_cache
def load_templates_v2() -> TemplatesV2:
    v1 = yaml.safe_load(TEMPLATES_V1.read_text(encoding="utf-8"))
    v2 = yaml.safe_load(TEMPLATES_V2.read_text(encoding="utf-8"))
    criteria: dict[str, CriterionNotes] = {}
    profiles: dict[str, tuple[ProfileV2, ...]] = {}
    for policy_id, block in v2["policies"].items():

        def full(short: str, policy_id: str = policy_id) -> str:
            return f"{policy_id}.{short}"

        for short, spec in block["criteria"].items():
            criteria[full(short)] = CriterionNotes(
                criterion_id=full(short),
                met=_sets(spec.get("met")),
                not_met=_sets(spec.get("not_met")),
                situation=_sets(spec.get("situation")),
                missing=spec.get("missing", ""),
                with_not_met=tuple(full(c) for c in spec.get("with_not_met", [])),
                diagnoses_when_not_met=tuple(spec.get("diagnoses_when_not_met", [])),
            )
        profiles[policy_id] = tuple(
            ProfileV2(
                policy_id=policy_id,
                profile_id=p["id"],
                codes=tuple(p["codes"]),
                diagnoses=tuple(p.get("diagnoses", [])),
                diagnoses_all_of=tuple(tuple(g) for g in p.get("diagnoses_all_of", [])),
                units=p.get("units", {}),
                pos=tuple(p["pos"]),
                slots=p.get("slots") or {},
                lead=_sets(p["lead"]),
                indication=full(p["indication"]) if p.get("indication") else None,
                conditionals=tuple(full(c) for c in p.get("conditionals", [])),
                flag_conditionals={
                    full(c): flag for c, flag in (p.get("flag_conditionals") or {}).items()
                },
                flag_states={full(c): v for c, v in (p.get("flag_states") or {}).items()},
                exclusions=tuple(full(c) for c in p.get("exclusions", [])),
                modifiers=tuple(p.get("modifiers", [])),
            )
            for p in block["profiles"]
        )
    return TemplatesV2(
        criteria=criteria,
        profiles=profiles,
        filler=_sets(v1["filler"]),
        plan_line=v1["plan_line"],
        office_visit=_sets(v1["office_visit"]),
        distinct=v1["distinct_service"],
        bypass=v2["bypass_documentation"],
        problems=tuple(v2["problems"]),
        unrelated=tuple(
            (u["code"], {k: v for k, v in u.items() if k != "code"})
            for u in v1["unrelated_conditions"]
        ),
    )


def template_problems(curated_policies: Mapping[str, CoveragePolicy], icd10: set[str]) -> list[str]:
    """Every v2 criterion has the sentences its type needs; profiles name real codes."""
    t = load_templates_v2()
    problems = []
    for policy in curated_policies.values():
        if policy.policy_id not in t.profiles:
            problems.append(f"{policy.policy_id}: no profiles")
            continue
        for criterion in policy.criteria:
            notes = t.criteria.get(criterion.criterion_id)
            if notes is None:
                problems.append(f"{criterion.criterion_id}: no templates")
                continue
            if criterion.criterion_type == "exclusion" and not notes.not_met:
                problems.append(f"{criterion.criterion_id}: an exclusion needs not_met sentences")
            if criterion.criterion_type != "exclusion" and not notes.met:
                problems.append(f"{criterion.criterion_id}: needs met sentences")
            if criterion.criterion_type != "exclusion" and criterion.group is None:
                if not notes.missing:
                    problems.append(f"{criterion.criterion_id}: needs a missing text")
        for profile in t.profiles[policy.policy_id]:
            if not set(profile.codes) <= set(policy.procedure_codes):
                problems.append(f"{profile.key}: codes outside the policy")
            dx = set(profile.diagnoses) | {d for g in profile.diagnoses_all_of for d in g}
            if dx - icd10:
                problems.append(f"{profile.key}: unknown ICD-10-CM codes {sorted(dx - icd10)}")
    for notes in t.criteria.values():
        for sentences in (*notes.met.values(), *notes.not_met.values(), *notes.situation.values()):
            for sentence in sentences:
                if LEAKAGE.search(sentence):
                    problems.append(f"{notes.criterion_id}: leakage word in {sentence!r}")
    return problems


# --- Plans ---------------------------------------------------------------------------------------


@dataclass
class LineV2:
    code: str
    profile: ProfileV2 | None  # None for an office visit
    states: dict[str, str] = field(default_factory=dict)  # criterion ID -> state
    unrelated: tuple[str, Mapping[str, str]] | None = None  # visit condition or R15 mismatch
    bypass: tuple[str, str] | None = None  # (BYPASS_PHRASES key or distinct kind, met | missing)
    modifiers: tuple[str, ...] = ()
    units: int = 1
    day_offset: int = 0
    expect_reasons: tuple[str, ...] = ()  # the rule denial expected (empty: the line passes)
    expect_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Kind:
    """A criterion's role in v2: requirement, exclusion, conditional or group (an indication)."""

    criterion: Criterion
    policy: CoveragePolicy

    @property
    def role(self) -> str:
        if self.criterion.group:
            return "group"
        return self.criterion.criterion_type or "requirement"


STATUS = {
    ("requirement", "met"): CriterionStatus.MET,
    ("requirement", "not_met"): CriterionStatus.NOT_MET,
    ("requirement", "missing"): CriterionStatus.NOT_DOCUMENTED,
    ("exclusion", "absent"): CriterionStatus.NOT_APPLICABLE,
    ("exclusion", "not_met"): CriterionStatus.NOT_MET,
    ("conditional", "absent"): CriterionStatus.NOT_APPLICABLE,
    ("conditional", "met"): CriterionStatus.MET,
    ("conditional", "not_met"): CriterionStatus.NOT_MET,
    ("conditional", "missing"): CriterionStatus.NOT_DOCUMENTED,
    ("group", "absent"): CriterionStatus.NOT_APPLICABLE,
    ("group", "met"): CriterionStatus.MET,
    ("group", "not_met"): CriterionStatus.NOT_MET,
}


def reference_dicts(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Generated reference rows with dates as ISO strings (what build_reference reads)."""
    return [
        {k: v.isoformat() if isinstance(v, date) else v for k, v in row.items()} for row in rows
    ]


class ScenarioBuilderV2(ScenarioBuilder):
    """Builds v2 scenarios for one split. `policies` may appear as claim lines; `styles` are the
    note styles drawn from; `retriever` is the v2 exact lookup (its excluded policies are those not
    allowed in the split)."""

    def __init__(
        self,
        seed: int,
        styles: Sequence[str],
        policies: set[str],
        excluded_policies: set[str],
        retriever: Any,
        reference: ReferenceData | None = None,
        lookups: Any = None,
    ) -> None:
        self.rng = random.Random(seed)
        self.seed = seed
        self.styles = tuple(styles)
        self.template_set = self.styles[0]
        self.cb: Codebook = load_codebook()
        self.cur = load_curated(POLICY_SET)
        self.t2 = load_templates_v2()
        self.policies = {p for p in policies if p in self.t2.profiles}
        self.excluded_policies = frozenset(excluded_policies)
        self.retriever = retriever
        self.lookups = lookups
        self.reference = reference or generate_reference(DEFAULT_SEED)[0]
        self.members = [m for m in self.reference.members if self._active(m)]
        self.providers = {p["npi"]: p for p in self.reference.providers}
        self.network = {
            (n["npi"], n["plan_id"]): n["in_network"] for n in self.reference.provider_networks
        }
        self.visits = {
            (v["member_id"], v["benefit_category"]): v["visits_used"]
            for v in self.reference.visit_usage
        }
        self.auth_counter = 0
        self.rules_reference = rules_reference(self.reference)
        self.kinds = {
            c.criterion_id: Kind(c, p) for p in self.cur.policies.values() for c in p.criteria
        }
        self.em_pairs = self._em_pairs()

    # --- what the lookup shows -------------------------------------------------------------------

    def shown(self, code: str) -> list[str]:
        """The v2 criteria the exact lookup shows on `code` (plan ALL, effective 2026-01-01), in
        policy-file order; the dataset check compares them with the lookup on every line."""
        entry = self.cur.scope.get(code)
        if entry is None or entry.policy_id is None:
            return []
        policy = self.cur.policies[entry.policy_id]
        return [c.criterion_id for c in policy.criteria if code in policy.criterion_codes(c)]

    def _profiles(self, policies: set[str] | None = None) -> list[ProfileV2]:  # type: ignore[override]
        chosen = sorted(policies if policies is not None else self.policies)
        return [p for policy in chosen if policy in self.policies for p in self.t2.profiles[policy]]

    def _em_pairs(self) -> list[tuple[str, str, str]]:
        """(procedure, E&M, modifier) for same-day NCCI edits with indicator 1 the manual lets 25
        or 57 bypass (D-RULE-8), by the procedure's PFS global period."""
        days = self.rules_reference.global_days
        pairs = []
        for profile in self._profiles():
            for code in profile.codes:
                for office in OFFICE_CODES:
                    if self.cb.ncci_indicator(code, office, DOS_START) != "1":
                        continue
                    if days.get(code) in ("000", "010", "XXX"):
                        pairs.append((code, office, "25"))
                    elif days.get(code) == "090":
                        pairs.append((code, office, "57"))
        return sorted(set(pairs))

    # --- states ----------------------------------------------------------------------------------

    def _base_states(self, profile: ProfileV2, code: str, flags: Sequence[str]) -> dict[str, str]:
        situation = set(profile.conditionals) | {
            c for c, flag in profile.flag_conditionals.items() if flag in flags
        }
        states = {}
        for criterion_id in self.shown(code):
            role = self.kinds[criterion_id].role
            if role == "group":
                states[criterion_id] = "met" if criterion_id == profile.indication else "absent"
            elif role == "exclusion":
                states[criterion_id] = "absent"
            elif role == "conditional":
                states[criterion_id] = (
                    profile.flag_states.get(criterion_id, "met")
                    if criterion_id in situation
                    else "absent"
                )
            else:
                states[criterion_id] = "met"
        return states

    def _states(  # type: ignore[override]
        self, profile: ProfileV2, code: str, mode: str, flags: Sequence[str] = ()
    ) -> dict[str, str] | None:
        states = self._base_states(profile, code, flags)
        t = self.t2.criteria
        if mode == "approve":
            return states
        decided = [
            c
            for c, s in states.items()
            if s == "met" and self.kinds[c].role in ("requirement", "conditional")
        ]
        if mode == "pend":
            options = [c for c in decided if t[c].missing]
            group = profile.indication is not None and profile.indication in states
            if group and (not options or self.rng.random() < 0.4):
                member = profile.indication
                states[member] = (
                    "not_met" if t[member].not_met and self.rng.random() < 0.5 else "absent"
                )
                return states
            if not options:
                return None
            count = 2 if len(options) >= 2 and self.rng.random() < 0.2 else 1
            for c in self.rng.sample(options, count):
                states[c] = "missing"
            return states
        if mode == "deny_criterion":
            options = [c for c in decided if t[c].not_met]
            if not options:
                return None
            target = self.rng.choice(options)
            states[target] = "not_met"
            for other in t[target].with_not_met:
                if other in states and states[other] == "met":
                    states[other] = "not_met"
            return states
        if mode == "deny_exclusion":
            options = [c for c in profile.exclusions if c in states and t[c].not_met]
            if not options:
                return None
            target = self.rng.choice(options)
            states[target] = "not_met"
            for other in t[target].with_not_met:
                if other in states:
                    states[other] = "not_met"
            for c in states:  # the excluded situation is not also an indication
                if self.kinds[c].role == "group":
                    states[c] = "absent"
            return states
        raise ValueError(mode)

    def _line(
        self,
        profile: ProfileV2,
        mode: str,
        code: str | None = None,
        flags: Sequence[str] = (),
    ) -> LineV2:
        code = code or self.rng.choice(profile.codes)
        states = self._states(profile, code, mode, flags)
        if states is None:
            raise ScenarioError(f"{profile.key} {code} cannot produce {mode}")
        spec = profile.units.get(code)
        units = 1
        if spec:
            low, high = (int(x) for x in spec.split("-"))
            units = self.rng.randint(low, high)
        return LineV2(
            code=code,
            profile=profile,
            states=states,
            modifiers=profile.modifiers,
            units=units,
            expect_flags=tuple(flags),
        )

    def _profile_for(self, mode: str, policies: set[str] | None = None) -> ProfileV2:  # type: ignore[override]
        profiles = self._profiles(policies)
        self.rng.shuffle(profiles)
        for profile in profiles:
            for code in profile.codes:
                if self._states(profile, code, mode) is not None:
                    return profile
        raise ScenarioError(f"no profile supports {mode}")

    def _mode(self) -> str:
        return self.rng.choices(MODES, weights=MODE_WEIGHTS)[0]

    def _policy_line(self, profile: ProfileV2, mode: str, code: str | None = None) -> LineV2:  # type: ignore[override]
        for _ in range(8):
            try:
                return self._line(profile, mode, code)
            except ScenarioError:
                if code is not None:
                    break
        return self._line(profile, "approve", code)

    # --- planning --------------------------------------------------------------------------------

    def _plan(  # type: ignore[override]
        self, scenario_type: str
    ) -> tuple[list[LineV2], set[str] | None, set[str] | None]:
        rng = self.rng
        single = {
            "approve_single": "approve",
            "deny_criterion": "deny_criterion",
            "deny_exclusion": "deny_exclusion",
            "pend_missing": "pend",
        }
        if scenario_type in single:
            mode = single[scenario_type]
            profile = self._profile_for(mode)
            codes = [c for c in profile.codes if self._states(profile, c, mode) is not None]
            return [self._line(profile, mode, rng.choice(codes))], None, None
        if scenario_type == "office_visit":
            line = LineV2(code=rng.choice(OFFICE_CODES), profile=None)
            line.unrelated = rng.choice(self.t2.unrelated)
            types = (
                {"PRIMARY_CARE"}
                if rng.random() < 0.7
                else set(self.cur.scope["99213"].provider_types)
            )
            return [line], types, None
        if scenario_type == "office_plus_procedure":
            office_types = set(self.cur.scope["99213"].provider_types)
            profiles = [
                p
                for p in self._profiles()
                if office_types & set(self.cur.scope[p.codes[0]].provider_types)
            ]
            if not profiles:
                raise ScenarioError("no office/procedure provider")
            procedure = self._policy_line(rng.choice(profiles), self._mode())
            procedure.day_offset = rng.randint(7, 21)
            return [LineV2(code=rng.choice(OFFICE_CODES), profile=None), procedure], None, None
        if scenario_type == "office_same_day":
            return self._plan_office_same_day()
        if scenario_type == "same_profile_multi":
            profiles = [p for p in self._profiles() if len(p.codes) >= 2]
            if not profiles:
                raise ScenarioError("no profile with several codes")
            profile = rng.choice(profiles)
            mode = rng.choices(("approve", "pend", "deny_criterion"), weights=(60, 25, 15))[0]
            codes = rng.sample(profile.codes, min(len(profile.codes), rng.choice((2, 2, 3))))
            if any(self.cb.ncci_indicator(a, b, DOS_START) for a in codes for b in codes if a != b):
                raise ScenarioError(f"{profile.key}: codes {codes} form an NCCI pair")
            first = self._line(profile, mode, codes[0])
            lines = [first]
            for code in codes[1:]:  # D-GEN-4: one patient, one set of facts across the lines
                line = self._line(profile, "approve", code)
                line.states = {c: first.states.get(c, s) for c, s in line.states.items()}
                lines.append(line)
            return lines, None, None
        if scenario_type == "two_policy":
            pairs = [p for p in TWO_POLICY_PAIRS if p[0] in self.policies and p[1] in self.policies]
            if not pairs:
                raise ScenarioError("no policy pair")
            first_policy, second_policy, provider_type = rng.choice(pairs)
            lines = []
            for policy_id in (first_policy, second_policy):
                profiles = [
                    p
                    for p in self._profiles({policy_id})
                    if provider_type in self.cur.scope[p.codes[0]].provider_types
                ]
                if not profiles:
                    raise ScenarioError(f"no {provider_type} profile in {policy_id}")
                lines.append(self._policy_line(rng.choice(profiles), self._mode()))
            if lines[0].day_offset == lines[1].day_offset and self.cb.ncci_indicator(
                lines[0].code, lines[1].code, DOS_START
            ):
                lines[1].day_offset = rng.randint(7, 14)
            return lines, {provider_type}, None
        if scenario_type == "ncci_bypass":
            return self._plan_bypass()
        if scenario_type == "rule_denied_line":
            return self._plan_rule_denied()
        if scenario_type == "ncs_without_emg":
            if "POL-DX-002" not in self.policies:
                raise ScenarioError("NCS scenarios use POL-DX-002")
            profile = rng.choice(self.t2.profiles["POL-DX-002"])
            mode = rng.choices(MODES[:3], weights=(45, 30, 25))[0]
            code = rng.choice(("95907", "95910"))
            flags = ("NCS_WITHOUT_EMG",)
            line = self._line(profile, mode, code, flags)
            target = next(c for c in profile.flag_conditionals)
            usual = profile.flag_states.get(target, "met")
            if mode != "approve" and usual == "met" and rng.random() < 0.6:  # in play
                line.states[target] = "not_met" if mode == "deny_criterion" else "missing"
                for c, s in list(line.states.items()):
                    if c != target and s in ("not_met", "missing"):
                        line.states[c] = "met"
            return [line], None, None
        if scenario_type == "facet_two_regions":
            if "POL-PAIN-002" not in self.policies:
                raise ScenarioError("facet scenarios use POL-PAIN-002")
            profile = next(
                p for p in self.t2.profiles["POL-PAIN-002"] if p.profile_id == "two_regions"
            )
            mode = rng.choices(MODES[:3], weights=(55, 25, 20))[0]
            flags = ("FACET_TWO_REGIONS",)
            first = self._line(profile, mode, "64490", flags)
            second = self._line(profile, "approve", "64493", flags)
            second.states = {c: first.states.get(c, s) for c, s in second.states.items()}
            return [first, second], None, None
        if scenario_type == "extended_testing":
            if "POL-BH-001" not in self.policies:
                raise ScenarioError("extended testing uses POL-BH-001")
            profile = next(
                p for p in self.t2.profiles["POL-BH-001"] if p.profile_id == "new_evaluation"
            )
            mode = rng.choices(MODES, weights=(55, 20, 15, 10))[0]
            flags = ("EXTENDED_TESTING",)
            first = self._line(profile, mode, "96130", flags)
            lines = [first]
            for code, units in (("96131", 7), ("96136", 1)):
                line = self._line(profile, "approve", code, flags)
                line.states = {c: first.states.get(c, s) for c, s in line.states.items()}
                line.units = units
                lines.append(line)
            first.units = 1
            return lines, None, None
        raise ValueError(f"unknown scenario type {scenario_type}")

    def _plan_office_same_day(self) -> tuple[list[LineV2], set[str] | None, set[str] | None]:
        rng = self.rng
        pairs = [p for p in self.em_pairs if self._policy_of(p[0]) in self.policies]
        if not pairs:
            raise ScenarioError("no same-day E&M pair")
        code, office_code, modifier = rng.choice(pairs)
        profile = rng.choice([p for p in self._profiles() if code in p.codes])
        procedure = self._policy_line(profile, self._mode(), code)
        office = LineV2(code=office_code, profile=None)
        if rng.random() < 0.75:
            key = "SEPARATE_EM" if modifier == "25" else "SURGERY_DECISION"
            office.modifiers = (modifier,)
            office.bypass = (key, rng.choice(("met", "met", "missing")))
            office.expect_flags = ("NCCI_BYPASS",)
        else:
            office.expect_reasons = ("DN_NCCI_BUNDLED",)
        return [procedure, office], None, None

    def _plan_bypass(self) -> tuple[list[LineV2], set[str] | None, set[str] | None]:
        rng = self.rng
        options = [k for k, (policy, _, _) in DISTINCT_PAIRS.items() if policy in self.policies]
        if not options:
            raise ScenarioError("no bypass pair in these policies")
        kind = rng.choice(options)
        policy_id, column1, column2 = DISTINCT_PAIRS[kind]
        profiles = [p for p in self._profiles({policy_id}) if {column1, column2} <= set(p.codes)]
        profile = rng.choice(profiles)
        mode = "approve" if rng.random() < 0.8 else "pend"
        first = self._line(profile, mode, column1)
        second = self._line(profile, "approve", column2)
        second.states = {c: first.states.get(c, s) for c, s in second.states.items()}
        documented = rng.choice(("met", "missing"))
        if kind == "wound" and rng.random() < 0.4:  # different anatomic sites (D-RULE-8)
            sides = rng.sample(SIDES, 2)
            first.modifiers, second.modifiers = (sides[0],), (sides[1],)
            second.bypass = ("SITES", documented)
        else:
            second.modifiers = (rng.choice(DISTINCT_MODIFIERS),)
            second.bypass = (kind, documented)
        second.units = 1
        second.expect_flags = ("NCCI_BYPASS",)
        return [first, second], None, None

    def _plan_rule_denied(self) -> tuple[list[LineV2], set[str] | None, set[str] | None]:
        rng = self.rng
        kind = rng.choice(("ncci", "ncci", "excluded", "mue", "dx", "dx"))
        if kind == "excluded":
            options = [e for e in EXCLUDED_EXTRAS if e[2].split("/")[0] in self.policies]
            if options:
                plan_id, code, key = rng.choice(options)
                profile = next(p for p in self._profiles() if p.key == key)
                others = [c for c in profile.codes if c != code]
                model = (
                    self._policy_line(profile, self._mode(), rng.choice(others))
                    if others
                    else LineV2(code=rng.choice(OFFICE_CODES), profile=None, day_offset=7)
                )
                excluded = self._line(profile, "approve", code)
                if model.profile:
                    excluded.states = {
                        c: model.states.get(c, s) for c, s in excluded.states.items()
                    }
                excluded.expect_reasons = ("DN_EXCLUDED",)
                return [model, excluded], None, {plan_id}
            kind = "ncci"
        if kind == "mue" and "POL-REHAB-001" in self.policies:
            profile = next(
                p for p in self.t2.profiles["POL-REHAB-001"] if p.profile_id == "treatment"
            )
            model = self._policy_line(profile, self._mode(), "97530")
            over = self._line(profile, "approve", "97110")
            over.states = {c: model.states.get(c, s) for c, s in over.states.items()}
            over.units = rng.randint(7, 9)
            over.expect_reasons = ("DN_MUE_EXCEEDED",)
            return [model, over], None, None
        if kind == "dx":
            profiles = self._profiles()
            rng.shuffle(profiles)
            for profile in profiles:
                code = rng.choice(profile.codes)
                options = [
                    u
                    for u in self.t2.unrelated
                    if not self._supported(code, [u[0]], profile.modifiers)
                ]
                if not options:
                    continue
                mismatch = self._line(profile, "approve", code)
                mismatch.unrelated = rng.choice(options)
                mismatch.expect_reasons = ("DN_DX_NOT_SUPPORTED",)
                mismatch.day_offset = rng.randint(10, 20)
                partners = [
                    p
                    for p in self._profiles({profile.policy_id})
                    if p.profile_id != profile.profile_id
                ]
                partner = (  # the same specialty, so one provider bills both lines
                    self._policy_line(rng.choice(partners), self._mode())
                    if partners
                    else LineV2(code=rng.choice(OFFICE_CODES), profile=None)
                )
                return [partner, mismatch], None, None
            raise ScenarioError("no diagnosis mismatch available")
        pairs = []
        for profile in self._profiles():
            for a in profile.codes:
                for b in profile.codes:
                    if a != b and self.cb.ncci_indicator(a, b, DOS_START) in ("0", "1"):
                        pairs.append((profile, a, b))
        if not pairs:
            raise ScenarioError("no NCCI pair within a profile")
        profile, column1, column2 = rng.choice(pairs)
        model = self._policy_line(profile, self._mode(), column1)
        bundled = self._line(profile, "approve", column2)
        bundled.states = {c: model.states.get(c, s) for c, s in bundled.states.items()}
        bundled.modifiers = ()
        bundled.expect_reasons = ("DN_NCCI_BUNDLED",)
        return [model, bundled], None, None

    def _policy_of(self, code: str) -> str | None:
        entry = self.cur.scope.get(code)
        return entry.policy_id if entry else None

    def _supported(self, code: str, diagnoses: list[str], modifiers: Sequence[str]) -> bool:
        """R15's own check (D-RULE-4) on a one-line claim with these diagnoses."""
        from app.rules.lcd_edits import supported

        support = self.rules_reference.diagnosis_support.get(code)
        if support is None:
            return True
        claim = IntakeClaim.model_construct(diagnoses=list(diagnoses))
        line = _LineView(code, list(modifiers), ["ABCDEFGHIJKL"[i] for i in range(len(diagnoses))])
        return supported(claim, line, support, self.rules_reference)  # type: ignore[arg-type]

    # --- building --------------------------------------------------------------------------------

    def build(self, scenario_type: str, claim_id: str, oon_rate: float = 0.1) -> Scenario:  # type: ignore[override]
        last_error: Exception | None = None
        for _ in range(60):
            self.template_set = self.rng.choice(self.styles)
            try:
                lines, provider_types, plans = self._plan(scenario_type)
                return self._build_v2(
                    scenario_type, claim_id, lines, provider_types, plans, oon_rate
                )
            except ScenarioError as error:
                last_error = error
        raise ScenarioError(f"could not build {scenario_type}: {last_error}")

    def _build_v2(
        self,
        scenario_type: str,
        claim_id: str,
        planned: list[LineV2],
        provider_types: set[str] | None,
        plans: set[str] | None,
        oon_rate: float,
    ) -> Scenario:
        rng, cur = self.rng, self.cur
        types = provider_types or set.intersection(
            *(set(cur.scope[line.code].provider_types) for line in planned)
        )
        if not types:
            raise ScenarioError("lines share no provider type")
        allowed_plans = set(plans or cur.plans)
        for line in planned:
            if "DN_EXCLUDED" not in line.expect_reasons:
                allowed_plans -= {
                    e.plan_id for e in cur.exclusions if e.procedure_code == line.code
                }
        oon = (
            scenario_type not in ("office_same_day",)
            and rng.random() < oon_rate
            and bool(allowed_plans & set(OON_PLANS))
        )
        if oon:
            allowed_plans &= set(OON_PLANS)
        if not allowed_plans:
            raise ScenarioError("no plan fits")
        first_day = DOS_START + timedelta(days=rng.randint(0, 60))
        policies = sorted({line.profile.policy_id for line in planned if line.profile})
        min_age = max([MIN_AGE.get(p, 18) for p in policies] or [0])
        member = self._pick_member(allowed_plans, min_age, first_day)
        plan = cur.plans[member["plan_id"]]
        provider = self._pick_provider(types, plan.plan_id, not oon)
        network = Network.OUT_OF_NETWORK if oon else Network.IN_NETWORK
        days = [first_day + timedelta(days=line.day_offset) for line in planned]
        if max(days) > DOS_END:
            raise ScenarioError("dates outside the window")

        diagnoses, pointers = self._diagnoses_v2(planned)
        notes, evidence = self._notes_v2(planned)
        referring = None
        if provider["provider_type"] in plan.referral_required_provider_types:
            referring = self._pick_provider({"PRIMARY_CARE"}, plan.plan_id, True)["npi"]
        auths = self._authorizations(member, provider, planned, days, plan.plan_id)  # type: ignore[arg-type]
        received = max(days) + timedelta(days=rng.randint(2, 25))
        service_lines = []
        for n, (line, day) in enumerate(zip(planned, days, strict=True), start=1):
            fee = self.cb.fees[line.code][0] * line.units
            charge = apply_bps(fee, rng.randint(130, 220) * 100)
            service_lines.append(
                {
                    "line_no": n,
                    "date_of_service": day,
                    "place_of_service": "11"
                    if line.profile is None
                    else rng.choice(line.profile.pos),
                    "procedure_code": line.code,
                    "modifiers": list(line.modifiers),
                    "diagnosis_pointers": pointers[n - 1],
                    "units": line.units,
                    "charge_cents": -(-charge // 100) * 100,
                    "rendering_npi": provider["npi"],
                }
            )
        claim = IntakeClaim.model_validate(
            {
                "claim_id": claim_id,
                "member_id": member["member_id"],
                "patient": {
                    "first_name": member["first_name"],
                    "last_name": member["last_name"],
                    "date_of_birth": member["date_of_birth"],
                    "sex": member["sex"],
                    "address": {
                        "line1": member["address_line"],
                        "city": member["city"],
                        "state": member["state"],
                        "zip_code": member["zip_code"],
                    },
                },
                "subscriber_is_patient": True,
                "billing_npi": provider["npi"],
                "billing_tin": provider["tin"],
                "referring_npi": referring,
                "prior_auth_number": auths[0]["auth_number"] if auths else None,
                "diagnoses": diagnoses,
                "service_lines": service_lines,
                "clinical_notes": notes,
                "received_date": received,
                "frequency_code": "1",
                "other_coverage": None,
            }
        )
        rules = self.engine(claim, auths)
        if rules.claim_outcome is not RuleOutcomeValue.PASS:
            stopped = [r.rule_id for r in rules.rule_results if not r.passed]
            raise ScenarioError(f"the engine stops the claim ({stopped})")
        for line, outcome in zip(planned, rules.line_outcomes, strict=True):
            if tuple(outcome.reason_codes) != line.expect_reasons:
                raise ScenarioError(f"line {outcome.line_no}: {outcome.reason_codes}")
            if outcome.outcome == "PASS" and set(outcome.flags) != set(line.expect_flags):
                raise ScenarioError(f"line {outcome.line_no}: flags {outcome.flags}")
        if (rules.flags == ["OON"]) != oon:
            raise ScenarioError("network flag does not match")
        context = self._context_v2(claim, rules, planned, provider, member, plan.plan_id, network)
        target = self._target_v2(planned, rules, context, evidence, oon)
        labels = []
        target_lines = {line.line_no: line for line in target.lines}
        for outcome in rules.line_outcomes:
            if outcome.outcome == "DENY":
                labels.append(
                    {
                        "line_no": outcome.line_no,
                        "decision": "DENY",
                        "source": "RULE",
                        "reason_codes": list(outcome.reason_codes),
                    }
                )
            else:
                slm = target_lines[outcome.line_no]
                labels.append(
                    {
                        "line_no": outcome.line_no,
                        "decision": slm.decision.value,
                        "source": "MODEL",
                        "reason_codes": list(slm.reasons),
                        "benefit_category": slm.benefit_category,
                    }
                )
        return Scenario(
            scenario_type=scenario_type,
            template_set=self.template_set,
            claim=claim,
            rules=rules,
            context=context,
            target=target,
            line_labels=labels,
            policy_ids=policies,
            profile_keys=sorted({line.profile.key for line in planned if line.profile}),
            authorizations=auths,
            member=member,
            provider=provider,
        )

    def engine(self, claim: IntakeClaim, auths: list[dict[str, Any]]) -> RulesOutcome:
        """The rules engine on the claim with the generated reference data and the claim's own
        authorizations (D-GEN-5)."""
        reference = dataclasses.replace(
            self.rules_reference,
            authorizations=self.rules_reference.authorizations
            + tuple(authorization_ref(a) for a in auths),
        )
        return evaluate(claim.model_dump(mode="json"), {}, reference, confidence_min=CONFIDENCE_MIN)

    def _diagnoses_v2(self, planned: list[LineV2]) -> tuple[list[str], list[list[str]]]:
        diagnoses: list[str] = []
        pointers: list[list[str]] = []
        chosen: dict[str, tuple[str, ...]] = {}
        for line in planned:
            if line.unrelated and line.profile is not None:  # an R15 mismatch: only this code
                codes: tuple[str, ...] = (line.unrelated[0],)
            elif line.profile:
                key = line.profile.key
                if key not in chosen:
                    overrides = [
                        self.t2.criteria[c].diagnoses_when_not_met
                        for c, s in line.states.items()
                        if s == "not_met" and self.t2.criteria[c].diagnoses_when_not_met
                    ]
                    options = (
                        [(code,) for code in overrides[0]]
                        if overrides
                        else line.profile.diagnosis_sets()
                    )
                    supported = [
                        o for o in options if self._supported(line.code, list(o), line.modifiers)
                    ]
                    if not supported:
                        raise ScenarioError(f"{key}: no diagnosis R15 accepts for {line.code}")
                    chosen[key] = self.rng.choice(supported)
                codes = chosen[key]
            elif line.unrelated:  # an office visit's condition
                codes = (line.unrelated[0],)
            else:
                codes = ()
            letters = []
            for code in codes:
                if code not in diagnoses:
                    diagnoses.append(code)
                letters.append("ABCDEFGHIJKL"[diagnoses.index(code)])
            pointers.append(letters)
        for i in range(len(planned)):  # office visits point at the claim's first diagnosis
            if not pointers[i]:
                if not diagnoses:
                    raise ScenarioError("office visit without a diagnosis")
                pointers[i] = ["A"]
        return diagnoses, pointers

    # --- notes -----------------------------------------------------------------------------------

    def _wording(self, options: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
        """The sentences of the record's style: A and C read wording A, B reads B, D mixes them
        sentence by sentence; a criterion with one wording only uses it."""
        style = self.template_set
        prefer = {"A": "A", "B": "B", "C": self._c_wording, "D": self.rng.choice(WORDINGS)}[style]
        if prefer in options:
            return options[prefer]
        return next(iter(options.values()))

    def _notes_v2(self, planned: list[LineV2]) -> tuple[str, dict[tuple[str, str], str]]:
        rng, t = self.rng, self.t2
        self._c_wording = rng.choice(WORDINGS)
        lead_sentences: list[str] = []
        body: list[str] = []
        evidence: dict[tuple[str, str], str] = {}
        done: set[str] = set()
        slots_by_profile: dict[str, dict[str, str]] = {}
        states_by_profile: dict[str, dict[str, str]] = {}
        for line in planned:
            if line.profile:
                states_by_profile.setdefault(line.profile.key, {}).update(line.states)
        for line in planned:
            if line.unrelated and line.unrelated[0] not in done:
                text = self._wording({k: (v,) for k, v in line.unrelated[1].items()})[0]
                body.append(text)
                done.add(line.unrelated[0])
            if not line.profile or line.profile.key in done:
                continue
            profile = line.profile
            done.add(profile.key)
            slots = draw_slots(rng, profile.slots)
            slots["units"] = str(line.units)
            slots_by_profile[profile.key] = slots
            lead_sentences.append(fill(rng.choice(self._wording(profile.lead)), slots))
            states = states_by_profile[profile.key]
            for criterion_id, state in states.items():
                notes = t.criteria[criterion_id]
                if state == "met":
                    text = fill(rng.choice(self._wording(notes.met)), slots)
                elif state == "not_met" and notes.not_met:
                    text = fill(rng.choice(self._wording(notes.not_met)), slots)
                elif state == "missing" and notes.situation:
                    body.append(fill(rng.choice(self._wording(notes.situation)), slots))
                    continue
                else:
                    continue
                body.append(text)
                evidence[(profile.key, criterion_id)] = text
            for criterion_id, state in states.items():  # criteria failing together share it
                if state == "not_met" and (profile.key, criterion_id) not in evidence:
                    trigger = next(
                        c
                        for c in states
                        if criterion_id in t.criteria[c].with_not_met
                        and states[c] == "not_met"
                        and (profile.key, c) in evidence
                    )
                    evidence[(profile.key, criterion_id)] = evidence[(profile.key, trigger)]
        for line in planned:
            if line.bypass is None or line.bypass[1] != "met":
                continue
            key = line.bypass[0]
            slots = dict(slots_by_profile.get(line.profile.key, {})) if line.profile else {}
            slots.setdefault("site2", "left lower leg")
            slots["problem"] = rng.choice(t.problems)
            segments = rng.sample(COLON_SEGMENTS, 2)
            slots.update(
                {"size": str(rng.randint(6, 15)), "seg1": segments[0], "seg2": segments[1]}
            )
            spec = t.distinct[key] if key in t.distinct else t.bypass[key]
            text = fill(self._wording(_sets(spec["met"]))[0], slots)
            body.append(text)
            evidence[(f"line{planned.index(line)}", "bypass")] = text
        if any(line.profile is None for line in planned):
            body.append(rng.choice(self._wording(t.office_visit)))
        procedures = [
            self.cur.descriptions[line.code]
            for line in planned
            if line.profile and not line.expect_reasons
        ]
        plan = ""
        if procedures:
            listed = "; ".join(p[0].lower() + p[1:] for p in dict.fromkeys(procedures))
            wording = "B" if self.template_set == "B" else "A"
            plan = t.plan_line[wording].format(procedure=listed)
        fillers = list(rng.sample(self._wording(t.filler), rng.randint(1, 2)))
        notes = self._layout(lead_sentences, body, fillers, plan)
        if LEAKAGE.search(notes):
            raise AssertionError(f"leakage word in notes: {notes}")
        return notes, evidence

    def _layout(self, lead: list[str], body: list[str], fillers: list[str], plan: str) -> str:
        rng, style = self.rng, self.template_set
        if style == "C":  # sections
            findings = list(body)
            for filler in fillers:
                findings.insert(rng.randint(0, len(findings)), filler)
            parts = [f"Reason for visit: {' '.join(lead)}" if lead else ""]
            parts.append(f"Findings: {' '.join(findings)}")
            if plan:
                parts.append(plan if plan.startswith("Plan:") else f"Plan: {plan}")
            return " ".join(p for p in parts if p)
        sentences = lead + body
        for filler in fillers:
            sentences.insert(rng.randint(min(1, len(sentences)), len(sentences)), filler)
        if plan:
            sentences.append(plan)
        if style == "D":  # numbered list, held out of training
            return " ".join(f"{n}) {s}" for n, s in enumerate(sentences, start=1))
        return " ".join(sentences)

    # --- context and labels ----------------------------------------------------------------------

    def _context_v2(
        self,
        claim: IntakeClaim,
        rules: RulesOutcome,
        planned: list[LineV2],
        provider: dict[str, Any],
        member: dict[str, Any],
        plan_id: str,
        network: Network,
    ) -> ContextPackage:
        primary_care = self.cur.provider_types[provider["provider_type"]]
        lines = []
        for outcome, line in zip(rules.line_outcomes, planned, strict=True):
            if outcome.outcome != "PASS":
                continue
            categories = list(self.cur.scope[line.code].candidate_categories)
            if line.profile is None:
                categories = ["OFFICE_VISIT_PCP" if primary_care else "OFFICE_VISIT_SPECIALIST"]
            facts = []
            for category in categories:
                benefit = self.cur.benefit(plan_id, category)
                facts.append(
                    BenefitFact(
                        benefit_category=category,
                        covered=benefit.covered,
                        auth_required=benefit.auth_required,
                        visit_limit=benefit.visit_limit,
                        visits_used=self.visits.get((member["member_id"], category), 0)
                        if benefit.visit_limit
                        else 0,
                        cost_share_rule=CostShareRule(benefit.cost_share_rule),
                    )
                )
            service = claim.service_lines[outcome.line_no - 1]
            criteria = self.retriever.retrieve(
                "", plan_id, service.date_of_service, line.code, self.excluded_policies
            )
            lines.append(
                LineContext(
                    line_no=outcome.line_no,
                    procedure_code=line.code,
                    candidate_benefits=facts,
                    criteria=criteria,
                    rule_flags=list(outcome.flags),
                )
            )
        return ContextPackage(
            claim_id=claim.claim_id,
            plan_id=plan_id,
            plan_type=self.cur.plans[plan_id].plan_type,
            network=network,
            excluded_codes=sorted(self.cur.excluded_codes(plan_id)),
            lines=lines,
        )

    def _target_v2(
        self,
        planned: list[LineV2],
        rules: RulesOutcome,
        context: ContextPackage,
        evidence: dict[tuple[str, str], str],
        oon: bool,
    ) -> SLMOutput:
        """Statuses from the states of the criteria the lookup returned; the decision derived by
        the pipeline's code (D-DEC-1)."""
        by_line = {c.line_no: c for c in context.lines}
        slm_lines = []
        for outcome, line in zip(rules.line_outcomes, planned, strict=True):
            if outcome.outcome != "PASS":
                continue
            line_context = by_line[outcome.line_no]
            shown = [c.criterion_id for c in line_context.criteria]
            if line.profile is not None and shown != list(line.states):
                raise ScenarioError(f"lookup {shown} != planned {list(line.states)}")
            results = []
            kinds: list[tuple[CriterionStatus, bool]] = []
            for retrieved in line_context.criteria:
                criterion_id = retrieved.criterion_id
                role = self.kinds[criterion_id].role
                state = line.states[criterion_id]
                status = STATUS[(role, state)]
                if status in (CriterionStatus.MET, CriterionStatus.NOT_MET):
                    text = evidence[(line.profile.key, criterion_id)]  # type: ignore[union-attr]
                elif status is CriterionStatus.NOT_DOCUMENTED:
                    text = NOT_DOCUMENTED
                else:
                    text = NOT_APPLICABLE
                results.append(
                    CriterionResult(criterion_id=criterion_id, status=status, evidence=text)
                )
                kinds.append((status, retrieved.group is not None))
            decision, unsatisfied = implied_decision(kinds)
            bypass_missing = (
                line.bypass is not None
                and line.bypass[1] == "missing"
                and "NCCI_BYPASS" in outcome.flags
            )
            if decision is LineDecision.APPROVE and bypass_missing:
                decision = LineDecision.PEND
            reasons: list[str] = []
            missing: list[str] = []
            if decision is LineDecision.DENY:
                exclusion = any(
                    r.status is CriterionStatus.NOT_MET
                    and self.kinds[r.criterion_id].role == "exclusion"
                    for r in results
                )
                reasons = [DENY_EXCLUSION if exclusion else DENY_CRITERION]
            elif decision is LineDecision.PEND:
                reasons = [PEND_MISSING]
                if unsatisfied:
                    missing.append(NO_INDICATION)
                missing += [
                    self.t2.criteria[r.criterion_id].missing
                    for r in results
                    if r.status is CriterionStatus.NOT_DOCUMENTED
                ]
                if bypass_missing:
                    assert line.bypass is not None
                    key = line.bypass[0]
                    spec = self.t2.distinct[key] if key in self.t2.distinct else self.t2.bypass[key]
                    missing.append(spec["missing"])
            slm = SLMLine(
                line_no=outcome.line_no,
                decision=decision,
                benefit_category=self._category(line, line_context),  # type: ignore[arg-type]
                criteria=results,
                reasons=reasons,
                missing_information=missing,
            )
            derived = derive_line(slm, line_context.criteria, outcome.flags)
            if derived.decision is not decision or derived.changed:
                raise AssertionError(f"label {decision} != derived {derived.decision}")
            slm_lines.append(slm)
        if not slm_lines:
            raise ScenarioError("every line is denied by the rules")
        return SLMOutput(lines=slm_lines, complexity=self._complexity(slm_lines, rules, oon))


class _LineView:
    """The fields of a service line R15's `supported` reads."""

    def __init__(self, code: str, modifiers: list[str], pointers: list[str]) -> None:
        self.procedure_code = code
        self.modifiers = modifiers
        self.diagnosis_pointers = pointers


def authorization_ref(row: Mapping[str, Any]) -> AuthorizationRef:
    def day(value: Any) -> date:
        return value if isinstance(value, date) else date.fromisoformat(value)

    return AuthorizationRef(
        auth_number=row["auth_number"],
        member_id=row["member_id"],
        provider_npi=row["provider_npi"],
        procedure_code=row["procedure_code"],
        start_date=day(row["start_date"]),
        end_date=day(row["end_date"]),
    )


@lru_cache
def _code_tables() -> Any:
    return load_code_tables(rule_codes(load_curated()))


def rules_reference(reference: ReferenceData) -> RulesReference:
    """The engine's reference for generated claims: the generated members, providers, networks and
    authorizations, with the full code tables (data/raw)."""
    return build_reference(
        load_curated(),
        _code_tables(),
        reference_dicts(reference.members),
        reference_dicts(reference.providers),
        reference_dicts(reference.provider_networks),
        reference_dicts(reference.authorizations),
    )
