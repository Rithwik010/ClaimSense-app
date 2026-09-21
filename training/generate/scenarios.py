"""Scenario engine: ground truth first, then the claim (INSTRUCTIONS.md §9.4).

A scenario fixes, for every line, which coverage criteria are met, not met or undocumented, whether
the diagnosis fits, and whether a bypass modifier is documented. From that it builds the clinical
notes, the `IntakeClaim`, the Group C rule outcome, the `ContextPackage` (plan facts and simulated
retrieval) and the target `SLMOutput`. Labels come only from the coverage policies, the billing-
article diagnosis groups and the NCCI/MUE files (H6).

Retrieval is simulated until P3.3 exists: each policy line gets its profile's criteria (at most
RAG_TOP_K) plus distractors from other policies; office-visit lines get distractors only.
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.calculator.money import apply_bps
from app.domain.contracts import (
    BenefitFact,
    Complexity,
    ContextPackage,
    CostShareRule,
    CriterionResult,
    IntakeClaim,
    LineContext,
    LineDecision,
    LineRuleOutcome,
    Network,
    RetrievedCriterion,
    RuleOutcomeValue,
    RuleResult,
    RulesOutcome,
    SLMLine,
    SLMOutput,
)
from app.ml.prompt import NOT_DOCUMENTED, age_on
from training.generate.codebook import Codebook, load_codebook
from training.generate.common import DEFAULT_SEED, DOS_END, DOS_START
from training.generate.notes import (
    LEAKAGE,
    Profile,
    Templates,
    draw_slots,
    fill,
    load_templates,
    profile_diagnosis_sets,
)
from training.generate.reference import ReferenceData, generate_reference

GENERATOR_VERSION = "scenarios-v1"
RAG_TOP_K = 3
MIN_AGE = {
    "POL-SURG-001": 50,
    "POL-SURG-002": 40,
    "POL-SURG-003": 30,
    "POL-SURG-004": 35,
    "POL-FOOT-001": 40,
}
OFFICE_CODES = ("99202", "99203", "99204", "99212", "99213", "99214")
OON_PLANS = ("PLN-PPO-GOLD", "PLN-PPO-SILVER", "PLN-HDHP")
TWO_POLICY_PAIRS = (
    ("POL-CAR-001", "POL-CAR-002", "CARDIOLOGY"),
    ("POL-PAIN-001", "POL-PAIN-002", "PAIN_MEDICINE"),
    ("POL-WOUND-001", "POL-FOOT-001", "PODIATRY"),
    ("POL-SURG-001", "POL-SURG-004", "OPHTHALMOLOGY"),
    ("POL-IMG-001", "POL-IMG-002", "RADIOLOGY"),
)
BYPASS_SETS = {
    "wound": ("POL-WOUND-001", "11042", "97597"),
    "colon": ("POL-SURG-002", "45385", "45380"),
}
EXCLUDED_EXTRAS = (  # plan, excluded code, profile key
    ("PLN-PPO-SILVER", "64635", "POL-PAIN-002/lumbar_facet"),
    ("PLN-EPO", "97140", "POL-REHAB-001/treatment"),
    ("PLN-HMO", "95044", "POL-DX-003/contact"),
)
COLON_SEGMENTS = (
    "sigmoid colon",
    "descending colon",
    "transverse colon",
    "ascending colon",
    "cecum",
)
LINE_MODES = ("approve", "pend", "deny_criterion", "deny_dx")
MODE_WEIGHTS = (50, 20, 15, 15)

SCENARIO_TYPES = (
    "approve_single",
    "deny_dx",
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
)
ALL_LINES_DENIED = ("excluded_only", "mue_only")  # every line denied by Group C: no model call


class ScenarioError(Exception):
    """The requested scenario cannot be built with these policies; the caller retries."""


@dataclass
class PlannedLine:
    code: str
    profile: Profile | None  # None for an office visit
    mode: str = "approve"
    states: dict[str, str] = field(default_factory=dict)  # criterion ID -> met | not_met | missing
    unrelated: tuple[str, dict[str, str]] | None = None  # diagnosis that does not fit the service
    bypass: str | None = None  # met | missing: notes document a distinct service
    modifiers: tuple[str, ...] = ()
    units: int = 1
    day_offset: int = 0
    expect_rule_denial: bool = False


@dataclass
class Scenario:
    scenario_type: str
    template_set: str
    claim: IntakeClaim
    rules: RulesOutcome
    context: ContextPackage
    target: SLMOutput | None
    line_labels: list[dict[str, Any]]
    policy_ids: list[str]
    profile_keys: list[str]
    authorizations: list[dict[str, Any]]
    member: dict[str, Any]
    provider: dict[str, Any]

    def metadata(self) -> dict[str, Any]:
        return {
            "generator_version": GENERATOR_VERSION,
            "scenario_type": self.scenario_type,
            "template_id": self.template_set,
            "policy_ids": self.policy_ids,
            "profiles": self.profile_keys,
            "plan_id": self.context.plan_id,
            "network": self.context.network.value,
            "line_labels": self.line_labels,
            "complexity": self.target.complexity.value if self.target else None,
        }


def _mode_weights(rng: random.Random) -> str:
    return rng.choices(LINE_MODES, weights=MODE_WEIGHTS)[0]


class ScenarioBuilder:
    """Builds scenarios for one split: `policies` may appear as claim lines, `distractor_policies`
    only as retrieved distractors, and `template_set` picks the note wording (A or B)."""

    def __init__(
        self,
        seed: int,
        template_set: str,
        policies: set[str],
        distractor_policies: set[str],
        reference: ReferenceData | None = None,
    ) -> None:
        self.rng = random.Random(seed)
        self.seed = seed
        self.template_set = template_set
        self.cb: Codebook = load_codebook()
        self.cur = self.cb.curated
        self.t: Templates = load_templates()
        self.policies = {p for p in policies if template_set in self.t.template_sets(p)}
        self.distractor_ids = [
            c.criterion_id
            for p in sorted(distractor_policies)
            for c in self.cur.policies[p].criteria
        ]
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

    # --- choices ---------------------------------------------------------------------------------

    @staticmethod
    def _active(member: dict[str, Any]) -> bool:
        return member["coverage_start"] <= DOS_START and (
            member["coverage_end"] is None or member["coverage_end"] >= DOS_END
        )

    def _profiles(self, policies: set[str] | None = None) -> list[Profile]:
        chosen = sorted(policies if policies is not None else self.policies)
        return [p for policy in chosen if policy in self.policies for p in self.t.profiles[policy]]

    def _states(self, profile: Profile, mode: str) -> dict[str, str] | None:
        states = {c: "met" for c in profile.criteria}
        ts = self.template_set
        if mode in ("approve", "deny_dx"):
            return states
        if mode == "pend":
            count = 2 if len(profile.criteria) >= 2 and self.rng.random() < 0.2 else 1
            for c in self.rng.sample(profile.criteria, count):
                states[c] = "missing"
            return states
        kind = "exclusion" if mode == "deny_exclusion" else "required"
        if kind == "exclusion" and not profile.exclusion_scenarios:
            return None
        options = [
            c
            for c in profile.criteria
            if self.t.criteria[c].kind == kind and ts in self.t.criteria[c].not_met
        ]
        if not options:
            return None
        target = self.rng.choice(options)
        states[target] = "not_met"
        for other in self.t.criteria[target].with_not_met:
            if other in states:
                states[other] = "not_met"
        return states

    def _unrelated_for(self, codes: list[str]) -> tuple[str, dict[str, str]]:
        options = [
            u for u in self.t.unrelated if not any(self.cb.supported(c, [u[0]]) for c in codes)
        ]
        if not options:
            raise ScenarioError(f"no unrelated condition for {codes}")
        return self.rng.choice(options)

    def _units(self, profile: Profile | None, code: str) -> int:
        spec = profile.units.get(code) if profile else None
        if not spec:
            return 1
        low, high = (int(x) for x in spec.split("-"))
        return self.rng.randint(low, high)

    def _policy_line(self, profile: Profile, mode: str, code: str | None = None) -> PlannedLine:
        states = self._states(profile, mode)
        if states is None:
            raise ScenarioError(f"{profile.key} cannot produce {mode}")
        code = code or self.rng.choice(profile.codes)
        line = PlannedLine(
            code=code, profile=profile, mode=mode, states=states, units=self._units(profile, code)
        )
        if mode == "deny_dx":
            line.unrelated = self._unrelated_for([code])
        return line

    def _profile_for(self, mode: str, policies: set[str] | None = None) -> Profile:
        profiles = self._profiles(policies)
        self.rng.shuffle(profiles)
        for profile in profiles:
            if self._states(profile, mode) is not None:
                return profile
        raise ScenarioError(f"no profile supports {mode}")

    # --- planning --------------------------------------------------------------------------------

    def _plan(
        self, scenario_type: str
    ) -> tuple[list[PlannedLine], set[str] | None, set[str] | None]:
        """Lines, allowed provider types (None = from the codes) and allowed plans (None = any)."""
        rng = self.rng
        single = {
            "approve_single": "approve",
            "deny_dx": "deny_dx",
            "deny_criterion": "deny_criterion",
            "deny_exclusion": "deny_exclusion",
            "pend_missing": "pend",
        }
        if scenario_type in single:
            mode = single[scenario_type]
            return [self._policy_line(self._profile_for(mode), mode)], None, None
        if scenario_type == "office_visit":
            reason = rng.choice(self.t.unrelated)
            line = PlannedLine(code=rng.choice(OFFICE_CODES), profile=None, unrelated=reason)
            types = (
                {"PRIMARY_CARE"}
                if rng.random() < 0.7
                else set(self.cur.scope["99213"].provider_types)
            )
            return [line], types, None
        if scenario_type in ("office_plus_procedure", "office_same_day"):
            office_types = set(self.cur.scope["99213"].provider_types)
            profiles = [
                p
                for p in self._profiles()
                if office_types & set(self.cur.scope[p.codes[0]].provider_types)
            ]
            rng.shuffle(profiles)
            for profile in profiles:
                procedure = self._policy_line(profile, _mode_weights(rng))
                office = PlannedLine(code=rng.choice(OFFICE_CODES), profile=None)
                if scenario_type == "office_plus_procedure":
                    procedure.day_offset = rng.randint(7, 21)
                    return [office, procedure], None, None
                if self.cb.ncci_indicator(procedure.code, office.code, DOS_START) in ("0", "1"):
                    office.expect_rule_denial = True
                    return [office, procedure], None, None
            raise ScenarioError("no same-day office/procedure pair")
        if scenario_type == "same_profile_multi":
            profiles = [p for p in self._profiles() if len(p.codes) >= 2]
            if not profiles:
                raise ScenarioError("no profile with several codes")
            profile = rng.choice(profiles)
            mode = rng.choices(
                ("approve", "pend", "deny_criterion", "deny_dx"), weights=(55, 20, 15, 10)
            )[0]
            codes = rng.sample(profile.codes, min(len(profile.codes), rng.choice((2, 2, 3))))
            if any(self.cb.ncci_indicator(a, b, DOS_START) for a in codes for b in codes if a != b):
                raise ScenarioError(f"{profile.key}: codes {codes} form an NCCI pair")
            first = self._policy_line(profile, mode, codes[0])
            lines = [first]
            for code in codes[1:]:
                lines.append(
                    PlannedLine(
                        code=code,
                        profile=profile,
                        mode=mode,
                        states=dict(first.states),
                        units=self._units(profile, code),
                    )
                )
            if mode == "deny_dx":
                reason = self._unrelated_for(codes)
                for line in lines:
                    line.unrelated = reason
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
                lines.append(self._policy_line(rng.choice(profiles), _mode_weights(rng)))
            return lines, {provider_type}, None
        if scenario_type == "ncci_bypass":
            options = [k for k, (policy, _, _) in BYPASS_SETS.items() if policy in self.policies]
            if not options:
                raise ScenarioError("no bypass pair in these policies")
            kind = rng.choice(options)
            policy_id, column1, column2 = BYPASS_SETS[kind]
            profile = rng.choice(
                [p for p in self._profiles({policy_id}) if {column1, column2} <= set(p.codes)]
            )
            mode = "approve" if rng.random() < 0.8 else "pend"
            first = self._policy_line(profile, mode, column1)
            second = PlannedLine(
                code=column2,
                profile=profile,
                mode=mode,
                states=dict(first.states),
                modifiers=("XS",),
                bypass=rng.choice(("met", "missing")),
            )
            second.units = 1
            return [first, second], None, None
        if scenario_type == "rule_denied_line":
            return self._plan_rule_denied()
        if scenario_type == "excluded_only":
            options = [e for e in EXCLUDED_EXTRAS if e[2].split("/")[0] in self.policies]
            if not options:
                raise ScenarioError("no excluded code in these policies")
            plan_id, code, key = rng.choice(options)
            profile = next(p for p in self._profiles() if p.key == key)
            line = self._policy_line(profile, "approve", code)
            line.expect_rule_denial = True
            return [line], None, {plan_id}
        if scenario_type == "mue_only":
            if "POL-REHAB-001" not in self.policies:
                raise ScenarioError("MUE scenarios use POL-REHAB-001")
            profile = next(
                p for p in self._profiles({"POL-REHAB-001"}) if p.profile_id == "treatment"
            )
            line = self._policy_line(profile, "approve", "97110")
            line.units, line.expect_rule_denial = rng.randint(7, 9), True
            return [line], None, None
        raise ValueError(f"unknown scenario type {scenario_type}")

    def _plan_rule_denied(self) -> tuple[list[PlannedLine], set[str] | None, set[str] | None]:
        rng = self.rng
        kind = rng.choice(("ncci", "ncci", "excluded", "mue"))
        if kind == "excluded":
            options = [e for e in EXCLUDED_EXTRAS if e[2].split("/")[0] in self.policies]
            if options:
                plan_id, code, key = rng.choice(options)
                profile = next(p for p in self._profiles() if p.key == key)
                others = [c for c in profile.codes if c != code]
                model = (
                    self._policy_line(profile, _mode_weights(rng), rng.choice(others))
                    if others
                    else PlannedLine(code=rng.choice(OFFICE_CODES), profile=None, day_offset=7)
                )
                states = (
                    dict(model.states) if model.profile else {c: "met" for c in profile.criteria}
                )
                excluded = PlannedLine(
                    code=code, profile=profile, states=states, expect_rule_denial=True
                )
                excluded.units = self._units(profile, code)
                return [model, excluded], None, {plan_id}
            kind = "ncci"
        if kind == "mue" and "POL-REHAB-001" in self.policies:
            profile = next(
                p for p in self._profiles({"POL-REHAB-001"}) if p.profile_id == "treatment"
            )
            model = self._policy_line(profile, _mode_weights(rng), "97530")
            over = PlannedLine(
                code="97110", profile=profile, states=dict(model.states), units=rng.randint(7, 9)
            )
            over.expect_rule_denial = True
            return [model, over], None, None
        pairs = []
        for profile in self._profiles():
            for a in profile.codes:
                for b in profile.codes:
                    if a != b and self.cb.ncci_indicator(a, b, DOS_START) in ("0", "1"):
                        pairs.append((profile, a, b))
        if not pairs:
            raise ScenarioError("no NCCI pair within a profile")
        profile, column1, column2 = rng.choice(pairs)
        model = self._policy_line(profile, _mode_weights(rng), column1)
        bundled = PlannedLine(
            code=column2, profile=profile, states=dict(model.states), expect_rule_denial=True
        )
        if model.unrelated:
            bundled.unrelated = model.unrelated
        return [model, bundled], None, None

    # --- building --------------------------------------------------------------------------------

    def build(self, scenario_type: str, claim_id: str, oon_rate: float = 0.1) -> Scenario:
        last_error: Exception | None = None
        for _ in range(40):
            try:
                lines, provider_types, plans = self._plan(scenario_type)
                return self._build(scenario_type, claim_id, lines, provider_types, plans, oon_rate)
            except ScenarioError as error:
                last_error = error
        raise ScenarioError(f"could not build {scenario_type}: {last_error}")

    def _pick_member(self, plans: set[str], min_age: int, first_day: date) -> dict[str, Any]:
        options = [
            m
            for m in self.members
            if m["plan_id"] in plans and age_on(m["date_of_birth"], first_day) >= min_age
        ]
        if not options:
            raise ScenarioError("no member fits")
        return self.rng.choice(options)

    def _pick_provider(self, types: set[str], plan_id: str, in_network: bool) -> dict[str, Any]:
        options = [
            p
            for p in self.providers.values()
            if p["provider_type"] in types
            and p["enrollment_status"] == "ENROLLED"
            and self.network.get((p["npi"], plan_id), False) == in_network
        ]
        if not options:
            raise ScenarioError("no provider fits")
        return self.rng.choice(sorted(options, key=lambda p: p["npi"]))

    def _build(
        self,
        scenario_type: str,
        claim_id: str,
        planned: list[PlannedLine],
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
            if not line.expect_rule_denial:
                allowed_plans -= {
                    e.plan_id for e in cur.exclusions if e.procedure_code == line.code
                }
        oon = (
            scenario_type != "office_same_day"
            and rng.random() < oon_rate
            and bool(allowed_plans & set(OON_PLANS))
        )
        if oon:
            allowed_plans &= set(OON_PLANS)
        first_day = DOS_START + timedelta(days=rng.randint(0, 60))
        policies = [line.profile.policy_id for line in planned if line.profile]
        min_age = max([MIN_AGE.get(p, 18) for p in policies] or [0])
        member = self._pick_member(allowed_plans, min_age, first_day)
        plan = cur.plans[member["plan_id"]]
        provider = self._pick_provider(types, plan.plan_id, not oon)
        network = Network.OUT_OF_NETWORK if oon else Network.IN_NETWORK

        # Dates: spread lines apart when an unintended NCCI pair would deny one of them.
        for i, line in enumerate(planned):
            for other in planned[:i]:
                if (
                    line.expect_rule_denial
                    or other.expect_rule_denial
                    or line.day_offset != other.day_offset
                ):
                    continue
                if "XS" in line.modifiers:
                    continue
                if self.cb.ncci_indicator(
                    other.code, line.code, first_day
                ) or self.cb.ncci_indicator(line.code, other.code, first_day):
                    line.day_offset = other.day_offset + rng.randint(7, 14)
        days = [first_day + timedelta(days=line.day_offset) for line in planned]
        if max(days) > DOS_END:
            raise ScenarioError("dates outside the window")

        rules = self._rules(claim_id, plan.plan_id, planned, days, oon)
        denied = [o.line_no for o in rules.line_outcomes if o.outcome == "DENY"]
        expected = [i + 1 for i, line in enumerate(planned) if line.expect_rule_denial]
        all_denied = scenario_type in ALL_LINES_DENIED
        if denied != expected or all_denied == any(
            o.outcome == "PASS" for o in rules.line_outcomes
        ):
            raise ScenarioError("rule outcome does not match the scenario")

        diagnoses, pointers, profile_dx = self._diagnoses(planned)
        notes, evidence = self._notes(planned)
        referring = None
        if provider["provider_type"] in plan.referral_required_provider_types:
            referring = self._pick_provider({"PRIMARY_CARE"}, plan.plan_id, True)["npi"]
        auths = self._authorizations(member, provider, planned, days, plan.plan_id)
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
        context = self._context(claim, rules, planned, provider, member, plan.plan_id, network)
        target = None if all_denied else self._target(planned, rules, context, evidence, oon)
        labels = []
        target_lines = {line.line_no: line for line in target.lines} if target else {}
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
            policy_ids=sorted({p for p in policies}),
            profile_keys=sorted({line.profile.key for line in planned if line.profile}),
            authorizations=auths,
            member=member,
            provider=provider,
        )

    def _rules(
        self, claim_id: str, plan_id: str, planned: list[PlannedLine], days: list[date], oon: bool
    ) -> RulesOutcome:
        outcomes = self.cb.line_rule_outcomes(
            plan_id,
            [
                (line.code, day, line.units, line.modifiers)
                for line, day in zip(planned, days, strict=True)
            ],
        )
        rule_of = {"DN_NCCI_BUNDLED": "R11", "DN_MUE_EXCEEDED": "R12", "DN_EXCLUDED": "R13"}
        results: list[RuleResult] = []
        if oon:
            results.append(
                RuleResult(
                    rule_id="R08",
                    passed=True,
                    outcome=RuleOutcomeValue.PASS,
                    detail="Out-of-network provider; the plan covers out-of-network care",
                    fields_used=["billing_npi", "member_id"],
                )
            )
        line_outcomes = []
        for n, outcome in enumerate(outcomes, start=1):
            for reason in outcome.reason_codes:
                results.append(
                    RuleResult(
                        rule_id=rule_of[reason],
                        passed=False,
                        outcome=RuleOutcomeValue.DENY,
                        reason_code=reason,
                        detail=f"Line {n} {planned[n - 1].code}: {reason}",
                        fields_used=[
                            f"service_lines.{n - 1}.procedure_code",
                            f"service_lines.{n - 1}.units",
                        ],
                        line_no=n,
                    )
                )
            if "NCCI_BYPASS" in outcome.flags:
                results.append(
                    RuleResult(
                        rule_id="R11",
                        passed=True,
                        outcome=RuleOutcomeValue.PASS,
                        detail=f"Line {n}: NCCI pair with a bypass modifier; check the notes",
                        fields_used=[f"service_lines.{n - 1}.modifiers"],
                        line_no=n,
                    )
                )
            line_outcomes.append(
                LineRuleOutcome(
                    line_no=n,
                    outcome=outcome.outcome,
                    reason_codes=list(outcome.reason_codes),
                    flags=list(outcome.flags),
                )
            )
        passed = any(o.outcome == "PASS" for o in line_outcomes)
        return RulesOutcome(
            claim_outcome=RuleOutcomeValue.PASS if passed else RuleOutcomeValue.DENY,
            rule_results=results,
            line_outcomes=line_outcomes,
            flags=["OON"] if oon else [],
        )

    def _diagnoses(
        self, planned: list[PlannedLine]
    ) -> tuple[list[str], list[list[str]], dict[str, tuple[str, ...]]]:
        diagnoses: list[str] = []
        pointers: list[list[str]] = []
        chosen: dict[str, tuple[str, ...]] = {}
        for line in planned:
            if line.unrelated:
                codes: tuple[str, ...] = (line.unrelated[0],)
            elif line.profile:
                key = line.profile.key
                if key not in chosen:
                    overrides = [
                        self.t.criteria[c].diagnoses_when_not_met
                        for c, s in line.states.items()
                        if s == "not_met" and self.t.criteria[c].diagnoses_when_not_met
                    ]
                    if overrides:
                        chosen[key] = (self.rng.choice(overrides[0]),)
                    else:
                        chosen[key] = self.rng.choice(profile_diagnosis_sets(line.profile))
                codes = chosen[key]
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
        return diagnoses, pointers, chosen

    def _notes(self, planned: list[PlannedLine]) -> tuple[str, dict[tuple[str, str], str]]:
        rng, ts, t = self.rng, self.template_set, self.t
        sentences: list[str] = []
        evidence: dict[tuple[str, str], str] = {}
        done: set[str] = set()
        slots_by_profile: dict[str, dict[str, str]] = {}
        for line in planned:
            if line.unrelated and line.unrelated[0] not in done:
                text = line.unrelated[1][ts]
                sentences.append(text)
                done.add(line.unrelated[0])
                if line.profile:
                    evidence[(line.profile.key, "unrelated")] = text
            if not line.profile or line.unrelated or line.profile.key in done:
                continue
            profile = line.profile
            done.add(profile.key)
            slots = draw_slots(rng, profile.slots)
            slots["units"] = str(line.units)
            slots_by_profile[profile.key] = slots
            sentences.append(fill(rng.choice(profile.lead[ts]), slots))
            for criterion_id in profile.criteria:
                state = line.states[criterion_id]
                template = t.criteria[criterion_id]
                if state == "met":
                    text = fill(rng.choice(template.met[ts]), slots)
                elif state == "not_met" and ts in template.not_met:
                    text = fill(rng.choice(template.not_met[ts]), slots)
                else:
                    continue
                sentences.append(text)
                evidence[(profile.key, criterion_id)] = text
            for criterion_id in profile.criteria:  # criteria that fail together share the evidence
                template = t.criteria[criterion_id]
                if (
                    line.states[criterion_id] == "not_met"
                    and (profile.key, criterion_id) not in evidence
                ):
                    trigger = next(
                        c
                        for c in profile.criteria
                        if criterion_id in t.criteria[c].with_not_met
                        and line.states[c] == "not_met"
                    )
                    evidence[(profile.key, criterion_id)] = evidence[(profile.key, trigger)]
        for line in planned:
            if line.bypass == "met" and line.profile:
                kind = "wound" if line.profile.policy_id == "POL-WOUND-001" else "colon"
                slots = dict(slots_by_profile.get(line.profile.key, {}))
                segments = rng.sample(COLON_SEGMENTS, 2)
                slots.update(
                    {"size": str(rng.randint(6, 15)), "seg1": segments[0], "seg2": segments[1]}
                )
                slots.setdefault("site2", "left lower leg")
                text = fill(t.distinct[kind]["met"][ts], slots)
                sentences.append(text)
                evidence[(line.profile.key, "distinct")] = text
        if any(line.profile is None for line in planned):
            sentences.append(rng.choice(t.office_visit[ts]))
        procedures = [
            self.cur.descriptions[line.code]
            for line in planned
            if line.profile and not line.expect_rule_denial
        ]
        if procedures:
            listed = "; ".join(p[0].lower() + p[1:] for p in dict.fromkeys(procedures))
            sentences.append(t.plan_line[ts].format(procedure=listed))
        for filler in rng.sample(t.filler[ts], rng.randint(1, 2)):
            sentences.insert(rng.randint(1, len(sentences)), filler)
        notes = " ".join(sentences)
        if LEAKAGE.search(notes):
            raise AssertionError(f"leakage word in notes: {notes}")
        return notes, evidence

    def _authorizations(
        self,
        member: dict[str, Any],
        provider: dict[str, Any],
        planned: list[PlannedLine],
        days: list[date],
        plan_id: str,
    ) -> list[dict[str, Any]]:
        auths = []
        for line, day in zip(planned, days, strict=True):
            if not self.cur.auth_required(plan_id, line.code):
                continue
            self.auth_counter += 1
            start = day - timedelta(days=self.rng.randint(3, 20))
            auths.append(
                {
                    "auth_number": f"AUTH-S{self.seed % 100000:05d}-{self.auth_counter:05d}",
                    "member_id": member["member_id"],
                    "provider_npi": provider["npi"],
                    "procedure_code": line.code,
                    "start_date": start,
                    "end_date": start + timedelta(days=90),
                    "units_approved": None,
                }
            )
        return auths

    def _retrieve(self, line: PlannedLine, claim_policies: list[str]) -> list[RetrievedCriterion]:
        rng = self.rng
        relevant = list(line.profile.criteria) if line.profile else []
        own = (
            {c.criterion_id for c in self.cur.policies[line.profile.policy_id].criteria}
            if line.profile
            else set()
        )
        picks: list[str] = []
        if not line.profile and claim_policies and rng.random() < 0.7:
            near = [c.criterion_id for p in claim_policies for c in self.cur.policies[p].criteria]
            picks = rng.sample(near, min(2, len(near)))
        pool = [c for c in self.distractor_ids if c not in own and c not in picks]
        chosen = relevant + picks + rng.sample(pool, RAG_TOP_K - len(relevant) - len(picks))
        if relevant and len(chosen) > len(relevant) and rng.random() < 0.3:
            item = chosen.pop()
            chosen.insert(rng.randint(0, len(chosen)), item)
        criteria = self.cur.criteria()
        result = []
        for criterion_id in chosen:
            policy = self.cur.policies[criterion_id.split(".")[0]]
            result.append(
                RetrievedCriterion(
                    criterion_id=criterion_id,
                    policy_id=policy.policy_id,
                    policy_title=policy.title,
                    text=criteria[criterion_id].text,
                    source=criteria[criterion_id].source,
                    effective_date=policy.effective_date,
                )
            )
        return result

    def _context(
        self,
        claim: IntakeClaim,
        rules: RulesOutcome,
        planned: list[PlannedLine],
        provider: dict[str, Any],
        member: dict[str, Any],
        plan_id: str,
        network: Network,
    ) -> ContextPackage:
        primary_care = self.cur.provider_types[provider["provider_type"]]
        claim_policies = sorted({line.profile.policy_id for line in planned if line.profile})
        lines = []
        for outcome, line in zip(rules.line_outcomes, planned, strict=True):
            if outcome.outcome != "PASS":
                continue
            categories = list(self.cur.scope[line.code].candidate_categories)
            if line.profile is None:  # office visits: category follows the provider type (§8.4)
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
            lines.append(
                LineContext(
                    line_no=outcome.line_no,
                    procedure_code=line.code,
                    candidate_benefits=facts,
                    criteria=self._retrieve(line, claim_policies),
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

    def _target(
        self,
        planned: list[PlannedLine],
        rules: RulesOutcome,
        context: ContextPackage,
        evidence: dict[tuple[str, str], str],
        oon: bool,
    ) -> SLMOutput:
        by_line = {c.line_no: c for c in context.lines}
        slm_lines = []
        for outcome, line in zip(rules.line_outcomes, planned, strict=True):
            if outcome.outcome != "PASS":
                continue
            line_context = by_line[outcome.line_no]
            category = self._category(line, line_context)
            if line.profile is None:
                slm_lines.append(
                    SLMLine(
                        line_no=outcome.line_no,
                        decision=LineDecision.APPROVE,
                        benefit_category=category,
                        criteria=[],
                        reasons=[],
                        missing_information=[],
                    )
                )
                continue
            profile = line.profile
            results = []
            for retrieved in line_context.criteria:
                criterion_id = retrieved.criterion_id
                if criterion_id not in profile.criteria:
                    continue
                if line.unrelated:
                    first = next(
                        c.criterion_id
                        for c in line_context.criteria
                        if c.criterion_id in profile.criteria
                    )
                    text = (
                        evidence[(profile.key, "unrelated")]
                        if criterion_id == first
                        else NOT_DOCUMENTED
                    )
                    results.append(
                        CriterionResult(criterion_id=criterion_id, met=False, evidence=text)
                    )
                    continue
                state = line.states[criterion_id]
                text = evidence.get((profile.key, criterion_id), NOT_DOCUMENTED)
                results.append(
                    CriterionResult(criterion_id=criterion_id, met=state == "met", evidence=text)
                )
            kinds = {c: self.t.criteria[c].kind for c in profile.criteria}
            missing = [
                self.t.criteria[c].missing for c in profile.criteria if line.states[c] == "missing"
            ]
            if "NCCI_BYPASS" in outcome.flags and line.bypass == "missing":
                kind = "wound" if profile.policy_id == "POL-WOUND-001" else "colon"
                missing.append(self.t.distinct[kind]["missing"])
            if any(s == "not_met" and kinds[c] == "exclusion" for c, s in line.states.items()):
                decision, reasons, missing = LineDecision.DENY, ["DN_CONDITIONAL_EXCLUSION"], []
            elif line.unrelated or any(s == "not_met" for s in line.states.values()):
                decision, reasons, missing = LineDecision.DENY, ["DN_NOT_MEDICALLY_NECESSARY"], []
            elif missing:
                decision, reasons = LineDecision.PEND, ["PD_MISSING_DOCUMENTATION"]
            else:
                decision, reasons = LineDecision.APPROVE, []
            slm_lines.append(
                SLMLine(
                    line_no=outcome.line_no,
                    decision=decision,
                    benefit_category=category,
                    criteria=results,
                    reasons=reasons,
                    missing_information=missing,
                )
            )
        return SLMOutput(lines=slm_lines, complexity=self._complexity(slm_lines, rules, oon))

    @staticmethod
    def _category(line: PlannedLine, line_context: LineContext) -> str:
        categories = [fact.benefit_category for fact in line_context.candidate_benefits]
        if "ENDOSCOPY" in categories:  # colonoscopy lines here are diagnostic or surveillance
            return "ENDOSCOPY"
        return categories[0]

    @staticmethod
    def _complexity(slm_lines: list[SLMLine], rules: RulesOutcome, oon: bool) -> Complexity:
        decisions = {line.decision.value for line in slm_lines}
        decisions |= {"DENY" for o in rules.line_outcomes if o.outcome == "DENY"}
        with_criteria = sum(1 for line in slm_lines if line.criteria)
        bypass = any("NCCI_BYPASS" in o.flags for o in rules.line_outcomes)
        exclusion = any("DN_CONDITIONAL_EXCLUSION" in line.reasons for line in slm_lines)
        if bypass or exclusion or len(decisions) > 1 or with_criteria >= 3:
            return Complexity.HIGH
        if decisions & {"PEND", "DENY"} or oon or with_criteria == 2:
            return Complexity.MEDIUM
        return Complexity.LOW
