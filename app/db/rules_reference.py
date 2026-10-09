"""The rules engine's reference (`app.rules.reference.RulesReference`), two ways.

- File-backed (`build_reference`, P2.3a): from the curated files, the public files in `data/raw/`
  and reference records given as dicts in the shape of `data/generated/reference/*.jsonl`. NCCI
  edits and MUE limits are read for the in-scope procedure codes only, as the generator's rule
  mirror reads them (training/generate/codebook.py). Used by the golden and parity tests.
- Database-backed (`reference_for_claim`, P2.1): what one claim touches, from the tables the seed
  loads (NCCI and MUE in full). The pipeline uses it; the rules stay pure functions.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from functools import cache
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import raw
from app.db.curated import CuratedData, billing_articles, em_codes, load_curated
from app.db.models import (
    ArticleIcd10Covered,
    Authorization,
    Benefit,
    Claim,
    Icd10Code,
    Member,
    MueLimit,
    NcciPtpEdit,
    PlaceOfServiceCode,
    Plan,
    PlanExclusion,
    PlanReferralRule,
    ProcedureCode,
    Provider,
    ProviderNetwork,
)
from app.rules.reference import (
    AuthorizationRef,
    CodeRoleRef,
    DiagnosisSupportRef,
    ExistingClaimLine,
    MemberRef,
    NcciEdit,
    PlanRef,
    ProviderRef,
    PtpModifierRef,
    RulesReference,
)


@dataclass(frozen=True)
class CodeTables:
    icd10_codes: Mapping[int, frozenset[str]]
    procedure_codes: frozenset[str]
    place_of_service_codes: frozenset[str]
    ncci: Mapping[tuple[str, str], tuple[NcciEdit, ...]]
    mue: Mapping[str, int]
    article_covered: Mapping[str, Mapping[int, frozenset[str]]]  # article -> group -> codes
    global_days: Mapping[str, str]  # PFS global days


@cache
def load_code_tables(codes: frozenset[str]) -> CodeTables:
    """The code tables from `data/raw/` (slow: the NCCI table has 2.6 million rows): ICD-10-CM,
    the procedure code table and places of service in full; NCCI edits between `codes`, and their
    MUE limits and PFS global days. Pass every code the evaluated claims bill (with the rules' own
    codes, `rule_codes`), so the tables equal what the database reference reads per claim
    (D-CI-5)."""
    ncci: dict[tuple[str, str], list[NcciEdit]] = {}
    for pair in raw.read_ncci_pairs(set(codes)):
        ncci.setdefault((pair.column1, pair.column2), []).append(
            NcciEdit(
                column1=pair.column1,
                column2=pair.column2,
                effective_date=pair.effective_date,
                deletion_date=pair.deletion_date,
                modifier_indicator=pair.modifier_indicator,
            )
        )
    return CodeTables(
        icd10_codes={raw.ICD10_FISCAL_YEAR: frozenset(raw.read_icd10_codes())},
        procedure_codes=raw.read_procedure_code_table(),
        place_of_service_codes=frozenset(raw.read_place_of_service_codes()),
        ncci={key: tuple(edits) for key, edits in ncci.items()},
        mue={code: entry.max_units for code, entry in raw.read_mue(set(codes)).items()},
        article_covered={
            article: dict(found.covered)
            for article, found in raw.read_article_diagnoses(
                billing_articles(load_curated())
            ).items()
        },
        global_days=raw.read_pfs_global_days(set(codes)),
    )


def rule_refs(
    curated: CuratedData,
) -> tuple[dict[str, DiagnosisSupportRef], dict[str, CodeRoleRef], dict[str, frozenset[str]]]:
    """The curated part of the rules v2 reference: R15's diagnosis support, the code roles and the
    diagnosis sets."""
    support = {
        code: DiagnosisSupportRef(
            billing_article=s.billing_article,
            alternatives=s.rule_alternatives,
            first_group=s.rule_first_group,
            group_modifiers=dict(s.rule_group_modifiers),
        )
        for code, s in curated.diagnosis_support.items()
    }
    roles = {
        code: CodeRoleRef(r.role, r.spinal_region, r.primary_code, r.minutes_per_unit)
        for code, r in curated.code_roles.items()
    }
    return support, roles, dict(curated.diagnosis_sets)


def ptp_refs(curated: CuratedData) -> tuple[dict[str, PtpModifierRef], frozenset[str]]:
    """R11's NCCI PTP-associated modifiers and the E&M codes (D-RULE-8)."""
    modifiers = {
        name: PtpModifierRef(m.group, m.placement, m.paired_global_days)
        for name, m in curated.ptp_modifiers.items()
    }
    return modifiers, em_codes(curated)


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def plan_refs(curated: CuratedData) -> dict[str, PlanRef]:
    return {
        plan_id: PlanRef(
            plan_id=plan_id,
            filing_window_inn_days=plan.filing_window_inn_days,
            filing_window_oon_days=plan.filing_window_oon_days,
            oon_covered=plan.oon_covered,
            referral_provider_types=plan.referral_required_provider_types,
            auth_required_codes=frozenset(
                code for code in curated.scope if curated.auth_required(plan_id, code)
            ),
            excluded_codes=curated.excluded_codes(plan_id),
        )
        for plan_id, plan in curated.plans.items()
    }


