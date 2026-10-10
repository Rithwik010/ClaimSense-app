"""Line decisions derived from the criterion statuses (D-DEC-1; D-POL-3).

The model's statuses decide the line, not its `decision` field: any NOT_MET outside an indication
group gives DENY; otherwise an indication group with no MET member gives PEND ("no covered
indication documented"); otherwise any NOT_DOCUMENTED outside the group gives PEND; otherwise
APPROVE. Group members are the criteria the retrieval tags `group` (policy set v2 only), so for v1
criteria the rule is prompt decision_v2's. One branch keeps the model's answer: a PEND on a line
flagged NCCI_BYPASS whose statuses imply APPROVE (the bypass documentation is not a criterion).

The pipeline uses this for both models, and generator v2 builds its labels with it.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.contracts import (
    CriterionStatus,
    LineDecision,
    RetrievedCriterion,
    SLMLine,
)

NO_INDICATION = "No covered indication documented."
BYPASS_FLAG = "NCCI_BYPASS"
DENY_CRITERION = "DN_NOT_MEDICALLY_NECESSARY"
DENY_EXCLUSION = "DN_CONDITIONAL_EXCLUSION"
PEND_MISSING = "PD_MISSING_DOCUMENTATION"


@dataclass(frozen=True)
class DerivedLine:
    decision: LineDecision
    reasons: list[str]
    missing_information: list[str]
    changed: bool  # the derived decision differs from the model's


def implied_decision(
    statuses: Sequence[tuple[CriterionStatus, bool]],
) -> tuple[LineDecision, bool]:
    """(decision, whether an indication group is unsatisfied) from (status, in a group) pairs."""
    outside = [status for status, grouped in statuses if not grouped]
    members = [status for status, grouped in statuses if grouped]
    unsatisfied = bool(members) and CriterionStatus.MET not in members
    if CriterionStatus.NOT_MET in outside:
        return LineDecision.DENY, unsatisfied
    if unsatisfied or CriterionStatus.NOT_DOCUMENTED in outside:
        return LineDecision.PEND, unsatisfied
    return LineDecision.APPROVE, False


def derive_line(
    line: SLMLine, criteria: Sequence[RetrievedCriterion], flags: Sequence[str]
) -> DerivedLine:
    """The decision for one model line; `criteria` are the line's retrieved criteria."""
    shown = {c.criterion_id: c for c in criteria}
    pairs = [
        (result.status, bool(shown.get(result.criterion_id) and shown[result.criterion_id].group))
        for result in line.criteria
    ]
    decision, unsatisfied = implied_decision(pairs)
    if (
        decision is LineDecision.APPROVE
        and line.decision is LineDecision.PEND
        and BYPASS_FLAG in flags
    ):
        decision = LineDecision.PEND
    if decision is line.decision:
        return DerivedLine(decision, list(line.reasons), list(line.missing_information), False)
    if decision is LineDecision.APPROVE:
        return DerivedLine(decision, [], [], True)
    if decision is LineDecision.DENY:
        exclusion = any(
            result.status is CriterionStatus.NOT_MET
            and shown.get(result.criterion_id) is not None
            and shown[result.criterion_id].criterion_type == "exclusion"
            for result in line.criteria
        )
        return DerivedLine(decision, [DENY_EXCLUSION if exclusion else DENY_CRITERION], [], True)
    missing = [NO_INDICATION] if unsatisfied else []
    missing += [
        f"{result.criterion_id}: {shown[result.criterion_id].text}"
        if result.criterion_id in shown
        else result.criterion_id
        for result in line.criteria
        if result.status is CriterionStatus.NOT_DOCUMENTED
        and not (shown.get(result.criterion_id) and shown[result.criterion_id].group)
    ]
    return DerivedLine(decision, [PEND_MISSING], missing, True)
