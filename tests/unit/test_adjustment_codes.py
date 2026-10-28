"""D-CARC-2: external reason codes (CARC/RARC) on DENY and REJECT reasons, looked up by reason code
(app/explain/codes.py). Descriptions come from the official lists in data/raw/; without them (CI)
the codes are shown alone and R15 gets no N115."""

import csv
from datetime import date
from pathlib import Path

from app.domain.contracts import (
    ClaimStatus,
    DecisionRecord,
    FinalLineDecision,
    RuleResult,
    RulesOutcome,
    Timestamps,
    Versions,
)
from app.explain.codes import adjustments, official, related_lcds
from app.explain.render import render

ROOT = Path(__file__).resolve().parents[2]
R15_CODE, R15_ARTICLE = next(
    (r["procedure_code"], r["billing_article"])
    for r in csv.DictReader((ROOT / "data/curated/diagnosis_support.csv").open())
    if r["billing_article"]
)
RAW = bool(official()["CARC"])


def record(
    lines: list[FinalLineDecision], failures: list[RuleResult] | None = None
) -> DecisionRecord:
    return DecisionRecord(
        claim_id="CLM-CARC-1",
        status=ClaimStatus.AWAITING_REVIEW,
        rules_outcome=RulesOutcome(
            claim_outcome="PASS", rule_results=failures or [], line_outcomes=[]
        ),
        line_decisions=lines,
        versions=Versions(rules_version="2.1.0"),
        timestamps=Timestamps(received=date(2026, 10, 1)),
    )


def line(n: int, decision: str, code: str | None, source: str = "MODEL") -> FinalLineDecision:
    return FinalLineDecision(
        line_no=n,
        decision=decision,
        benefit_category=None,
        source=source,  # type: ignore[arg-type]
        reason_codes=[code] if code else [],
    )


def codes(found) -> list[tuple]:  # noqa: ANN001
    return [
        (a.line_no, a.reason_code, a.group_code, [(c.kind, c.code) for c in a.codes]) for a in found
    ]


def test_deny_and_reject_reasons_get_their_codes_and_pended_lines_none() -> None:
    found = adjustments(
        record(
            [
                line(1, "DENY", "DN_NOT_MEDICALLY_NECESSARY"),
                line(2, "PEND", "PD_MISSING_DOCUMENTATION"),
            ],
            [
                RuleResult(
                    rule_id="R09",
                    passed=False,
                    outcome="DENY",
                    reason_code="DN_MISSING_REFERRAL",
                    detail="No referral",
                    fields_used=[],
                ),
                RuleResult(
                    rule_id="R01",
                    passed=False,
                    outcome="REJECT",
                    reason_code="RJ_MISSING_FIELD",
                    detail="Missing",
                    fields_used=[],
                ),
            ],
        )
    )

    assert codes(found) == [
        (1, "DN_NOT_MEDICALLY_NECESSARY", "CO", [("CARC", "50")]),
        (None, "DN_MISSING_REFERRAL", "CO", [("CARC", "288")]),  # no RARC (D-CARC-2)
        (None, "RJ_MISSING_FIELD", "CO", [("CARC", "16"), ("RARC", "MA130")]),
    ]


def test_level_limits_share_carc_151() -> None:
    found = adjustments(
        record(
            [line(1, "DENY", "DN_FACET_LEVELS", "RULE"), line(2, "DENY", "DN_ESI_LEVELS", "RULE")]
        )
    )

    assert [c[3] for c in codes(found)] == [[("CARC", "151"), ("RARC", "N115")]] * 2


def test_a_visit_limit_denial_is_pr_119_with_n640_and_its_official_descriptions() -> None:
    """D-CARC-3 (R21, D-RULE-10)."""
    (found,) = adjustments(record([line(1, "DENY", "DN_VISIT_LIMIT", "RULE")]))
    text = render(record([line(1, "DENY", "DN_VISIT_LIMIT", "RULE")]), "text")

    assert codes([found]) == [(1, "DN_VISIT_LIMIT", "PR", [("CARC", "119"), ("RARC", "N640")])]
    assert "the plan's yearly visit limit for this service is used up" in text
    assert "group PR" in text
    if RAW:
        assert [c.description for c in found.codes] == [
            "Benefit maximum for this time period or occurrence has been reached.",
            "Exceeds number/frequency approved/allowed within time period.",
        ]


def test_an_r15_denial_names_its_article_and_gets_n115_only_with_a_related_lcd() -> None:
    (found,) = adjustments(record([line(1, "DENY", "DN_DX_NOT_SUPPORTED", "RULE")]), {1: R15_CODE})

    assert found.billing_article == R15_ARTICLE
    assert found.lcds == related_lcds().get(R15_ARTICLE, [])
    assert [(c.kind, c.code) for c in found.codes] == [("CARC", "11")] + (
        [("RARC", "N115")] if found.lcds else []
    )


def test_descriptions_are_official_without_the_usage_note() -> None:
    (found,) = adjustments(
        record(
            [],
            [
                RuleResult(
                    rule_id="R01",
                    passed=False,
                    outcome="REJECT",
                    reason_code="RJ_MISSING_FIELD",
                    detail="x",
                    fields_used=[],
                )
            ],
        )
    )
    text = render(
        record(
            [],
            [
                RuleResult(
                    rule_id="R01",
                    passed=False,
                    outcome="REJECT",
                    reason_code="RJ_MISSING_FIELD",
                    detail="x",
                    fields_used=[],
                )
            ],
        ),
        "text",
    )

    assert "Adjustment codes\n  Claim (RJ_MISSING_FIELD), group CO" in text
    if RAW:
        assert (
            found.codes[0].description
            == "Claim/service lacks information or has submission/billing error(s)."
        )
        assert "Usage:" not in text
    else:
        assert found.codes[0].description is None
