"""Policies v2, checkpoint 1: the v2 policy format, the criterion ID rules (a changed meaning gets
a new ID, never a reused one) and the source references, checked by
scripts/verify/policies_v2_sources.py. Runs in CI: the v2 and v1 policy files are curated; the
LCD and manual texts are not needed here."""

import pytest

from scripts.verify.policies_v2_sources import (
    V1_DIR,
    V2_DIR,
    field_problems,
    id_problems,
    missing_values,
    parse_refs,
    parse_v2,
    read_v1,
)

FRONT = """---
policy_id: POL-TST-001
title: Test policy
procedure_codes: ["11111", "22222"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L10000 version 3 (test)"]
billing_article: A10000
split: TRAIN
policy_set: v2
replaces: {replaces}
---
"""
V1_TEXTS = {"POL-TST-001.c1": "Kept text.", "POL-TST-001.c2": "Old text."}
V1_META = {
    "policy_id": "POL-TST-001",
    "title": "Test policy",
    "procedure_codes": ["11111", "22222"],
    "plan_ids": ["ALL"],
    "effective_date": "2026-01-01",
    "sources": ["LCD L10000 version 3 (test)"],
    "billing_article": "A10000",
    "split": "TRAIN",
}


def policy(body: str, replaces: str = '{"POL-TST-001.c2": ["POL-TST-001.c3"]}'):  # noqa: ANN201
    return parse_v2("POL-TST-001.md", FRONT.format(replaces=replaces) + body)


GOOD = """
## POL-TST-001.c1
Kept text.

Type: requirement
Source: LCD L10000 v3, Indications.

## POL-TST-001.c3
New text.

Type: exclusion
Applies to: 22222
Source: LCD L10000 v3 cov-004.
"""


def test_a_well_formed_v2_policy_has_no_problems() -> None:
    found = policy(GOOD)

    assert found.problems == ()
    assert [(c.criterion_id, c.type, c.applies_to, c.group) for c in found.criteria] == [
        ("POL-TST-001.c1", "requirement", (), ""),
        ("POL-TST-001.c3", "exclusion", ("22222",), ""),
    ]
    assert id_problems(V1_TEXTS, found) == []
    assert field_problems(found, V1_META) == []


def test_a_kept_id_whose_text_changed_needs_a_new_id() -> None:
    found = policy(GOOD.replace("Kept text.", "Kept text, now broader."))

    assert id_problems(V1_TEXTS, found) == [
        "POL-TST-001.c1 keeps its v1 ID but its text changed: a changed meaning needs a new ID"
    ]


def test_a_new_criterion_never_reuses_a_v1_number() -> None:
    found = policy(GOOD.replace("c3", "c2"), replaces="{}")  # c2's number now holds new text

    assert id_problems(V1_TEXTS, found) == [
        "POL-TST-001.c2 keeps its v1 ID but its text changed: a changed meaning needs a new ID"
    ]
    renumbered = policy(GOOD.replace("c3", "c2").replace("New text.", "Old text."), "{}")
    assert id_problems(V1_TEXTS, renumbered) == []  # the same text keeps the same ID


def test_every_retired_criterion_is_listed_under_replaces_with_new_ids() -> None:
    assert id_problems(V1_TEXTS, policy(GOOD, replaces="{}")) == [
        "POL-TST-001.c2 is retired but not listed under replaces"
    ]
    assert id_problems(V1_TEXTS, policy(GOOD, '{"POL-TST-001.c2": ["POL-TST-001.c1"]}')) == [
        "replaces POL-TST-001.c2: POL-TST-001.c1 is not a new criterion"
    ]


def test_ids_run_upwards_and_new_ones_sit_above_the_highest_v1_number() -> None:
    swapped = GOOD.replace("## POL-TST-001.c1", "## POL-TST-001.cX").replace(
        "## POL-TST-001.c3", "## POL-TST-001.c1"
    )
    found = policy(swapped.replace("## POL-TST-001.cX", "## POL-TST-001.c3"))

    assert "criterion IDs must be unique and ascending" in id_problems(V1_TEXTS, found)


