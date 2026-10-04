"""Task P2.4-G: four new calculator golden cases (D-GOLD-2), drafted for an independent check.

D-GOLD-2 lists the calculator situations the golden set lacks: a deductible split across two lines,
a second copay capped by the allowed amount, and a second COB case where the primary paid at least
the allowed amount; the task adds the out-of-pocket maximum reached partway through a multi-line
claim. This script drafts one case for each (C53-C56, the next free IDs):

- the expected amounts and worked steps follow INSTRUCTIONS.md section 8.6 and the confirmed
  assumptions A1-A9 (tests/golden/README.md), computed here with `decimal.Decimal` and
  ROUND_HALF_UP, independently of `app/calculator` (the code the cases will test, H12). The same
  computation reproduces every existing golden calculator case (tests/unit/test_new_calculator_
  cases.py);
- fees come from the PFS RVU file as D6 sets them (national = RVU x conversion factor; in network
  x 12500 bps, out of network x 10000 bps; each rounded half up).

Outputs, in data/generated/verification/ (not committed):
- new_golden/calculator_new_cases.json: the drafted cases, in the golden format. They go into
  tests/golden/calculator/ only after the independent check (H12, D-GOLD-2);
- G3_new_cases_sheet.md: the blind sheet: inputs and the quoted section 8.6 steps only, with blank
  amount cells, and the assumptions A1-A9 listed once.
It also prints the golden_checks invariants on the drafted cases (report only).

Accepted in G3 (2026-10-04, scripts/verify/g3_compare.py): a separate Claude chat's answers from
the sheet agreed on all 48 amounts, and C53-C56 are now in tests/golden/calculator/. Once they are
there the script stops instead of overwriting the filled sheet; the tests check that it still
drafts exactly those cases.

    uv run python -m scripts.verify.new_calculator_cases
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from scripts.verify.golden_checks import (
    INSTRUCTIONS_MD,
    MINUTES_PER_CALCULATOR_CASE,
    README_MD,
    blind_view,
    check_calculator_case,
    cob_total_differs,
    parse_instructions,
    readme_assumptions,
    render_calculator_case,
    situations,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "generated" / "verification"
STAGING = OUT_DIR / "new_golden"
CASES_FILE = STAGING / "calculator_new_cases.json"
SHEET_FILE = OUT_DIR / "G3_new_cases_sheet.md"
GOLDEN_CALCULATOR = ROOT / "tests" / "golden" / "calculator"
SOURCES = [
    "data/curated/plans.yaml",
    "data/curated/benefits.yaml",
    "data/curated/fee_schedule.yaml (D6)",
    "data/raw/pfs/rvu26a PPRRVU2026_Jan_nonQPP.csv",
]
LINE_FIELDS = (
    "billed_cents",
    "allowed_cents",
    "contractual_adjustment_cents",
    "deductible_cents",
    "copay_cents",
    "coinsurance_cents",
    "cob_primary_paid_cents",
    "plan_pays_cents",
    "member_pays_cents",
    "balance_bill_exposure_cents",
)
BASIS = Decimal(10000)


def half_up(value: Decimal) -> int:
    """Whole cents, ROUND_HALF_UP (section 8.6)."""
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _num(value: Decimal) -> str:
    return format(value, "f")


# --- the drafts ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class LineInput:
    line_no: int
    procedure_code: str
    units: int
    billed_cents: int
    decision: str
    benefit_category: str | None


@dataclass(frozen=True)
class Draft:
    case_id: str
    title: str
    assumptions: tuple[str, ...]
    plan_id: str
    network: str
    deductible_met_cents: int
    oop_met_cents: int
    lines: tuple[LineInput, ...]
    primary_paid: tuple[tuple[int, int], ...] = ()  # (line_no, paid cents); empty = no COB


PAYER = "Northwind Health Plan"
DRAFTS = (
    Draft(
        "C53",
        "Deductible split across two lines",
        (),
        "PLN-PPO-SILVER",
        "IN_NETWORK",
        120000,
        120000,
        (
            LineInput(1, "93306", 1, 41000, "APPROVE", "DIAGNOSTIC_TESTS"),
            LineInput(2, "70553", 1, 60000, "APPROVE", "ADVANCED_IMAGING"),
        ),
    ),
    Draft(
        "C54",
        "Copay capped by the allowed amount; billed and fee both below the copay",
        (),
        "PLN-EPO",
        "IN_NETWORK",
        30000,
        30000,
        (LineInput(1, "99211", 1, 2800, "APPROVE", "OFFICE_VISIT_SPECIALIST"),),
    ),
    Draft(
        "C55",
        "COB: primary paid more than the allowed amount on line 1; line 2 not paid by the primary",
        ("A6",),
        "PLN-HDHP",
        "IN_NETWORK",
        300000,
        300000,
        (
            LineInput(1, "93306", 1, 41000, "APPROVE", "DIAGNOSTIC_TESTS"),
            LineInput(2, "99214", 1, 27000, "APPROVE", "OFFICE_VISIT_SPECIALIST"),
        ),
        primary_paid=((1, 30000),),
    ),
    Draft(
        "C56",
        "Out-of-pocket maximum reached on line 2 of three",
        ("A1", "A4", "A5"),
        "PLN-HMO",
        "IN_NETWORK",
        15000,
        385000,
        (
            LineInput(1, "99214", 1, 27000, "APPROVE", "OFFICE_VISIT_SPECIALIST"),
            LineInput(2, "70553", 1, 60000, "APPROVE", "ADVANCED_IMAGING"),
            LineInput(3, "97110", 2, 12000, "APPROVE", "REHAB_THERAPY"),
        ),
    ),
)


# --- section 8.6 ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Fee:
    """A code's fee schedule entry with how D6 derives it, for the worked steps."""

    rvu: Decimal
    conversion_factor: Decimal
    national: int
    inn_allowed_cents: int
    oon_allowed_cents: int
    in_network_bps: int
    out_of_network_bps: int

    def derivation(self, code: str) -> str:
        product = self.rvu * self.conversion_factor
        inn_raw = Decimal(self.national) * self.in_network_bps / BASIS
        oon = (
            f"out-of-network {self.oon_allowed_cents}"
            if self.out_of_network_bps == BASIS
            else f"out-of-network {self.national} x {_num(self.out_of_network_bps / BASIS)} = "
            f"{Decimal(self.national) * self.out_of_network_bps / BASIS:.2f} -> "
            f"{self.oon_allowed_cents}"
        )
        return (
            f"fee {code}: RVU {_num(self.rvu)} x CF {_num(self.conversion_factor)} = "
            f"{_num(product)} -> national {self.national}; in-network {self.national} x "
            f"{_num(self.in_network_bps / BASIS)} = {inn_raw:.2f} -> {self.inn_allowed_cents}; "
            f"{oon}."
        )


