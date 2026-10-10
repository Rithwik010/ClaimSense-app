"""Readers for the committed curated data in `data/curated/` (INSTRUCTIONS.md §9.2).

Pure file readers with no database access. The seed loaders (P2.1) insert what these return and the
synthetic generators (`training/generate/`) read the same values, so both always agree.
`validate_curated` lists every consistency problem; the test suite requires it to return none.
"""

import csv
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CURATED_DIR = Path(__file__).resolve().parents[2] / "data" / "curated"

CRITERION_HEADING = re.compile(r"^## (POL-[A-Z]+-[0-9]{3}\.c[0-9]+)\s*$", re.MULTILINE)

# Coverage policy sets (D-POL-2): v1 is frozen for model v1 and its dataset; the pipeline and the
# v2 data use v2. Each set is a folder of `POL-*.md` files under `coverage_policies/`.
POLICY_SETS = ("v1", "v2")
CRITERION_TYPES = ("requirement", "exclusion", "conditional")  # D-ESI-6, D-GEN-3
CRITERION_GROUPS = ("indication",)  # D-POL-3
# The criterion lines of a v2 file besides its text (D-POL-3); v1 files have only `Source:`.
CRITERION_FIELD = re.compile(r"^(Type|Applies to|Group|Source):\s*(.*)$")

# The line rules R14 to R20 (D-RULE-3): what a code is for them, and their diagnosis sets.
RULE_ROLES = (
    "ESI_INTERLAMINAR",
    "ESI_TRANSFORAMINAL",
    "ESI_TRANSFORAMINAL_ADDON",
    "FACET_INJECTION",
    "FACET_INJECTION_ADDON",
    "FACET_THIRD_LEVEL",
    "FACET_DENERVATION",
    "FACET_DENERVATION_ADDON",
    "HOME_SLEEP_TEST",
    "NERVE_CONDUCTION",
    "NEEDLE_EMG",
    "TESTING_TIME",
)
EXTENDING_ROLES = {  # role of a code that extends a primary procedure -> the primary's role
    "ESI_TRANSFORAMINAL_ADDON": "ESI_TRANSFORAMINAL",
    "FACET_INJECTION_ADDON": "FACET_INJECTION",
    "FACET_THIRD_LEVEL": "FACET_INJECTION",
    "FACET_DENERVATION_ADDON": "FACET_DENERVATION",
}
SPINAL_ROLES = {role for role in RULE_ROLES if role.startswith(("ESI_", "FACET_"))}
SPINAL_REGIONS = ("CERVICAL_THORACIC", "LUMBAR_SACRAL")
RULE_DIAGNOSIS_SETS = ("PARASOMNIA", "FACET_SYNOVIAL_CYST")

# R11's NCCI PTP-associated modifiers (D-RULE-8; 2026 NCCI Policy Manual, Chapter I section E).
PTP_GROUPS = ("ANATOMIC", "GLOBAL_SURGERY", "OTHER")
PTP_PLACEMENTS = ("NOT_EM", "EM_WITH_PROCEDURE", "PROCEDURE", "EITHER", "DIFFERENT_SITES")
GLOBAL_DAYS = ("000", "010", "090", "XXX", "YYY", "ZZZ", "MMM")  # PFS GLOB DAYS values


@dataclass(frozen=True)
class NetworkTerms:
    deductible_cents: int
    coinsurance_bps: int
    oop_max_cents: int


@dataclass(frozen=True)
class PlanConfig:
    plan_id: str
    name: str
    plan_type: str
    effective_date: date
    filing_window_inn_days: int
    filing_window_oon_days: int
    referral_required_provider_types: frozenset[str]
    in_network: NetworkTerms
    out_of_network: NetworkTerms | None

    @property
    def oon_covered(self) -> bool:
        return self.out_of_network is not None


@dataclass(frozen=True)
class BenefitConfig:
    plan_id: str
    benefit_category: str
    covered: bool
    auth_required: bool
    visit_limit: int | None
    cost_share_rule: str
    copay_cents: int | None


@dataclass(frozen=True)
class Exclusion:
    plan_id: str
    procedure_code: str
    reason: str


@dataclass(frozen=True)
class ScopeEntry:
    procedure_code: str
    code_system: str
    policy_id: str | None
    candidate_categories: tuple[str, ...]
    provider_types: tuple[str, ...]
    policy_split: str | None


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    text: str
    source: str
    # Policy set v2 only (D-POL-3): the type, the codes the criterion is shown on (empty: every
    # code of the policy) and its group.
    criterion_type: str | None = None
    applies_to: tuple[str, ...] = ()
    group: str | None = None