def test_type_group_and_applies_to_are_checked() -> None:
    body = GOOD.replace("Type: exclusion", "Type: optional").replace(
        "Applies to: 22222", "Applies to: 22222, 99999"
    )
    assert field_problems(policy(body), V1_META) == [
        "POL-TST-001.c3: type 'optional' is not requirement, exclusion or conditional",
        "POL-TST-001.c3: applies to 99999, which the policy does not cover",
    ]
    grouped = GOOD.replace("Type: exclusion", "Type: exclusion\nGroup: indication")
    assert field_problems(policy(grouped), V1_META) == [
        "POL-TST-001.c3: an indication-group criterion must be conditional, not exclusion",
        "group indication has 1 criterion; a group needs 2 or more alternatives",
    ]


def test_missing_or_repeated_lines_are_format_problems() -> None:
    body = GOOD.replace("Type: requirement\n", "").replace(
        "Source: LCD L10000 v3 cov-004.", "Source: LCD L10000 v3 cov-004.\nSource: again."
    )
    assert policy(body).problems == (
        "POL-TST-001.c1: needs exactly one Type line, found 0",
        "POL-TST-001.c3: needs exactly one Source line, found 2",
    )


def test_the_front_matter_keeps_the_v1_values() -> None:
    changed = parse_v2(
        "POL-TST-001.md",
        FRONT.format(replaces='{"POL-TST-001.c2": ["POL-TST-001.c3"]}').replace(
            "split: TRAIN", "split: TEST_ONLY"
        )
        + GOOD,
    )
    assert field_problems(changed, V1_META) == ["front matter split differs from v1"]


def test_source_references_expand_ranges_and_name_their_kind() -> None:
    refs, problems = parse_refs(
        "LCD L34636 v38 cov-004, cov-005 to cov-007, doc-002; "
        "Medicare Benefit Policy Manual Ch. 15 §290.C.3, §290.D; decision D-ESI-2."
    )

    assert problems == []
    assert [(r.kind, r.lcd_id, r.version, r.blocks, r.sections, r.decision) for r in refs] == [
        (
            "lcd",
            "L34636",
            "38",
            (("cov", 4), ("cov", 5), ("cov", 6), ("cov", 7), ("doc", 2)),
            (),
            "",
        ),
        ("bpm", "", "", (), ("290.C.3", "290.D"), ""),
        ("decision", "", "", (), (), "D-ESI-2"),
    ]


@pytest.mark.parametrize(
    "source",
    [
        "LCD L34636 v38, Indications.",  # prose: a new criterion must cite blocks
        "LCD L34636 v38 cov-009 to cov-005",  # backwards range
        "LCD L34636 v38 cov-005 to doc-007",  # range across fields
        "Benefit Policy Manual §290",  # not the cited form
    ],
)
def test_unreadable_source_references_are_problems(source: str) -> None:
    assert parse_refs(source)[1]


def test_numbers_in_a_criterion_missing_from_its_excerpts_are_flagged() -> None:
    excerpts = ["Pain duration of at least four (4) weeks.", "A maximum of two (2) levels."]

    assert missing_values("Pain for at least 4 weeks, at most 2 levels.", excerpts) == []
    assert missing_values("Pain for at least 6 weeks.", excerpts) == ["at least 6 week"]


def test_the_v2_policy_files_follow_the_format_and_the_id_rules() -> None:
    v1 = read_v1()
    paths = sorted(V2_DIR.glob("POL-*.md"))

    assert [p.name for p in paths] == sorted(p.name for p in V1_DIR.glob("POL-*.md"))
    for path in paths:
        found = parse_v2(path.name, path.read_text(encoding="utf-8"))
        texts, meta = v1[found.meta["policy_id"]]
        assert found.problems == (), path.name
        assert id_problems(texts, found) == [], path.name
        assert field_problems(found, meta) == [], path.name
