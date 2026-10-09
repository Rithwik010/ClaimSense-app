"""P2.3c: R11's NCCI PTP-associated modifiers (D-RULE-8) on what the golden cases leave out (the 13
cases checked on sheet G5 cover 59, the X modifiers, 25, 57, 58 and anatomic modifiers): 24, 78,
79, 27 and 91, 25 with a 010-day procedure or no known global period, and a v1 reference without
the manual's list. Runs in CI: the modifiers are curated; the edits and global days synthetic."""

from typing import Any

import pytest

from app.db.curated import load_curated
from app.db.rules_reference import ptp_refs
from app.domain.contracts import IntakeClaim
from app.rules.line_edits import check_line_edits
from tests.unit.rules_support import PLAN, claim_data, line, ncci, reference

PROCEDURE, VISIT = "11042", "99213"  # an NCCI edit: procedure column 1, office visit column 2
DAYS = {PROCEDURE: "000", VISIT: "XXX"}


def modifier_reference(days: dict[str, str] = DAYS, **overrides: Any):  # noqa: ANN201, B006
    modifiers, em = ptp_refs(load_curated())
    return reference(
        ncci={(PROCEDURE, VISIT): (ncci(PROCEDURE, VISIT, "1"),)},
        ptp_modifiers=modifiers,
        em_codes=em,
        global_days=days,
        **overrides,
    )


def visit_line(procedure_modifiers: list[str], visit_modifiers: list[str], ref) -> tuple:  # noqa: ANN001
    claim = IntakeClaim.model_validate(
        claim_data(
            service_lines=[
                line(line_no=1, procedure_code=PROCEDURE, modifiers=procedure_modifiers),
                line(line_no=2, procedure_code=VISIT, modifiers=visit_modifiers),
            ]
        )
    )
    _, outcomes = check_line_edits(claim, PLAN, ref)
    return outcomes[1].outcome, outcomes[1].reason_codes, outcomes[1].flags


BYPASSED = ("PASS", [], ["NCCI_BYPASS"])
DENIED = ("DENY", ["DN_NCCI_BUNDLED"], [])


@pytest.mark.parametrize(
    ("procedure_modifiers", "visit_modifiers", "expected"),
    [
        ([], ["24"], BYPASSED),  # 24 on the E&M, paired with a procedure
        (["24"], [], DENIED),  # 24 on the procedure: not its place
        (["78"], [], BYPASSED),  # 78 and 79 on the procedure
        (["79"], [], BYPASSED),
        ([], ["78"], DENIED),  # on the E&M: not their place
        ([], ["79"], DENIED),
        ([], ["27"], BYPASSED),  # 27 and 91 on either line
        (["91"], [], BYPASSED),
        ([], ["22"], DENIED),  # 22, 76 and 77 are not NCCI PTP-associated (page I-14)
    ],
)
def test_modifiers_the_golden_cases_leave_out(
    procedure_modifiers: list[str], visit_modifiers: list[str], expected: tuple
) -> None:
    assert visit_line(procedure_modifiers, visit_modifiers, modifier_reference()) == expected


def test_25_with_a_010_day_procedure_bypasses_and_without_a_global_period_does_not() -> None:
    assert visit_line([], ["25"], modifier_reference({PROCEDURE: "010"})) == BYPASSED
    assert visit_line([], ["25"], modifier_reference({})) == DENIED


def test_a_v1_reference_keeps_x_modifiers_on_either_line() -> None:
    """Without the manual's list (the generator's frozen v1 rules): XE, XP, XS, XU anywhere."""
    v1 = reference(ncci={(PROCEDURE, VISIT): (ncci(PROCEDURE, VISIT, "1"),)})

    assert visit_line([], ["XU"], v1) == BYPASSED
    assert visit_line([], ["XU"], modifier_reference()) == DENIED  # D-RULE-8: not on an E&M
