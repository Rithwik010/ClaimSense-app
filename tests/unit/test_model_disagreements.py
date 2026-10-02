"""Task V1c: model-versus-gold disagreements are paired, grouped by known label problem and
sampled reproducibly. In-memory records only; no data/generated/ or data/raw/ needed."""

from collections import Counter

import pytest

from scripts.verify.model_disagreements import (
    CONTRADICTION,
    DECISION,
    DX,
    ESI,
    REHAB_EVAL,
    STATUS,
    Disagreement,
    Line,
    contradictory_notes,
    line_groups,
    pair_criteria,
    record_disagreements,
    select_sample,
)

RADICULAR = "Pain travels down the left leg to the foot."
NO_LIMB_PAIN = "No pain or numbness down the limbs."


def test_contradictory_notes_need_both_statements() -> None:
    assert contradictory_notes(f"{RADICULAR} {NO_LIMB_PAIN}")
    assert contradictory_notes("NO RADICULAR SX. Imaging: compressing the L5 nerve root.")
    assert not contradictory_notes(RADICULAR)
    assert not contradictory_notes(NO_LIMB_PAIN)
    assert not contradictory_notes("Low back pain, worse with standing.")


def _dx(results: dict[int, bool | None]):  # noqa: ANN202
    return lambda line: results[line.line_no]


def test_each_line_gets_its_known_problem_groups() -> None:
    lines = [
        Line(1, "62323", ("M5416",)),  # ESI
        Line(2, "97161", ("M6281",)),  # POL-REHAB-001 evaluation
        Line(3, "70553", ("R51",)),  # diagnosis not supported
        Line(4, "99213", ("R51",)),  # office visit: no billing article, not checkable
        Line(5, "93306", ("I10",)),  # supported, no group
    ]
    dx = _dx({1: True, 2: True, 3: False, 4: None, 5: True})

    groups = line_groups("approve_single", "Notes.", lines, dx)

    assert groups == {1: (ESI,), 2: (REHAB_EVAL,), 3: (DX,), 4: (), 5: ()}


def test_contradictory_notes_mark_every_line_but_only_in_two_policy_records() -> None:
    lines = [Line(1, "62323"), Line(2, "64493")]
    dx = _dx({1: False, 2: True})
    notes = f"{RADICULAR} {NO_LIMB_PAIN}"

    groups = line_groups("two_policy", notes, lines, dx)

    assert groups == {1: (DX, CONTRADICTION, ESI), 2: (CONTRADICTION,)}
    assert line_groups("same_profile_multi", notes, lines, dx)[2] == ()


def _target(*lines: tuple[int, list[tuple[str, str]]]) -> list[dict]:
    return [
        {
            "line_no": n,
            "criteria": [
                {"criterion_id": cid, "status": status, "evidence": f"gold {cid}"}
                for cid, status in criteria
            ],
        }
        for n, criteria in lines
    ]


def test_saved_pairs_get_their_criterion_ids_from_the_gold_order() -> None:
    target = _target((1, [("P.c1", "MET"), ("P.c2", "NOT_APPLICABLE")]), (2, [("P.c1", "MET")]))
    saved = [
        {"gold": "MET", "predicted": "NOT_DOCUMENTED"},
        {"gold": "NOT_APPLICABLE", "predicted": "NOT_APPLICABLE"},
        {"gold": "MET", "predicted": "MET"},
    ]

    pairs = pair_criteria(target, saved)

    assert [(p.line_no, p.criterion_id, p.gold, p.model) for p in pairs] == [
        (1, "P.c1", "MET", "NOT_DOCUMENTED"),
        (1, "P.c2", "NOT_APPLICABLE", "NOT_APPLICABLE"),
        (2, "P.c1", "MET", "MET"),
    ]
    with pytest.raises(ValueError, match="gold"):
        pair_criteria(target, [{**saved[0], "gold": "NOT_MET"}, *saved[1:]])
    with pytest.raises(ValueError, match="pairs"):
        pair_criteria(target, saved[:2])