def fee_from_rvu(rvu: Decimal, fee_rule: Any) -> Fee:
    """D6: national = RVU x conversion factor; network amounts = national x bps; half up each."""
    national = half_up(rvu * fee_rule.conversion_factor * 100)
    return Fee(
        rvu=rvu,
        conversion_factor=fee_rule.conversion_factor,
        national=national,
        inn_allowed_cents=half_up(Decimal(national) * fee_rule.in_network_bps / BASIS),
        oon_allowed_cents=half_up(Decimal(national) * fee_rule.out_of_network_bps / BASIS),
        in_network_bps=fee_rule.in_network_bps,
        out_of_network_bps=fee_rule.out_of_network_bps,
    )


@dataclass(frozen=True)
class Computed:
    lines: list[dict[str, int]]
    totals: dict[str, int]
    accumulators_after: dict[str, int]
    steps: list[str]


def compute(
    given: Mapping[str, Any], curated: Any, fees: Mapping[str, Fee] | None = None
) -> Computed:
    """Section 8.6 with A1-A9 on a case's `given`. `fees`, when given, adds how each fee is
    derived to the worked steps."""
    plan = curated.plans[given["plan_id"]]
    network = given["network"]
    in_network = network == "IN_NETWORK"
    terms = plan.in_network if in_network else plan.out_of_network
    before = given["accumulators"]
    remaining_deductible = max(0, terms.deductible_cents - before["deductible_met_cents"])
    remaining_oop = max(0, terms.oop_max_cents - before["oop_met_cents"])
    other = given.get("other_coverage")
    primary_paid = {p["line_no"]: p["paid_cents"] for p in (other or {}).get("primary_paid", [])}
    steps = [
        f"Plan {plan.plan_id}, {network}: deductible {terms.deductible_cents}, coinsurance "
        f"{terms.coinsurance_bps} bps, OOP max {terms.oop_max_cents}.",
        f"Accumulators before: deductible met {before['deductible_met_cents']} -> remaining "
        f"{remaining_deductible}; OOP met {before['oop_met_cents']} -> remaining {remaining_oop}.",
    ]
    rows: list[dict[str, int]] = []
    claim_deductible = claim_cost_share = 0
    for line in given["lines"]:
        n, code, units, billed = (
            line["line_no"],
            line["procedure_code"],
            line["units"],
            line["billed_cents"],
        )
        row = dict.fromkeys(LINE_FIELDS, 0)
        row["billed_cents"] = billed
        if line["decision"] != "APPROVE":
            rows.append({"line_no": n, **row})
            steps.append(
                f"Line {n} {code}: decision {line['decision']} -> plan pays 0, no cost share; "
                f"only billed {billed} reported (A7)."
            )
            continue
        fee = given["fee_schedule"][code][
            "inn_allowed_cents" if in_network else "oon_allowed_cents"
        ]
        fee_line = fee * units
        allowed = min(billed, fee_line)
        steps.append(
            f"Line {n} {code} x{units}: {fees[code].derivation(code)}"
            if fees
            else f"Line {n} {code} x{units}:"
        )
        steps.append(
            f"  fee for line = {fee} x {units} units = {fee_line} (A1); allowed = min(billed "
            f"{billed}, {fee_line}) = {allowed}."
        )
        contractual = billed - allowed if in_network else 0
        balance_bill = 0 if in_network else billed - allowed
        steps.append(
            f"  contractual adjustment = {contractual}; balance-bill exposure = "
            f"{balance_bill} (A9)."
        )
        category = line["benefit_category"]
        benefit = curated.benefit(plan.plan_id, category)
        deductible = copay = coinsurance = 0
        if in_network and benefit.cost_share_rule == "COPAY":
            copay = min(benefit.copay_cents, allowed)
            steps.append(
                f"  {category} COPAY {benefit.copay_cents}: copay = min({benefit.copay_cents}, "
                f"{allowed}) = {copay}; no deductible."
            )
        else:
            deductible = min(remaining_deductible, allowed)
            raw_coinsurance = Decimal(allowed - deductible) * terms.coinsurance_bps / BASIS
            coinsurance = half_up(raw_coinsurance)
            label = (
                f"{category} DEDUCTIBLE_COINSURANCE"
                if in_network
                else "out-of-network uses deductible and coinsurance (A3)"
            )
            steps.append(
                f"  {label}: deductible = min(remaining {remaining_deductible}, {allowed}) = "
                f"{deductible}; coinsurance = ({allowed} - {deductible}) x {terms.coinsurance_bps} "
                f"/ 10000 = {_num(raw_coinsurance)} -> {coinsurance}."
            )
        cost_share = deductible + copay + coinsurance
        if cost_share <= remaining_oop:
            steps.append(f"  OOP: cost share {cost_share} <= remaining {remaining_oop} -> no cap.")
        else:  # A4: fill deductible, then copay, then coinsurance up to the remaining maximum
            room = remaining_oop
            deductible, room = min(deductible, room), room - min(deductible, room)
            copay, room = min(copay, room), room - min(copay, room)
            coinsurance = min(coinsurance, room)
            cost_share = deductible + copay + coinsurance
            steps.append(
                f"  OOP cap: remaining {remaining_oop}; filled in order deductible, copay, "
                f"coinsurance (A4) -> deductible {deductible}, copay {copay}, coinsurance "
                f"{coinsurance}."
            )
        normal = allowed - cost_share
        primary = primary_paid.get(n, 0)
        if other and n in primary_paid:  # A6
            plan_pays = max(0, min(normal, allowed - primary))
            member_pays = max(0, allowed - primary - plan_pays)
            steps.append(
                f"  COB: primary paid {primary}; normal plan payment {allowed} - {cost_share} = "
                f"{normal}; plan pays = min({normal}, {allowed} - {primary}) = {plan_pays} (not "
                f"below 0); member pays = {allowed} - {primary} - {plan_pays} = {member_pays} (not "
                "below 0) (A6)."
            )
        else:
            plan_pays, member_pays = normal, cost_share
            steps.append(
                f"  plan pays = {allowed} - {cost_share} = {plan_pays}; member pays = {cost_share}."
            )
        remaining_deductible -= deductible
        remaining_oop -= cost_share  # A5: the whole cost share counts, whoever pays it (A6)
        claim_deductible += deductible
        claim_cost_share += cost_share
        steps.append(
            f"  working accumulators: deductible remaining {remaining_deductible}, OOP remaining "
            f"{remaining_oop}."
        )
        row.update(
            allowed_cents=allowed,
            contractual_adjustment_cents=contractual,
            deductible_cents=deductible,
            copay_cents=copay,
            coinsurance_cents=coinsurance,
            cob_primary_paid_cents=primary,
            plan_pays_cents=plan_pays,
            member_pays_cents=member_pays,
            balance_bill_exposure_cents=balance_bill,
        )
        rows.append({"line_no": n, **row})
    totals = {field: sum(row[field] for row in rows) for field in LINE_FIELDS}  # A8
    after = {
        "deductible_met_cents": before["deductible_met_cents"] + claim_deductible,
        "oop_met_cents": before["oop_met_cents"] + claim_cost_share,
    }
    steps.append(
        f"Totals: plan pays {totals['plan_pays_cents']}, member pays "
        f"{totals['member_pays_cents']}. Working accumulators after ({network}): deductible met "
        f"{after['deductible_met_cents']}, OOP met {after['oop_met_cents']} (A5)."
    )
    return Computed(rows, totals, after, steps)


