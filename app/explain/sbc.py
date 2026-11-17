"""A plan's summary of benefits and coverage (P3.2) as the member's plan page shows it: the
generated document (data/generated/sbc/<plan_id>.md) read into headings, paragraphs, lists and
tables, so the page shows it without rendering Markdown. Text is kept as written, `**bold**`
included; nothing is computed (every figure in it is checked against the plan by
tests/unit/test_sbc.py)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SbcBlock:
    kind: str  # paragraph, list or table
    text: str | None = None  # a paragraph
    items: list[str] = field(default_factory=list)  # a list's items
    header: list[str] = field(default_factory=list)  # a table's header row
    rows: list[list[str]] = field(default_factory=list)  # a table's rows


@dataclass(frozen=True)
class SbcSection:
    heading: str | None  # None for the text before the first section heading
    blocks: list[SbcBlock]


@dataclass(frozen=True)
class PlanSummary:
    plan_id: str
    title: str
    sections: list[SbcSection]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _divider(line: str) -> bool:
    return set(line.replace("|", "").replace(" ", "")) <= {"-", ":"} and "-" in line


def parse_sbc(plan_id: str, markdown: str) -> PlanSummary:
    title = plan_id
    sections: list[SbcSection] = []
    heading: str | None = None
    blocks: list[SbcBlock] = []
    paragraph: list[str] = []
    items: list[str] = []
    table: list[list[str]] = []

    def flush() -> None:
        nonlocal paragraph, items, table
        if paragraph:
            blocks.append(SbcBlock("paragraph", text=" ".join(paragraph)))
        if items:
            blocks.append(SbcBlock("list", items=items))
        if table:
            blocks.append(SbcBlock("table", header=table[0], rows=table[1:]))
        paragraph, items, table = [], [], []

    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            flush()
            title = line[2:].strip()
        elif line.startswith("#"):
            flush()
            if heading is not None or blocks:
                sections.append(SbcSection(heading, blocks))
            heading, blocks = line.lstrip("#").strip(), []
        elif line.startswith("|"):
            if paragraph or items:
                flush()
            if not _divider(line):
                table.append(_cells(line))
        elif line.startswith(("- ", "* ")):
            if paragraph or table:
                flush()
            items.append(line[2:].strip())
        elif not line:
            flush()
        else:
            if items or table:
                flush()
            paragraph.append(line)
    flush()
    if heading is not None or blocks:
        sections.append(SbcSection(heading, blocks))
    return PlanSummary(plan_id=plan_id, title=title, sections=sections)