@dataclass(frozen=True)
class CoveragePolicy:
    policy_id: str
    title: str
    procedure_codes: tuple[str, ...]
    plan_ids: tuple[str, ...]
    effective_date: date
    sources: tuple[str, ...]
    billing_article: str
    split: str
    criteria: tuple[Criterion, ...]
    policy_set: str = "v1"
    replaces: dict[str, tuple[str, ...]] = field(default_factory=dict)  # v2: retired v1 ID -> IDs

    def criterion_codes(self, criterion: Criterion) -> tuple[str, ...]:
        """The codes a criterion is shown on: its `Applies to` codes, else the policy's."""
        return criterion.applies_to or self.procedure_codes


@dataclass(frozen=True)
class ReasonCodeEntry:
    internal_code: str
    outcome: str
    group_code: str
    carc: str
    rarc: str | None
    notes: str | None


@dataclass(frozen=True)
class FeeRule:
    source_file: str
    conversion_factor: Decimal
    rvu_column: str
    in_network_bps: int
    out_of_network_bps: int
    effective_date: date


@dataclass(frozen=True)
class DiagnosisSupport:
    """Which covered ICD-10-CM groups of the billing article support a procedure code.

    `alternatives` is a tuple of group combinations: a line is supported when, for at least one
    combination, each group in it has one of the line's diagnoses (`1|2+3` = group 1, or both
    group 2 and group 3)."""

    procedure_code: str
    billing_article: str
    alternatives: tuple[tuple[int, ...], ...]  # v1, as the generator and V1a read the article
    source: str
    # R15 (D-RULE-4) follows the article where the v1 sets differ: its own combinations; a group
    # that must hold the line's first diagnosis; groups that count only with given modifiers.
    rule_alternatives: tuple[tuple[int, ...], ...] = ()
    rule_first_group: int | None = None
    rule_group_modifiers: tuple[tuple[int, frozenset[str]], ...] = ()


@dataclass(frozen=True)
class CodeRole:
    """What a procedure code is for the line rules R14 to R20 (`rule_code_roles.csv`)."""

    procedure_code: str
    role: str  # RULE_ROLES
    spinal_region: str | None  # SPINAL_REGIONS, for ESI and facet codes
    primary_code: str | None  # an add-on or third-level code: the primary procedure it extends
    minutes_per_unit: int | None  # TESTING_TIME codes
    source: str


@dataclass(frozen=True)
class PtpModifier:
    """An NCCI PTP-associated modifier and where it bypasses an edit (`ncci_ptp_modifiers.csv`)."""

    modifier: str
    group: str  # PTP_GROUPS
    placement: str  # PTP_PLACEMENTS
    paired_global_days: frozenset[str]  # EM_WITH_PROCEDURE: the paired code's global periods
    source: str


@dataclass(frozen=True)
class CuratedData:
    provider_types: dict[str, bool]  # provider type -> primary care
    plans: dict[str, PlanConfig]
    categories: tuple[str, ...]
    benefits: dict[tuple[str, str], BenefitConfig]
    exclusions: tuple[Exclusion, ...]
    scope: dict[str, ScopeEntry]
    descriptions: dict[str, str]
    reason_codes: dict[str, ReasonCodeEntry]
    fee_rule: FeeRule
    policies: dict[str, CoveragePolicy]
    diagnosis_support: dict[str, DiagnosisSupport]
    bypass_modifiers: frozenset[str]
    code_roles: dict[str, CodeRole] = field(default_factory=dict)
    diagnosis_sets: dict[str, frozenset[str]] = field(default_factory=dict)
    ptp_modifiers: dict[str, PtpModifier] = field(default_factory=dict)
    policy_set: str = "v1"

    def benefit(self, plan_id: str, category: str) -> BenefitConfig:
        return self.benefits[(plan_id, category)]

    def excluded_codes(self, plan_id: str) -> frozenset[str]:
        return frozenset(e.procedure_code for e in self.exclusions if e.plan_id == plan_id)

    def policy_for_code(self, procedure_code: str) -> CoveragePolicy | None:
        entry = self.scope.get(procedure_code)
        return self.policies[entry.policy_id] if entry and entry.policy_id else None

    def auth_required(self, plan_id: str, procedure_code: str) -> bool:
        """Every candidate category of a code agrees on auth (checked by `validate_curated`)."""
        categories = self.scope[procedure_code].candidate_categories
        return self.benefit(plan_id, categories[0]).auth_required

    def criteria(self) -> dict[str, Criterion]:
        return {c.criterion_id: c for p in self.policies.values() for c in p.criteria}