# --- building the cases and the sheet ------------------------------------------------------------


def given_for(draft: Draft, fees: Mapping[str, Fee]) -> dict[str, Any]:
    codes = list(dict.fromkeys(line.procedure_code for line in draft.lines))
    return {
        "plan_id": draft.plan_id,
        "network": draft.network,
        "accumulators": {
            "deductible_met_cents": draft.deductible_met_cents,
            "oop_met_cents": draft.oop_met_cents,
        },
        "fee_schedule": {
            code: {
                "inn_allowed_cents": fees[code].inn_allowed_cents,
                "oon_allowed_cents": fees[code].oon_allowed_cents,
            }
            for code in codes
        },
        "lines": [
            {
                "line_no": line.line_no,
                "procedure_code": line.procedure_code,
                "units": line.units,
                "billed_cents": line.billed_cents,
                "decision": line.decision,
                "benefit_category": line.benefit_category,
            }
            for line in draft.lines
        ],
        "other_coverage": (
            {
                "payer_name": PAYER,
                "primary_paid": [
                    {"line_no": n, "paid_cents": paid} for n, paid in draft.primary_paid
                ],
            }
            if draft.primary_paid
            else None
        ),
    }


def build_case(draft: Draft, curated: Any, fees: Mapping[str, Fee]) -> dict[str, Any]:
    given = given_for(draft, fees)
    result = compute(given, curated, fees)
    return {
        "case_id": draft.case_id,
        "title": draft.title,
        "assumptions": list(draft.assumptions),
        "given": given,
        "expected": {
            "amounts": {"lines": result.lines, "totals": result.totals},
            "accumulators_after": result.accumulators_after,
        },
        "worked_steps": result.steps,
        "sources": SOURCES,
    }


