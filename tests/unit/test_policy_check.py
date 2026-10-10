"""P3.1 policy format checker: every committed policy passes; each defect is reported."""

import pytest

from app.db.curated import CURATED_DIR
from app.db.policy_check import check_policy_file, check_policy_text, main

GOOD = """---
policy_id: POL-IMG-009
title: Test imaging policy
procedure_codes: ["70551"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L37373 version 41 (revision effective 2025-10-23); billing article A57204"]
billing_article: A57204
split: TRAIN
---

## POL-IMG-009.c1
Covered when the scan fits the documented symptoms.

Source: LCD L37373 v41, Indications.

## POL-IMG-009.c2
Not covered for screening.

Source: LCD L37373 v41, Limitations.
"""


def check(text: str, name: str = "POL-IMG-009.md") -> list[str]:
    return check_policy_text(name, text, plan_ids={"PLN-PPO-GOLD"})


def test_every_committed_policy_passes() -> None:
    paths = sorted((CURATED_DIR / "coverage_policies" / "v1").glob("*.md"))

    assert len(paths) == 17
    for path in paths:
        assert check_policy_file(path) == [], path.name


def test_well_formed_policy_passes() -> None:
    assert check(GOOD) == []


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ("---\npolicy_id", "policy_id", "front matter"),
        ("title: Test imaging policy\n", "", "missing title"),
        ("split: TRAIN\n", "split: TRAIN\nowner: me\n", "unknown key owner"),
        ("policy_id: POL-IMG-009", "policy_id: POL-IMG-010", "does not match the file name"),
        ('procedure_codes: ["70551"]', "procedure_codes: []", "procedure_codes"),
        ('procedure_codes: ["70551"]', 'procedure_codes: ["7055"]', "procedure code 7055"),
        ('plan_ids: ["ALL"]', 'plan_ids: ["PLN-NOPE"]', "unknown plan PLN-NOPE"),
        ("effective_date: 2026-01-01", "effective_date: soon", "effective_date"),
        ("sources: [", "sources: []\nx: [", "sources"),
        ("billing_article: A57204", "billing_article: 57204", "billing_article"),
        ("split: TRAIN", "split: MAYBE", "split"),
        ("## POL-IMG-009.c2", "## POL-IMG-009.c3", "run c1, c2"),
        ("## POL-IMG-009.c2", "## POL-CAR-001.c2", "belongs to another policy"),
        ("Source: LCD L37373 v41, Limitations.\n", "", "one Source line"),
        ("Not covered for screening.\n", "", "no text"),
        ("v41, Limitations", "v40, Limitations", "LCD L37373 v40"),
        ("## POL-IMG-009.c1", "# Notes\n\n## POL-IMG-009.c1", "unexpected heading"),
    ],
)
def test_defects_are_reported(old: str, new: str, problem: str) -> None:
    assert old in GOOD
    problems = check(GOOD.replace(old, new, 1))

    assert any(problem in p for p in problems), problems


def test_no_criteria_is_reported() -> None:
    text = GOOD[: GOOD.index("## POL-IMG-009.c1")]

    assert "no criteria" in " ".join(check(text))


def test_cli_exits_zero_when_every_policy_passes(capsys) -> None:
    assert main([]) == 0
    assert "17 policies checked, 0 problems" in capsys.readouterr().out