def build_reference(
    curated: CuratedData,
    codes: CodeTables,
    members: Iterable[Mapping[str, Any]],
    providers: Iterable[Mapping[str, Any]],
    provider_networks: Iterable[Mapping[str, Any]],
    authorizations: Iterable[Mapping[str, Any]] = (),
    existing_claims: Iterable[Mapping[str, Any]] = (),
) -> RulesReference:
    """`existing_claims` holds one dict per claim line on file: claim_id, member_id, billing_npi,
    date_of_service, procedure_code, status."""
    support, roles, diagnosis_sets = rule_refs(curated)
    ptp_modifiers, em = ptp_refs(curated)
    return RulesReference(
        members={
            m["member_id"]: MemberRef(
                m["member_id"],
                m["plan_id"],
                date.fromisoformat(m["coverage_start"]),
                _day(m["coverage_end"]),
            )
            for m in members
        },
        providers={
            p["npi"]: ProviderRef(p["npi"], p["provider_type"], p["enrollment_status"])
            for p in providers
        },
        networks={(n["npi"], n["plan_id"]): n["in_network"] for n in provider_networks},
        plans=plan_refs(curated),
        authorizations=tuple(
            AuthorizationRef(
                auth_number=a["auth_number"],
                member_id=a["member_id"],
                provider_npi=a["provider_npi"],
                procedure_code=a["procedure_code"],
                start_date=date.fromisoformat(a["start_date"]),
                end_date=date.fromisoformat(a["end_date"]),
            )
            for a in authorizations
        ),
        existing_claims=tuple(
            ExistingClaimLine(
                claim_id=c["claim_id"],
                member_id=c["member_id"],
                billing_npi=c["billing_npi"],
                date_of_service=date.fromisoformat(c["date_of_service"]),
                procedure_code=c["procedure_code"],
                status=c["status"],
            )
            for c in existing_claims
        ),
        icd10_codes=codes.icd10_codes,
        procedure_codes=codes.procedure_codes,
        place_of_service_codes=codes.place_of_service_codes,
        ncci=codes.ncci,
        mue=codes.mue,
        bypass_modifiers=curated.bypass_modifiers,
        diagnosis_support=support,
        article_covered=codes.article_covered,
        code_roles=roles,
        diagnosis_sets=diagnosis_sets,
        ptp_modifiers=ptp_modifiers,
        em_codes=em,
        global_days=codes.global_days,
    )


# --- Database-backed (P2.1) ----------------------------------------------------------------------


def _strings(values: Iterable[Any]) -> set[str]:
    return {value for value in values if isinstance(value, str)}