def test_disagreements_list_status_and_decision_differences() -> None:
    target = _target((1, [("P.c1", "MET"), ("P.c2", "NOT_MET")]), (2, [("P.c1", "MET")]))
    saved = [
        {"gold": "MET", "predicted": "NOT_DOCUMENTED"},
        {"gold": "NOT_MET", "predicted": "NOT_MET"},
        {"gold": "MET", "predicted": "MET"},
    ]
    lines = {1: Line(1, "64483"), 2: Line(2, "99213")}
    saved_lines = [
        {"line_no": 1, "gold": "DENY", "predicted": "PEND"},
        {"line_no": 2, "gold": "APPROVE", "predicted": "APPROVE"},
    ]

    rows = record_disagreements(
        "DEC-TE-1",
        lines,
        pair_criteria(target, saved),
        saved_lines,
        valid=True,
        model_evidence={(1, "P.c1"): "Not documented in the clinical notes."},
        groups={1: (ESI,), 2: ()},
    )

    assert [(r.kind, r.line_no, r.criterion_id, r.error_type) for r in rows] == [
        (STATUS, 1, "P.c1", "MET -> NOT_DOCUMENTED"),
        (DECISION, 1, "", "DENY -> PEND"),
    ]
    assert rows[0].gold_evidence == "gold P.c1"
    assert rows[0].model_evidence == "Not documented in the clinical notes."
    assert all(r.groups == (ESI,) and r.record_groups == (ESI,) for r in rows)


def test_an_invalid_answer_gives_decision_rows_only() -> None:
    """The evaluator scores statuses on valid answers only; an invalid answer is PEND."""
    target = _target((1, [("P.c1", "MET")]))
    saved = [{"gold": "MET", "predicted": None}]

    rows = record_disagreements(
        "DEC-TE-2",
        {1: Line(1, "93306")},
        pair_criteria(target, saved),
        [{"line_no": 1, "gold": "APPROVE", "predicted": "PEND"}],
        valid=False,
        model_evidence={},
        groups={1: ()},
    )

    assert [(r.kind, r.error_type, r.valid) for r in rows] == [(DECISION, "APPROVE -> PEND", False)]


def _row(record: str, gold: str, model: str, groups: tuple[str, ...] = ()) -> Disagreement:
    return Disagreement(
        record_id=record,
        line_no=1,
        code="93306",
        kind=STATUS,
        gold=gold,
        model=model,
        criterion_id=f"P.{gold}.{model}",
        record_groups=groups,
    )


def _pool() -> list[Disagreement]:
    rows = [_row(f"R{n:02d}", "MET", "NOT_DOCUMENTED") for n in range(10)]
    rows += [_row(f"S{n:02d}", "NOT_MET", "NOT_DOCUMENTED") for n in range(6)]
    rows += [_row(f"T{n:02d}", "NOT_APPLICABLE", "NOT_DOCUMENTED") for n in range(2)]
    rows += [_row(f"U{n:02d}", "NOT_DOCUMENTED", "NOT_APPLICABLE") for n in range(2)]
    rows += [_row(f"V{n:02d}", "MET", "NOT_APPLICABLE") for n in range(5)]  # not sampled
    rows += [_row(f"K{n:02d}", "MET", "NOT_DOCUMENTED", (ESI,)) for n in range(20)]  # excluded
    return rows


def test_the_sample_takes_3_3_2_from_records_without_known_problems() -> None:
    sample, short = select_sample(_pool(), seed=42)

    types = Counter(r.error_type for r in sample)
    assert short == {} and len(sample) == 8
    assert types["MET -> NOT_DOCUMENTED"] == 3
    assert types["NOT_MET -> NOT_DOCUMENTED"] == 3
    assert (
        types["NOT_APPLICABLE -> NOT_DOCUMENTED"] + types["NOT_DOCUMENTED -> NOT_APPLICABLE"] == 2
    )
    assert not any(r.record_groups for r in sample)  # known-problem records stay out


def test_the_sample_is_reproducible_and_skips_decisions_and_invalid_answers() -> None:
    rows = _pool()
    rows += [
        Disagreement("D01", 1, "93306", DECISION, "APPROVE", "PEND"),
        Disagreement("I01", 1, "93306", STATUS, "MET", "NOT_DOCUMENTED", valid=False),
    ]

    first, _ = select_sample(rows, seed=42)
    again, _ = select_sample(list(reversed(rows)), seed=42)

    assert [r.record_id for r in first] == [r.record_id for r in again]
    assert {r.record_id for r in first}.isdisjoint({"D01", "I01"})


def test_a_short_pool_is_taken_whole_and_reported() -> None:
    rows = [_row("R00", "MET", "NOT_DOCUMENTED"), _row("S00", "NOT_MET", "NOT_DOCUMENTED")]

    sample, short = select_sample(rows, seed=42)

    assert {r.record_id for r in sample} == {"R00", "S00"}
    assert short == {
        "MET -> NOT_DOCUMENTED": 2,
        "NOT_MET -> NOT_DOCUMENTED": 2,
        "NOT_APPLICABLE / NOT_DOCUMENTED boundary": 2,
    }