def load_fees(codes: set[str], curated: Any) -> dict[str, Fee]:
    from app.db import raw

    pfs = raw.read_pfs(codes)
    return {code: fee_from_rvu(pfs[code].nonfacility_total_rvu, curated.fee_rule) for code in codes}


def build_sheet(cases: Sequence[Mapping[str, Any]], curated: Any) -> str:
    """The blind sheet: the inputs and the quoted section 8.6 steps only. No titles, expected
    values, worked steps or per-case assumption names; A1-A9 once at the top."""
    spec = parse_instructions(INSTRUCTIONS_MD.read_text(encoding="utf-8"))
    assumptions = [
        (key, text)
        for key, text in readme_assumptions(README_MD.read_text(encoding="utf-8"))
        if not key.startswith("A-R")
    ]
    lines = [
        "# New calculator golden cases: independent check (Task G3)",
        "",
        "For one reviewer, or a separate Claude chat that sees only this sheet (D-GOLD-2). Work "
        "out each case by hand from the inputs shown, using only the quoted INSTRUCTIONS.md text "
        "and the assumptions below, then fill in the blank cells. Amounts are in cents.",
        "",
        "**Do not open data/generated/verification/new_golden/ until every cell is filled.**",
        "",
        f"Estimated time: {MINUTES_PER_CALCULATOR_CASE * len(cases)} minutes ({len(cases)} "
        f"calculator cases x {MINUTES_PER_CALCULATOR_CASE} minutes).",
        "",
        "## Assumptions (tests/golden/README.md, word for word; they apply to every case)",
        "",
        "| ID | Assumption |",
        "|---|---|",
        *[f"| {key} | {text} |" for key, text in assumptions],
        "",
        f"## Calculator cases ({len(cases)})",
        "",
        "How the calculator works (INSTRUCTIONS.md section 8.6, word for word):",
        "",
        *[f"> {paragraph}\n" for paragraph in spec.calc_intro],
    ]
    for number, case in enumerate(cases, start=1):
        lines += render_calculator_case(
            number, blind_view(case), curated, spec, name_assumptions=False
        )
    return "\n".join(lines).rstrip("\n") + "\n"


