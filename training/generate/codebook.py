"""Everything the scenario generators need from `data/curated/` and `data/raw/`, in one object.

`line_rule_outcomes` mirrors the Group C rules (R11–R13) as the golden cases define them
(tests/golden/README.md, A-R3/A-R4) so generated claims carry realistic line outcomes. The rules
engine (P2.3) is the authority; its results should be compared with these once it exists.
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from app.calculator.fee_schedule import allowed_amounts
from app.db import raw
from app.db.curated import CuratedData, load_curated


@dataclass(frozen=True)
class LineRuleResult:
    outcome: str  # PASS | DENY
    reason_codes: tuple[str, ...]
    flags: tuple[str, ...]


@dataclass(frozen=True)
class Codebook:
    curated: CuratedData
    icd10: dict[str, str]
    articles: dict[str, raw.ArticleDiagnoses]
    ncci: dict[tuple[str, str], tuple[raw.NcciPair, ...]]  # (column 1, column 2) -> edits
    mue: dict[str, raw.MueEntry]
    fees: dict[str, tuple[int, int]]  # code -> (in-network, out-of-network) allowed cents per unit
    place_of_service: dict[str, str]

    def groups_containing(self, procedure_code: str, diagnosis: str) -> set[int]:
        support = self.curated.diagnosis_support[procedure_code]
        article = self.articles[support.billing_article]
        return {group for group, codes in article.covered.items() if diagnosis in codes}

    def supported(self, procedure_code: str, diagnoses: list[str]) -> bool:
        """True when the diagnoses satisfy one of the code's supporting group combinations."""
        support = self.curated.diagnosis_support.get(procedure_code)
        if support is None:
            return True  # office visits: no billing article limits
        found = set().union(*(self.groups_containing(procedure_code, d) for d in diagnoses))
        return any(set(combination) <= found for combination in support.alternatives)

    def noncovered(self, procedure_code: str) -> frozenset[str]:
        support = self.curated.diagnosis_support.get(procedure_code)
        return self.articles[support.billing_article].noncovered if support else frozenset()

    def ncci_indicator(self, column1: str, column2: str, day: date) -> str | None:
        for pair in self.ncci.get((column1, column2), ()):
            if pair.active_on(day):
                return pair.modifier_indicator
        return None

    def line_rule_outcomes(
        self, plan_id: str, lines: list[tuple[str, date, int, tuple[str, ...]]]
    ) -> list[LineRuleResult]:
        """Group C for (code, date of service, units, modifiers) lines, in claim order."""
        reasons: list[list[str]] = [[] for _ in lines]
        flags: list[list[str]] = [[] for _ in lines]
        bypass = self.curated.bypass_modifiers
        for i, (code_a, day_a, _, mods_a) in enumerate(lines):
            for j, (code_b, day_b, _, mods_b) in enumerate(lines):
                if i == j or day_a != day_b:
                    continue
                indicator = self.ncci_indicator(code_a, code_b, day_a)  # a = column 1, b = column 2
                if indicator is None or indicator == "9":
                    continue
                if indicator == "1" and bypass & set(mods_a + mods_b):
                    if "NCCI_BYPASS" not in flags[j]:
                        flags[j].append("NCCI_BYPASS")
                elif "DN_NCCI_BUNDLED" not in reasons[j]:
                    reasons[j].append("DN_NCCI_BUNDLED")
        for i, (code, day, _, _) in enumerate(lines):
            total = sum(u for c, d, u, _ in lines if c == code and d == day)
            if code in self.mue and total > self.mue[code].max_units:
                reasons[i].append("DN_MUE_EXCEEDED")
        excluded = self.curated.excluded_codes(plan_id)
        for i, (code, _, _, _) in enumerate(lines):
            if code in excluded:
                reasons[i].append("DN_EXCLUDED")
        return [
            LineRuleResult("DENY" if r else "PASS", tuple(r), tuple(f))
            for r, f in zip(reasons, flags, strict=True)
        ]


@lru_cache
def load_codebook() -> Codebook:
    if not raw.raw_available():
        raise RuntimeError("data/raw/ is required to generate claims (see SOURCES.md)")
    curated = load_curated()
    codes = set(curated.scope)
    pfs = raw.read_pfs(codes)
    fee = curated.fee_rule
    fees = {
        code: allowed_amounts(
            entry.nonfacility_total_rvu,
            fee.conversion_factor,
            fee.in_network_bps,
            fee.out_of_network_bps,
        )
        for code, entry in pfs.items()
    }
    ncci: dict[tuple[str, str], list[raw.NcciPair]] = {}
    for pair in raw.read_ncci_pairs(codes):
        ncci.setdefault((pair.column1, pair.column2), []).append(pair)
    return Codebook(
        curated=curated,
        icd10=raw.read_icd10_codes(),
        articles=raw.read_article_diagnoses({p.billing_article for p in curated.policies.values()}),
        ncci={key: tuple(pairs) for key, pairs in ncci.items()},
        mue=raw.read_mue(codes),
        fees=fees,
        place_of_service=raw.read_place_of_service_codes(),
    )