def _claim_keys(claim: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], set[str], set[str]]:
    """The claim's service lines (as received, possibly invalid), procedure codes and NPIs."""
    lines = [line for line in claim.get("service_lines") or [] if isinstance(line, Mapping)]
    codes = _strings(line.get("procedure_code") for line in lines)
    npis = _strings([claim.get("billing_npi"), *(line.get("rendering_npi") for line in lines)])
    return lines, codes, npis


def plan_refs_from_db(session: Session, curated: CuratedData) -> dict[str, PlanRef]:
    """Every plan's rule terms from the database; a code needs authorization when the benefit of
    its first candidate category does (as CuratedData.auth_required reads the curated files)."""
    referral: dict[str, set[str]] = defaultdict(set)
    for plan_id, provider_type in session.execute(
        select(PlanReferralRule.plan_id, PlanReferralRule.provider_type)
    ):
        referral[plan_id].add(provider_type)
    excluded: dict[str, set[str]] = defaultdict(set)
    for plan_id, code in session.execute(
        select(PlanExclusion.plan_id, PlanExclusion.procedure_code)
    ):
        excluded[plan_id].add(code)
    auth = {
        (plan_id, category): required
        for plan_id, category, required in session.execute(
            select(Benefit.plan_id, Benefit.benefit_category, Benefit.auth_required)
        )
    }
    return {
        plan.plan_id: PlanRef(
            plan_id=plan.plan_id,
            filing_window_inn_days=plan.filing_window_inn_days,
            filing_window_oon_days=plan.filing_window_oon_days,
            oon_covered=plan.oon_covered,
            referral_provider_types=frozenset(referral[plan.plan_id]),
            auth_required_codes=frozenset(
                code
                for code, entry in curated.scope.items()
                if auth.get((plan.plan_id, entry.candidate_categories[0]), False)
            ),
            excluded_codes=frozenset(excluded[plan.plan_id]),
        )
        for plan in session.scalars(select(Plan))
    }


def _existing_lines(session: Session, member_id: str | None) -> tuple[ExistingClaimLine, ...]:
    """Every line of the member's claims on file, as stored at intake. The duplicate check skips
    the claim itself and rejected claims (A-R6)."""
    if member_id is None:
        return ()
    found = []
    claims = select(Claim).where(Claim.member_id == member_id).order_by(Claim.claim_id)
    for row in session.scalars(claims):
        billing = row.intake.get("billing_npi")
        for line in row.intake.get("service_lines") or []:
            if not isinstance(line, Mapping):
                continue
            day, code = line.get("date_of_service"), line.get("procedure_code")
            if isinstance(billing, str) and isinstance(day, str) and isinstance(code, str):
                found.append(
                    ExistingClaimLine(
                        claim_id=row.claim_id,
                        member_id=member_id,
                        billing_npi=billing,
                        date_of_service=date.fromisoformat(day),
                        procedure_code=code,
                        status=row.status,
                    )
                )
    return tuple(found)