def invariant_report(cases: Sequence[Mapping[str, Any]], curated: Any) -> str:
    """golden_checks' invariants and situations on the drafted cases (report only)."""
    out = ["golden_checks invariants on the drafted cases (report only):"]
    for case in cases:
        plan = curated.plans[case["given"]["plan_id"]]

        def benefit(category: str, plan_id: str = plan.plan_id) -> tuple[str, int | None]:
            b = curated.benefit(plan_id, category)
            return b.cost_share_rule, b.copay_cents

        findings = check_calculator_case(case, plan)
        found = ", ".join(sorted(situations(case, plan, benefit)))
        out.append(
            f"- {case['case_id']}: {len(findings)} violations"
            + "".join(f"\n    {f.check} (line {f.line_no}): {f.detail}" for f in findings)
            + f"; situations: {found}"
            + (
                "; per-line COB differs from the claim-level formula"
                if cob_total_differs(case)
                else ""
            )
        )
    return "\n".join(out)


def main() -> None:
    from app.db.curated import load_curated

    golden = {
        case["case_id"]
        for path in sorted(GOLDEN_CALCULATOR.glob("*.json"))
        for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
    }
    accepted = sorted(golden & {draft.case_id for draft in DRAFTS})
    if accepted:
        raise SystemExit(f"already in the golden set (G3): {accepted}; nothing written")
    curated = load_curated()
    fees = load_fees({line.procedure_code for d in DRAFTS for line in d.lines}, curated)
    cases = [build_case(draft, curated, fees) for draft in DRAFTS]
    STAGING.mkdir(parents=True, exist_ok=True)
    CASES_FILE.write_text(json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8")
    SHEET_FILE.write_text(build_sheet(cases, curated), encoding="utf-8")
    print(
        f"wrote {CASES_FILE.relative_to(ROOT)} ({len(cases)} cases) and "
        f"{SHEET_FILE.relative_to(ROOT)}"
    )
    print(invariant_report(cases, curated))


if __name__ == "__main__":
    main()
