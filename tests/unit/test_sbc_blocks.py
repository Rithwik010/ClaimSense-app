"""The plan summary as the member's page reads it (P3.2, D-MEM-5): the generated Markdown into
headings, paragraphs, lists and tables, the text kept as written."""

from pathlib import Path

import pytest

from app.explain.sbc import parse_sbc

SBC = Path(__file__).resolve().parents[2] / "data" / "generated" / "sbc"
SAMPLE = """# A Plan — Summary of Benefits and Coverage

Plan ID PLN-X · PPO.
Fictional.

## Important questions

- **Overall deductible:** $500.00 per person.
- **Out-of-pocket limit:** $3,000.00.

## What you pay

| Service | In-network cost |
|---|---|
| Primary care visit | $25.00 copay |
| Imaging | 20% coinsurance |

## Filing a claim

File within 90 days.
"""


def test_blocks_in_order() -> None:
    summary = parse_sbc("PLN-X", SAMPLE)
    assert summary.title == "A Plan — Summary of Benefits and Coverage"
    assert [s.heading for s in summary.sections] == [
        None,
        "Important questions",
        "What you pay",
        "Filing a claim",
    ]
    intro, questions, table, filing = summary.sections
    assert intro.blocks[0].text == "Plan ID PLN-X · PPO. Fictional."  # one paragraph
    assert questions.blocks[0].items == [
        "**Overall deductible:** $500.00 per person.",
        "**Out-of-pocket limit:** $3,000.00.",
    ]
    assert table.blocks[0].kind == "table"
    assert table.blocks[0].header == ["Service", "In-network cost"]
    assert table.blocks[0].rows == [
        ["Primary care visit", "$25.00 copay"],
        ["Imaging", "20% coinsurance"],
    ]
    assert filing.blocks[0].text == "File within 90 days."


@pytest.mark.parametrize("path", sorted(SBC.glob("PLN-*.md")), ids=lambda p: p.stem)
def test_every_generated_summary_reads(path: Path) -> None:
    summary = parse_sbc(path.stem, path.read_text(encoding="utf-8"))
    assert "Summary of Benefits and Coverage" in summary.title
    kinds = {b.kind for s in summary.sections for b in s.blocks}
    assert kinds == {"paragraph", "list", "table"}
    # Every figure in the file is in the blocks (nothing dropped).
    text = " ".join(
        " ".join([b.text or "", *b.items, *b.header, *(" ".join(r) for r in b.rows)])
        for s in summary.sections
        for b in s.blocks
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        for token in line.split():
            if token.startswith("$"):
                assert token.rstrip(".,;") in text
