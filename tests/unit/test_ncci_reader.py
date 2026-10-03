"""The NCCI PTP reader reads a part from its .txt, or from the official .xlsx when the .txt is
missing, with the same results. Synthetic files only; no data/raw/ needed."""

import zipfile
from pathlib import Path

import pytest

from app.db import raw

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TXT = (
    "CPT only copyright 2025 American Medical Association.\t\t\t\t\t\t\r\n"
    "Column1/Column2 Edits\t\t\t\t\t\t\r\n"
    "Column 1\tColumn 2\t*=in existence\tEffective\tDeletion\tModifier\tPTP Edit Rationale\r\n"
    "\t\tprior to 1996\tDate\tDate\t0=not allowed\t\r\n"
    "11042\t97597\t\t20120101\t*\t1\tMutually exclusive procedures\r\n"
    "11042\t0213T\t*\t19960101\t20061231\t9\tStandards of medical/surgical practice\r\n"
)
STRINGS = [
    "CPT only copyright 2025 American Medical Association.",
    "Column 1",
    "Column 2",
    "Effective",
    "11042",
    "97597",
    "20120101",
    "*",
    "1",
    "0213T",
    "19960101",
    "20061231",
    "9",
]


def _xlsx(path: Path, rows: list[list[tuple[str, int]]]) -> None:
    """A minimal .xlsx: every value is a shared string, as in the CMS files."""
    sheet = "".join(
        f'<row r="{n}">'
        + "".join(f'<c r="{col}{n}" t="s"><v>{index}</v></c>' for col, index in cells)
        + "</row>"
        for n, cells in enumerate(rows, start=1)
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook {NS} xmlns:r="{REL}"><sheets>'
            '<sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/sharedStrings.xml",
            f"<sst {NS}>" + "".join(f"<si><t>{s}</t></si>" for s in STRINGS) + "</sst>",
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            f"<worksheet {NS}><sheetData>{sheet}</sheetData></worksheet>",
        )


ROWS = [
    [("A", 0)],
    [("A", 1), ("B", 2), ("D", 3)],
    [("A", 4), ("B", 5), ("D", 6), ("E", 7), ("F", 8)],  # no C cell: the 1996 flag is empty
    [("A", 4), ("B", 9), ("C", 7), ("D", 10), ("E", 11), ("F", 12)],
]
EXPECTED = [
    ("11042", "97597", "20120101", "*", "1"),
    ("11042", "0213T", "19960101", "20061231", "9"),
]


def test_the_txt_and_the_xlsx_give_the_same_edit_records(tmp_path: Path) -> None:
    txt, xlsx = tmp_path / "part.TXT", tmp_path / "part.xlsx"
    txt.write_bytes(TXT.encode("latin-1"))
    _xlsx(xlsx, ROWS)

    assert list(raw.read_ncci_records(txt)) == EXPECTED
    assert list(raw.read_ncci_records(xlsx)) == EXPECTED


def _part(root: Path, name: str, *suffixes: str) -> None:
    folder = root / f"{raw.NCCI_VERSION}-{name}"
    folder.mkdir()
    for suffix in suffixes:
        (folder / f"{raw.NCCI_VERSION}-{name}{suffix}").write_text("", encoding="latin-1")


def test_a_part_is_read_from_its_txt_and_from_the_xlsx_only_without_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _part(tmp_path, "f1", ".xlsx")
    _part(tmp_path, "f2", ".TXT", ".xlsx")
    _part(tmp_path, "f3", ".txt")
    (tmp_path / "2026-10-changes-only").mkdir()
    monkeypatch.setattr(raw, "NCCI_DIR", tmp_path)

    assert [p.name for p in raw._ncci_files()] == [
        f"{raw.NCCI_VERSION}-f1.xlsx",
        f"{raw.NCCI_VERSION}-f2.TXT",
        f"{raw.NCCI_VERSION}-f3.txt",
    ]


def test_pairs_are_read_through_the_xlsx_when_the_txt_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / f"{raw.NCCI_VERSION}-f1"
    folder.mkdir()
    _xlsx(folder / f"{raw.NCCI_VERSION}-f1.xlsx", ROWS)
    monkeypatch.setattr(raw, "NCCI_DIR", tmp_path)

    pairs = raw.read_ncci_pairs({"11042", "97597"})

    assert [(p.column1, p.column2, p.modifier_indicator, p.deletion_date) for p in pairs] == [
        ("11042", "97597", "1", None)
    ]
    assert pairs[0].source_file == f"{raw.NCCI_VERSION}-f1.xlsx"