def _read_yaml(name: str) -> Any:
    return yaml.safe_load((CURATED_DIR / name).read_text(encoding="utf-8"))


def _read_csv(name: str) -> list[dict[str, str]]:
    with (CURATED_DIR / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _terms(raw: dict[str, int] | None) -> NetworkTerms | None:
    return NetworkTerms(**raw) if raw else None


def parse_policy(text: str) -> CoveragePolicy:
    """Parse a coverage policy file: YAML front matter, then `## <criterion id>` sections with the
    criterion text and a `Source:` line, plus in policy set v2 the `Type:`, `Applies to:` and
    `Group:` lines (D-POL-3). The text joins the other lines, as for v1."""
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front)
    parts = CRITERION_HEADING.split(body)
    criteria = []
    for criterion_id, section in zip(parts[1::2], parts[2::2], strict=True):
        lines = [line.strip() for line in section.strip().splitlines() if line.strip()]
        fields: dict[str, str] = {}
        text_lines = []
        for line in lines:
            match = CRITERION_FIELD.match(line)
            if match and match.group(1) not in fields:
                fields[match.group(1)] = match.group(2).strip()
            else:
                text_lines.append(line)
        applies = fields.get("Applies to", "")
        criteria.append(
            Criterion(
                criterion_id,
                " ".join(text_lines),
                fields.get("Source", ""),
                criterion_type=fields.get("Type") or None,
                applies_to=tuple(c.strip() for c in applies.split(",") if c.strip()),
                group=fields.get("Group") or None,
            )
        )
    return CoveragePolicy(
        policy_id=meta["policy_id"],
        title=meta["title"],
        procedure_codes=tuple(str(code) for code in meta["procedure_codes"]),
        plan_ids=tuple(meta["plan_ids"]),
        effective_date=meta["effective_date"],
        sources=tuple(meta["sources"]),
        billing_article=meta["billing_article"],
        split=meta["split"],
        criteria=tuple(criteria),
        policy_set=meta.get("policy_set", "v1"),
        replaces={k: tuple(v) for k, v in (meta.get("replaces") or {}).items()},
    )


def policy_dir(policy_set: str) -> Path:
    if policy_set not in POLICY_SETS:
        raise ValueError(f"unknown policy set {policy_set!r}; expected one of {POLICY_SETS}")
    return CURATED_DIR / "coverage_policies" / policy_set


def load_policies(policy_set: str) -> dict[str, CoveragePolicy]:
    return {
        policy.policy_id: policy
        for policy in (
            parse_policy(path.read_text(encoding="utf-8"))
            for path in sorted(policy_dir(policy_set).glob("POL-*.md"))
        )
    }


def _parse_alternatives(value: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(g) for g in alt.split("+")) for alt in value.split("|"))


def _parse_group_modifiers(value: str) -> tuple[tuple[int, frozenset[str]], ...]:
    """`2:Q7 Q8 Q9`, groups separated by `;`."""
    pairs = (part.partition(":") for part in value.split(";") if part.strip())
    return tuple((int(group), frozenset(modifiers.split())) for group, _, modifiers in pairs)


def _code_role(row: dict[str, str]) -> CodeRole:
    return CodeRole(
        procedure_code=row["procedure_code"],
        role=row["role"],
        spinal_region=row["spinal_region"] or None,
        primary_code=row["primary_code"] or None,
        minutes_per_unit=int(row["minutes_per_unit"]) if row["minutes_per_unit"] else None,
        source=row["source"],
    )


def _diagnosis_sets(rows: list[dict[str, str]]) -> dict[str, frozenset[str]]:
    sets: dict[str, set[str]] = {}
    for row in rows:
        sets.setdefault(row["set_name"], set()).add(row["icd10_code"])
    return {name: frozenset(codes) for name, codes in sets.items()}


def load_curated(policy_set: str = "v1") -> CuratedData:
    """The curated data with the coverage policies of one policy set (D-POL-2). The default, v1,
    keeps model v1's tools unchanged; the pipeline passes its `POLICY_SET` (default v2). Cached
    per set."""
    return _load_curated(policy_set)