def reference_for_claim(
    session: Session, claim: Mapping[str, Any], curated: CuratedData | None = None
) -> RulesReference:
    """What the rules need for one claim (as received, possibly invalid), from the database: its
    member, providers and their network rows, every plan's terms, the member's authorizations
    and claims on file, code-table membership of its codes, NCCI edits for every pair of its
    procedure codes in published order (source_order: the first edit active on a date applies),
    and MUE limits for its codes. A fiscal year without ICD-10-CM codes loaded is left out, so the
    rules raise MissingReference for it."""
    curated = curated or load_curated()
    lines, codes, npis = _claim_keys(claim)
    member_id = claim.get("member_id") if isinstance(claim.get("member_id"), str) else None
    diagnoses = {
        value.replace(".", "").strip().upper() for value in _strings(claim.get("diagnoses") or [])
    }
    places = _strings(line.get("place_of_service") for line in lines)

    members = {
        m.member_id: MemberRef(m.member_id, m.plan_id, m.coverage_start, m.coverage_end)
        for m in session.scalars(select(Member).where(Member.member_id == member_id))
    }
    ncci: dict[tuple[str, str], list[NcciEdit]] = defaultdict(list)
    for edit in session.scalars(
        select(NcciPtpEdit)
        .where(NcciPtpEdit.column1_code.in_(codes), NcciPtpEdit.column2_code.in_(codes))
        .order_by(NcciPtpEdit.source_order)
    ):
        ncci[(edit.column1_code, edit.column2_code)].append(
            NcciEdit(
                column1=edit.column1_code,
                column2=edit.column2_code,
                effective_date=edit.effective_date,
                deletion_date=edit.deletion_date,
                modifier_indicator=edit.modifier_indicator,
            )
        )
    latest_mue = (
        select(MueLimit.procedure_code, func.max(MueLimit.effective_date).label("effective"))
        .where(MueLimit.procedure_code.in_(codes))
        .group_by(MueLimit.procedure_code)
        .subquery()
    )
    years = session.scalars(select(Icd10Code.fiscal_year).distinct()).all()
    support, roles, diagnosis_sets = rule_refs(curated)
    ptp_modifiers, em = ptp_refs(curated)
    articles = {support[code].billing_article for code in codes if code in support}
    covered: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in session.scalars(
        select(ArticleIcd10Covered).where(
            ArticleIcd10Covered.article_id.in_(articles),
            ArticleIcd10Covered.icd10_code.in_(diagnoses),
        )
    ):
        covered[row.article_id][row.covered_group].add(row.icd10_code)
    return RulesReference(
        members=members,
        providers={
            p.npi: ProviderRef(p.npi, p.provider_type, p.enrollment_status)
            for p in session.scalars(select(Provider).where(Provider.npi.in_(npis)))
        },
        networks={
            (n.npi, n.plan_id): n.in_network
            for n in session.scalars(select(ProviderNetwork).where(ProviderNetwork.npi.in_(npis)))
        },
        plans=plan_refs_from_db(session, curated),
        authorizations=tuple(
            AuthorizationRef(
                auth_number=a.auth_number,
                member_id=a.member_id,
                provider_npi=a.provider_npi,
                procedure_code=a.procedure_code,
                start_date=a.start_date,
                end_date=a.end_date,
            )
            for a in session.scalars(
                select(Authorization)
                .where(Authorization.member_id == member_id)
                .order_by(Authorization.auth_number)
            )
        ),
        existing_claims=_existing_lines(session, member_id),
        icd10_codes={
            year: frozenset(
                session.scalars(
                    select(Icd10Code.code).where(
                        Icd10Code.fiscal_year == year, Icd10Code.code.in_(diagnoses)
                    )
                )
            )
            for year in years
        },
        procedure_codes=frozenset(
            session.scalars(select(ProcedureCode.code).where(ProcedureCode.code.in_(codes)))
        ),
        place_of_service_codes=frozenset(
            session.scalars(
                select(PlaceOfServiceCode.code).where(PlaceOfServiceCode.code.in_(places))
            )
        ),
        ncci={pair: tuple(edits) for pair, edits in ncci.items()},
        mue=dict(
            session.execute(
                select(MueLimit.procedure_code, MueLimit.max_units).join(
                    latest_mue,
                    (MueLimit.procedure_code == latest_mue.c.procedure_code)
                    & (MueLimit.effective_date == latest_mue.c.effective),
                )
            ).all()
        ),
        bypass_modifiers=curated.bypass_modifiers,
        diagnosis_support=support,
        article_covered={
            article: {group: frozenset(found) for group, found in groups.items()}
            for article, groups in covered.items()
        },
        code_roles=roles,
        diagnosis_sets=diagnosis_sets,
        ptp_modifiers=ptp_modifiers,
        em_codes=em,
        global_days={
            code: days
            for code, days in session.execute(
                select(ProcedureCode.code, ProcedureCode.global_days).where(
                    ProcedureCode.code.in_(codes), ProcedureCode.global_days.is_not(None)
                )
            ).all()
        },
    )
