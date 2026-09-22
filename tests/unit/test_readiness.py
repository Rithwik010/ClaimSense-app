"""Training readiness gate checks that need no services (parity is tested in tests/e2e)."""

import json

from app.ml.prompt import PROMPT_VERSION, system_prompt
from training.generate.decision_dataset import GENERATOR_VERSION
from training.readiness import (
    blind_review_agreement,
    check_current,
    check_lengths,
    check_missed,
    check_retrieval_label,
    sample_packet,
)


def record(n: int, scenario: str = "approve_single", missed: int = 0, prompt=PROMPT_VERSION):  # noqa: ANN001, ANN201
    return {
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": f"CLAIM {n}"},
            {"role": "assistant", "content": '{"lines": [], "complexity": "LOW"}'},
        ],
        "metadata": {
            "record_id": f"DEC-{n}",
            "split": "train",
            "scenario_type": scenario,
            "prompt_version": prompt,
            "criteria_missed": missed,
        },
    }


def data(records, **summary):  # noqa: ANN001, ANN003, ANN201
    return {
        "splits": {"train": (records, [{}] * len(records))},
        "summary": {"generator_version": GENERATOR_VERSION, "retrieval": "live", **summary},
    }


def test_dataset_must_match_the_current_code() -> None:
    assert check_current(data([record(1)])) == []
    assert "out of date" in check_current(data([record(1)], generator_version="old"))[0]
    assert "prompt versions" in check_current(data([record(1, prompt="decision_v1")]))[0]
    changed = record(2)
    changed["messages"][0]["content"] += " Extra."
    assert "system prompt text" in check_current(data([changed]))[0]


def test_retrieval_must_be_real_and_unchanged() -> None:
    assert check_retrieval_label(data([], retrieval="live"), "live") == []
    assert check_retrieval_label(data([], retrieval="simulated"), "live") == [
        "dataset built with simulated retrieval"
    ]
    assert "!=" in check_retrieval_label(data([], retrieval="old"), "live")[0]


def test_retrieval_misses_and_lengths() -> None:
    few = [record(n, missed=int(n == 0)) for n in range(20)]  # 5%
    many = [record(n, missed=int(n < 5)) for n in range(20)]  # 25%

    assert check_missed(data(few))[0] == []
    assert "25.0%" in check_missed(data(many))[0][0]
    problems, lengths = check_lengths(data(few))
    assert problems == [] and lengths["train"]["tokens_max"] > 0


def test_blind_review_agreement(tmp_path) -> None:  # noqa: ANN001
    sheet = tmp_path / "sheet.csv"
    key = tmp_path / "key.json"
    sheet.write_text(
        "claim_id,line_no,decision,benefit_category,reason_code,missing_information,"
        "reviewer_id,minutes_spent,notes\nC1,1,approve,,,,r1,2,\nC2,1,PEND,,,,r1,3,\nC3,1,,,,,,,\n"
    )
    lines = {"C1": "APPROVE", "C2": "DENY", "C3": "APPROVE"}
    key.write_text(
        json.dumps(
            {
                "key": {
                    c: {"target": {"lines": [{"line_no": 1, "decision": d}]}}
                    for c, d in lines.items()
                }
            }
        )
    )

    report = blind_review_agreement(sheet, key)

    assert report["lines"] == 2 and report["agreement"] == 0.5
    assert report["disagreements"] == [
        {"claim_id": "C2", "line_no": "1", "reviewer": "PEND", "label": "DENY"}
    ]


def test_review_packet_spreads_over_scenario_types() -> None:
    records = [record(n, scenario=f"type{n % 4}") for n in range(12)]

    packet = sample_packet(data(records), count=8)

    assert packet.count("## DEC-") == 8
    assert all(f"type{t})" in packet for t in range(4))