@lru_cache
def _load_curated(policy_set: str) -> CuratedData:
    plans_raw = _read_yaml("plans.yaml")
    plans = {
        p["plan_id"]: PlanConfig(
            plan_id=p["plan_id"],
            name=p["name"],
            plan_type=p["plan_type"],
            effective_date=p["effective_date"],
            filing_window_inn_days=p["filing_window_days"]["in_network"],
            filing_window_oon_days=p["filing_window_days"]["out_of_network"],
            referral_required_provider_types=frozenset(p["referral_required_provider_types"]),
            in_network=NetworkTerms(**p["in_network"]),
            out_of_network=_terms(p["out_of_network"]),
        )
        for p in plans_raw["plans"]
    }
    benefits_raw = _read_yaml("benefits.yaml")
    benefits = {
        (plan_id, category): BenefitConfig(
            plan_id=plan_id,
            benefit_category=category,
            covered=row["covered"],
            auth_required=row["auth_required"],
            visit_limit=row["visit_limit"],
            cost_share_rule=row["cost_share_rule"],
            copay_cents=row.get("copay_cents"),
        )
        for plan_id, rows in benefits_raw["benefits"].items()
        for category, row in rows.items()
    }
    exclusions = tuple(
        Exclusion(plan_id, str(row["procedure_code"]), row["reason"])
        for plan_id, rows in _read_yaml("exclusions.yaml")["exclusions"].items()
        for row in rows
    )
    scope = {
        row["procedure_code"]: ScopeEntry(
            procedure_code=row["procedure_code"],
            code_system=row["code_system"],
            policy_id=row["policy_id"] or None,
            candidate_categories=tuple(row["candidate_benefit_categories"].split(";")),
            provider_types=tuple(row["provider_types"].split(";")),
            policy_split=row["policy_split"] or None,
        )
        for row in _read_csv("procedure_scope.csv")
    }
    reason_codes = {
        row["internal_code"]: ReasonCodeEntry(
            internal_code=row["internal_code"],
            outcome=row["outcome"],
            group_code=row["group_code"],
            carc=row["carc"],
            rarc=row["rarc"] or None,
            notes=row["notes"] or None,
        )
        for row in _read_csv("reason_code_map.csv")
    }
    fee = _read_yaml("fee_schedule.yaml")
    policies = load_policies(policy_set)
    support = {
        row["procedure_code"]: DiagnosisSupport(
            procedure_code=row["procedure_code"],
            billing_article=row["billing_article"],
            alternatives=_parse_alternatives(row["supporting_groups"]),
            source=row["source"],
            rule_alternatives=_parse_alternatives(row["rule_groups"]),
            rule_first_group=int(row["rule_first_group"]) if row["rule_first_group"] else None,
            rule_group_modifiers=_parse_group_modifiers(row["rule_group_modifiers"]),
        )
        for row in _read_csv("diagnosis_support.csv")
    }
    return CuratedData(
        provider_types={p["provider_type"]: p["primary_care"] for p in plans_raw["provider_types"]},
        plans=plans,
        categories=tuple(benefits_raw["categories"]),
        benefits=benefits,
        exclusions=exclusions,
        scope=scope,
        descriptions={
            r["procedure_code"]: r["description"] for r in _read_csv("procedure_descriptions.csv")
        },
        reason_codes=reason_codes,
        fee_rule=FeeRule(
            source_file=fee["source_file"],
            conversion_factor=Decimal(fee["conversion_factor"]),
            rvu_column=fee["rvu_column"],
            in_network_bps=fee["in_network_bps"],
            out_of_network_bps=fee["out_of_network_bps"],
            effective_date=fee["effective_date"],
        ),
        policies=policies,
        diagnosis_support=support,
        bypass_modifiers=frozenset(r["modifier"] for r in _read_csv("ncci_bypass_modifiers.csv")),
        code_roles={r["procedure_code"]: _code_role(r) for r in _read_csv("rule_code_roles.csv")},
        diagnosis_sets=_diagnosis_sets(_read_csv("rule_diagnosis_sets.csv")),
        ptp_modifiers={
            r["modifier"]: PtpModifier(
                modifier=r["modifier"],
                group=r["group"],
                placement=r["placement"],
                paired_global_days=frozenset(r["paired_global_days"].split()),
                source=r["source"],
            )
            for r in _read_csv("ncci_ptp_modifiers.csv")
        },
        policy_set=policy_set,
    )


