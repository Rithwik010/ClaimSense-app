"""Claim cost calculation (INSTRUCTIONS.md §8.6; assumptions A1–A9 in tests/golden/README.md).

Walking skeleton (P1.5): in-network lines in COPAY benefit categories only, with the out-of-pocket
cap. Anything else an approved line needs (deductible and coinsurance, out-of-network, coordination
of benefits) raises `UnsupportedCalculation` until P2.4.

Pure functions over integer cents. Denied and pended lines report the billed amount only (A7).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.calculator.money import apply_bps
from app.domain.contracts import (
    AmountTotals,
    CostBreakdown,
    CostShareRule,
    LineAmounts,
    LineDecision,
    Network,
    OtherCoverage,
)


class UnsupportedCalculation(ValueError):
    """A calculation the walking skeleton does not cover yet (P2.4)."""


class CalculationError(ValueError):
    """The inputs cannot be calculated: an approved line without a benefit category or a fee, or a
    COPAY benefit without a copay amount."""


@dataclass(frozen=True)
class CostShareTerms:
    cost_share_rule: CostShareRule
    copay_cents: int | None


@dataclass(frozen=True)
class NetworkTerms:
    deductible_cents: int
    coinsurance_bps: int
    oop_max_cents: int


@dataclass(frozen=True)
class Accumulators:
    deductible_met_cents: int
    oop_met_cents: int


@dataclass(frozen=True)
class FeeEntry:
    """Allowed amount per unit (D6)."""

    inn_allowed_cents: int
    oon_allowed_cents: int


@dataclass(frozen=True)
class CalcLine:
    line_no: int
    procedure_code: str
    units: int
    billed_cents: int
    decision: LineDecision
    benefit_category: str | None


@dataclass(frozen=True)
class CostShare:
    deductible_cents: int
    copay_cents: int
    coinsurance_cents: int

    @property
    def total_cents(self) -> int:
        return self.deductible_cents + self.copay_cents + self.coinsurance_cents


@dataclass(frozen=True)
class CalculationResult:
    amounts: CostBreakdown
    accumulators_after: Accumulators  # working accumulators; stored ones change at finalization


# --- the steps of §8.6 ---------------------------------------------------------------------------


def allowed_amount(line: CalcLine, network: Network, fee: FeeEntry) -> int:
    """Step 1: min(billed, fee for the network x units). The fee is per unit (A1)."""
    per_unit = fee.inn_allowed_cents if network is Network.IN_NETWORK else fee.oon_allowed_cents
    return min(line.billed_cents, per_unit * line.units)


def adjustments(billed_cents: int, allowed_cents: int, network: Network) -> tuple[int, int]:
    """Step 2: (contractual adjustment, balance-bill exposure). Billed minus allowed is a
    contractual adjustment in network and a balance-bill exposure out of network (A9); neither is
    paid by anyone."""
    difference = billed_cents - allowed_cents
    return (difference, 0) if network is Network.IN_NETWORK else (0, difference)


def cost_share(
    allowed_cents: int,
    network: Network,
    benefit: CostShareTerms,
    terms: NetworkTerms,
    deductible_remaining_cents: int,
) -> CostShare:
    """Step 3, before the out-of-pocket cap. In network, COPAY: copay = min(copay, allowed), no
    deductible. DEDUCTIBLE_COINSURANCE, and every out-of-network line whatever its category (A3):
    deductible = min(remaining deductible, allowed); coinsurance = (allowed - deductible) x
    coinsurance bps / 10000, rounded half up. `terms` are the terms for the line's network."""
    if network is Network.IN_NETWORK and benefit.cost_share_rule is CostShareRule.COPAY:
        if benefit.copay_cents is None:
            raise CalculationError("a COPAY benefit needs a copay amount")
        return CostShare(0, min(benefit.copay_cents, allowed_cents), 0)
    deductible = min(deductible_remaining_cents, allowed_cents)
    return CostShare(deductible, 0, apply_bps(allowed_cents - deductible, terms.coinsurance_bps))


def _billed_only(line: CalcLine) -> LineAmounts:
    return LineAmounts(
        line_no=line.line_no,
        billed_cents=line.billed_cents,
        allowed_cents=0,
        contractual_adjustment_cents=0,
        deductible_cents=0,
        copay_cents=0,
        coinsurance_cents=0,
        cob_primary_paid_cents=0,
        plan_pays_cents=0,
        member_pays_cents=0,
        balance_bill_exposure_cents=0,
    )


def _totals(lines: list[LineAmounts]) -> AmountTotals:
    return AmountTotals(
        **{name: sum(getattr(line, name) for line in lines) for name in AmountTotals.model_fields}
    )


def calculate(
    lines: list[CalcLine],
    network: Network,
    terms: NetworkTerms,
    benefits: Mapping[str, CostShareTerms],
    fees: Mapping[str, FeeEntry],
    accumulators: Accumulators,
    other_coverage: OtherCoverage | None = None,
) -> CalculationResult:
    if other_coverage is not None and other_coverage.primary_paid:
        raise UnsupportedCalculation("coordination of benefits is not supported yet (P2.4)")
    oop_remaining = max(terms.oop_max_cents - accumulators.oop_met_cents, 0)
    deductible_remaining = max(terms.deductible_cents - accumulators.deductible_met_cents, 0)
    oop_added = deductible_added = 0
    results = []
    for line in lines:
        if line.decision is not LineDecision.APPROVE:
            results.append(_billed_only(line))
            continue
        if line.benefit_category is None:
            raise CalculationError(
                f"line {line.line_no}: an approved line needs a benefit category"
            )
        if line.procedure_code not in fees:
            raise CalculationError(f"line {line.line_no}: no fee for {line.procedure_code}")
        allowed = allowed_amount(line, network, fees[line.procedure_code])
        contractual, balance_bill = adjustments(line.billed_cents, allowed, network)
        share = cost_share(
            allowed, network, benefits[line.benefit_category], terms, deductible_remaining
        )
        copay = min(share.copay_cents, oop_remaining)  # the skeleton's cap; P2.4 step 4 next
        share = CostShare(share.deductible_cents, copay, share.coinsurance_cents)
        oop_remaining -= share.total_cents
        oop_added += share.total_cents
        deductible_added += share.deductible_cents
        results.append(
            LineAmounts(
                line_no=line.line_no,
                billed_cents=line.billed_cents,
                allowed_cents=allowed,
                contractual_adjustment_cents=contractual,
                deductible_cents=share.deductible_cents,
                copay_cents=share.copay_cents,
                coinsurance_cents=share.coinsurance_cents,
                cob_primary_paid_cents=0,
                plan_pays_cents=allowed - share.total_cents,
                member_pays_cents=share.total_cents,
                balance_bill_exposure_cents=balance_bill,
            )
        )
    return CalculationResult(
        amounts=CostBreakdown(lines=results, totals=_totals(results)),
        accumulators_after=Accumulators(
            deductible_met_cents=accumulators.deductible_met_cents + deductible_added,
            oop_met_cents=accumulators.oop_met_cents + oop_added,
        ),
    )