def em_codes(data: CuratedData) -> frozenset[str]:
    """The E&M codes R11's modifier placement reads (D-RULE-8): the in-scope office visit codes."""
    return frozenset(
        code
        for code, entry in data.scope.items()
        if any(category.startswith("OFFICE_VISIT") for category in entry.candidate_categories)
    )


def rule_codes(data: CuratedData) -> frozenset[str]:
    """The codes the rules know beyond the code table: the scope and the rules v2 code roles."""
    return frozenset(data.scope) | frozenset(data.code_roles)


def billing_articles(data: CuratedData) -> set[str]:
    """The billing articles R15 reads: those of the in-scope codes (diagnosis_support.csv)."""
    return {support.billing_article for support in data.diagnosis_support.values()}


def validate_curated(data: CuratedData) -> list[str]:
    """Cross-file consistency checks. Returns a list of problems (empty when consistent)."""
    problems: list[str] = []
    categories = set(data.categories)
    for plan_id in data.plans:
        missing = categories - {c for (p, c) in data.benefits if p == plan_id}
        if missing:
            problems.append(f"{plan_id}: no benefit row for {sorted(missing)}")
    for benefit in data.benefits.values():
        if benefit.plan_id not in data.plans:
            problems.append(f"benefit for unknown plan {benefit.plan_id}")
        if (benefit.cost_share_rule == "COPAY") != (benefit.copay_cents is not None):
            problems.append(f"{benefit.plan_id}/{benefit.benefit_category}: copay vs rule")
    for plan in data.plans.values():
        unknown = plan.referral_required_provider_types - set(data.provider_types)
        if unknown:
            problems.append(f"{plan.plan_id}: unknown referral provider types {sorted(unknown)}")
    for exclusion in data.exclusions:
        if exclusion.procedure_code not in data.scope:
            problems.append(f"exclusion {exclusion.procedure_code} is not an in-scope code")
    for code, entry in data.scope.items():
        if code not in data.descriptions:
            problems.append(f"{code}: no team-written description")
        if not set(entry.candidate_categories) <= categories:
            problems.append(f"{code}: unknown candidate categories")
        if not set(entry.provider_types) <= set(data.provider_types):
            problems.append(f"{code}: unknown provider types")
        for plan_id in data.plans:
            auth = {data.benefit(plan_id, c).auth_required for c in entry.candidate_categories}
            if len(auth) > 1:
                problems.append(f"{plan_id}/{code}: candidate categories disagree on auth")
        if entry.policy_id:
            policy = data.policies.get(entry.policy_id)
            if policy is None:
                problems.append(f"{code}: unknown policy {entry.policy_id}")
            elif code not in policy.procedure_codes or entry.policy_split != policy.split:
                problems.append(f"{code}: scope and {entry.policy_id} disagree")
            support = data.diagnosis_support.get(code)
            if support is None or (policy and support.billing_article != policy.billing_article):
                problems.append(f"{code}: missing or mismatched diagnosis support row")
    for policy in data.policies.values():
        if policy.policy_set != data.policy_set:
            problems.append(f"{policy.policy_id}: file says policy set {policy.policy_set}")
        problems += (
            _v2_criteria_problems(policy)
            if data.policy_set == "v2"
            else _v1_criteria_problems(policy)
        )
        for code in policy.procedure_codes:
            if data.scope.get(code) is None or data.scope[code].policy_id != policy.policy_id:
                problems.append(f"{policy.policy_id}: code {code} not mapped in procedure_scope")
    return problems + _rule_data_problems(data)


def _v1_criteria_problems(policy: CoveragePolicy) -> list[str]:
    problems = []
    for number, criterion in enumerate(policy.criteria, start=1):
        if criterion.criterion_id != f"{policy.policy_id}.c{number}":
            problems.append(f"{criterion.criterion_id}: IDs must run c1, c2, ...")
        if not criterion.source or not criterion.text:
            problems.append(f"{criterion.criterion_id}: missing text or source")
        if criterion.criterion_type or criterion.applies_to or criterion.group:
            problems.append(f"{criterion.criterion_id}: v1 criteria have no Type, Applies or Group")
    return problems


def _v2_criteria_problems(policy: CoveragePolicy) -> list[str]:
    """What the loader relies on in a v2 file (D-POL-1, D-POL-3). The ID history and the sources
    are checked by scripts/verify/policies_v2_sources.py."""
    problems = []
    numbers = [int(c.criterion_id.rsplit(".c", 1)[1]) for c in policy.criteria]
    if numbers != sorted(set(numbers)) or any(
        not c.criterion_id.startswith(f"{policy.policy_id}.c") for c in policy.criteria
    ):
        problems.append(f"{policy.policy_id}: criterion IDs must be the policy's, increasing")
    groups: dict[str, int] = {}
    for criterion in policy.criteria:
        name = criterion.criterion_id
        if not criterion.source or not criterion.text:
            problems.append(f"{name}: missing text or source")
        if criterion.criterion_type not in CRITERION_TYPES:
            problems.append(f"{name}: type {criterion.criterion_type!r} not in {CRITERION_TYPES}")
        if not set(criterion.applies_to) <= set(policy.procedure_codes):
            problems.append(f"{name}: applies to codes the policy does not cover")
        if criterion.group is not None:
            if criterion.group not in CRITERION_GROUPS:
                problems.append(f"{name}: unknown group {criterion.group!r}")
            if criterion.criterion_type != "conditional":
                problems.append(f"{name}: an indication-group member must be conditional")
            groups[criterion.group] = groups.get(criterion.group, 0) + 1
    problems += [
        f"{policy.policy_id}: group {g} has one member" for g, n in groups.items() if n < 2
    ]
    retired = {c.criterion_id for c in policy.criteria} & set(policy.replaces)
    if retired:
        problems.append(f"{policy.policy_id}: retired IDs still present {sorted(retired)}")
    return problems


def _rule_data_problems(data: CuratedData) -> list[str]:
    """The line rules' curated data (D-RULE-3, D-RULE-4)."""
    problems = []
    for code, support in data.diagnosis_support.items():
        groups = {g for alternative in support.rule_alternatives for g in alternative}
        if not support.rule_alternatives:
            problems.append(f"{code}: no rule_groups")
        if support.rule_first_group is not None and support.rule_first_group not in groups:
            problems.append(f"{code}: rule_first_group is in no rule_groups alternative")
        if not {g for g, _ in support.rule_group_modifiers} <= groups:
            problems.append(f"{code}: rule_group_modifiers names a group not in rule_groups")
    roles = data.code_roles
    for code, role in roles.items():
        if role.role not in RULE_ROLES:
            problems.append(f"{code}: unknown role {role.role}")
        if (role.spinal_region is not None) != (role.role in SPINAL_ROLES) or (
            role.spinal_region is not None and role.spinal_region not in SPINAL_REGIONS
        ):
            problems.append(f"{code}: spinal region does not fit role {role.role}")
        primary = roles.get(role.primary_code or "")
        if role.role in EXTENDING_ROLES:
            if primary is None or primary.role != EXTENDING_ROLES[role.role]:
                problems.append(f"{code}: primary code {role.primary_code} has the wrong role")
            elif primary.spinal_region != role.spinal_region:
                problems.append(f"{code}: primary code {role.primary_code} is in another region")
        elif role.primary_code is not None:
            problems.append(f"{code}: only add-on and third-level codes have a primary code")
        if (role.minutes_per_unit is not None) != (role.role == "TESTING_TIME") or (
            role.minutes_per_unit is not None and role.minutes_per_unit <= 0
        ):
            problems.append(f"{code}: minutes per unit do not fit role {role.role}")
    if set(data.diagnosis_sets) != set(RULE_DIAGNOSIS_SETS):
        problems.append(f"diagnosis sets {sorted(data.diagnosis_sets)} != {RULE_DIAGNOSIS_SETS}")
    for name, m in data.ptp_modifiers.items():
        if m.group not in PTP_GROUPS or m.placement not in PTP_PLACEMENTS:
            problems.append(f"modifier {name}: unknown group or placement")
        if (m.placement == "DIFFERENT_SITES") != (m.group == "ANATOMIC"):
            problems.append(f"modifier {name}: only anatomic modifiers need different sites")
        if not m.paired_global_days <= set(GLOBAL_DAYS) or (
            m.paired_global_days and m.placement != "EM_WITH_PROCEDURE"
        ):
            problems.append(f"modifier {name}: paired global days do not fit")
    if data.ptp_modifiers and not data.bypass_modifiers <= set(data.ptp_modifiers):
        problems.append("the v1 bypass modifiers are not all NCCI PTP-associated modifiers")
    return problems
