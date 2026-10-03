"""Readers for the public source files in `data/raw/` (INSTRUCTIONS.md §9.1, SOURCES.md).

Pure file readers with no database access, shared by the seed loaders (P2.1) and the synthetic
generators. `data/raw/` is never committed (H9), so callers check `raw_available()` first; tests
that need these files are skipped when it is absent (for example in CI).

AMA CPT descriptor text in the PFS, NCCI and MCD files is never returned (H10): only codes and
numbers are read from those files.
"""

import csv
import io
import re
import sys
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

import pymupdf

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

ICD10_ZIP = RAW_DIR / "icd10cm" / "FY2027" / "2027-code-descriptions-tabular-order.zip"
ICD10_MEMBER = "Code Descriptions/icd10cm_codes_2027.txt"
ICD10_FISCAL_YEAR = 2027
PFS_CSV = RAW_DIR / "pfs" / "rvu26a" / "PPRRVU2026_Jan_nonQPP.csv"
NCCI_DIR = RAW_DIR / "ncci-ptp"
NCCI_VERSION = "ccipra-v323r0"
MUE_CSV = RAW_DIR / "mue" / "2026-10" / "MCR_MUE_PractitionerServices_Eff_10-01-2026.csv"
MUE_EFFECTIVE = date(2026, 10, 1)
MCD_ARTICLES_ZIP = RAW_DIR / "mcd" / "2026-09-21" / "current_article.zip"
POS_PDF = RAW_DIR / "pos" / "2024-05-02" / "Website_POS_database__5_2_24 (kmk).pdf"

# PFS RVU file columns (the file has a ten-row header; see RVU26AR.pdf for the layout).
PFS_HCPCS, PFS_MOD, PFS_STATUS, PFS_NONFACILITY_TOTAL, PFS_CONVERSION_FACTOR = 0, 1, 3, 11, 25

csv.field_size_limit(sys.maxsize)


def raw_available() -> bool:
    return all(path.exists() for path in (ICD10_ZIP, PFS_CSV, NCCI_DIR, MUE_CSV, MCD_ARTICLES_ZIP))


@dataclass(frozen=True)
class PfsEntry:
    procedure_code: str
    status: str
    nonfacility_total_rvu: Decimal
    conversion_factor: Decimal


@dataclass(frozen=True)
class NcciPair:
    column1: str
    column2: str
    effective_date: date
    deletion_date: date | None
    modifier_indicator: str  # 0 = not allowed, 1 = allowed, 9 = not applicable
    source_file: str

    def active_on(self, day: date) -> bool:
        return self.effective_date <= day and (
            self.deletion_date is None or self.deletion_date >= day
        )


@dataclass(frozen=True)
class MueEntry:
    procedure_code: str
    max_units: int
    adjudication_indicator: str


@dataclass(frozen=True)
class ArticleDiagnoses:
    article_id: str  # e.g. "A56651"
    version: str
    covered: dict[int, frozenset[str]]  # covered group -> ICD-10-CM codes without dots
    noncovered: frozenset[str]


def _yyyymmdd(value: str) -> date | None:
    value = value.strip()
    if not value or value == "*":
        return None
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))


def read_icd10_codes() -> dict[str, str]:
    """Valid ICD-10-CM FY2027 codes (no dots) with their descriptions (public domain)."""
    with zipfile.ZipFile(ICD10_ZIP) as archive:
        text = archive.read(ICD10_MEMBER).decode("latin-1")
    codes = {}
    for line in text.splitlines():
        if line.strip():
            code, _, description = line.partition(" ")
            codes[code.strip()] = description.strip()
    return codes


def read_pfs(codes: set[str]) -> dict[str, PfsEntry]:
    """National non-facility total RVUs and conversion factor for the given codes (no modifier)."""
    entries = {}
    with PFS_CSV.open(encoding="latin-1", newline="") as f:
        for row in csv.reader(f):
            if len(row) <= PFS_CONVERSION_FACTOR or row[PFS_HCPCS] not in codes:
                continue
            if row[PFS_MOD].strip():
                continue
            entries[row[PFS_HCPCS]] = PfsEntry(
                procedure_code=row[PFS_HCPCS],
                status=row[PFS_STATUS],
                nonfacility_total_rvu=Decimal(row[PFS_NONFACILITY_TOTAL]),
                conversion_factor=Decimal(row[PFS_CONVERSION_FACTOR]),
            )
    return entries


def _ncci_files() -> list[Path]:
    """One file per part of the PTP edit table: its .txt, or the official .xlsx from the same CMS
    zip when the .txt is missing (f1: the .txt was lost; SOURCES.md)."""
    files = []
    for part in sorted(p for p in NCCI_DIR.glob(f"{NCCI_VERSION}-f*") if p.is_dir()):
        by_suffix = {p.suffix.lower(): p for p in part.iterdir() if p.stem == part.name}
        chosen = by_suffix.get(".txt") or by_suffix.get(".xlsx")
        if chosen is not None:
            files.append(chosen)
    return files


XLSX = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
XLSX_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NcciRecord = tuple[str, str, str, str, str]  # column 1, column 2, effective, deletion, modifier


def _xlsx_rows(path: Path) -> Iterator[list[str]]:
    """The first sheet's rows as text, one item per column from A, with the standard library
    (the CMS .xlsx stores every value as a shared string)."""
    with zipfile.ZipFile(path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        first = next(workbook.iter(f"{XLSX}sheet")).get(f"{XLSX_REL}id")
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(r for r in rels.iter(f"{PACKAGE_REL}Relationship") if r.get("Id") == first)
        sheet = "xl/" + target.get("Target", "").removeprefix("/xl/").removeprefix("/")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            table = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.iter(f"{XLSX}t")) for si in table]
        with archive.open(sheet) as f:
            parent = None
            for event, element in ElementTree.iterparse(f, events=("start", "end")):
                if event == "start":
                    if element.tag == f"{XLSX}sheetData":
                        parent = element
                    continue
                if element.tag != f"{XLSX}row":
                    continue
                cells: dict[int, str] = {}
                for cell in element.iterfind(f"{XLSX}c"):
                    kind, value = cell.get("t"), cell.find(f"{XLSX}v")
                    if kind == "s" and value is not None and value.text:
                        text = strings[int(value.text)]
                    elif kind == "inlineStr":
                        text = "".join(t.text or "" for t in cell.iter(f"{XLSX}t"))
                    else:
                        text = value.text or "" if value is not None else ""
                    letters = (cell.get("r") or "").rstrip("0123456789")
                    column = 0
                    for letter in letters:
                        column = column * 26 + ord(letter) - ord("A") + 1
                    cells[column - 1] = text
                yield [cells.get(i, "") for i in range(max(cells, default=-1) + 1)]
                if parent is not None:
                    parent.remove(element)  # keeps memory flat over a 200 MB sheet


def _txt_rows(path: Path) -> Iterator[list[str]]:
    with path.open(encoding="latin-1") as f:
        for line in f:
            yield line.rstrip("\n").split("\t")


def read_ncci_records(path: Path) -> Iterator[NcciRecord]:
    """Every edit row of one part of the PTP table, from its .txt or its .xlsx, as published:
    (column 1, column 2, effective date, deletion date or "*", modifier indicator). Header rows
    are skipped: an edit row has both codes and an eight-digit effective date."""
    rows = _xlsx_rows(path) if path.suffix.lower() == ".xlsx" else _txt_rows(path)
    for parts in rows:
        if len(parts) < 6:
            continue
        column1, column2, effective, deletion, modifier = (
            parts[i].strip() for i in (0, 1, 3, 4, 5)
        )
        if column1 and column2 and re.fullmatch(r"[0-9]{8}", effective):
            yield column1, column2, effective, deletion, modifier


def read_ncci_pairs(codes: set[str]) -> list[NcciPair]:
    """Practitioner PTP edits where both codes are in `codes` (all dates; filter with active_on)."""
    pairs = []
    for path in _ncci_files():
        for column1, column2, effective, deletion, modifier in read_ncci_records(path):
            effective_date = _yyyymmdd(effective)
            if column1 in codes and column2 in codes and effective_date is not None:
                pairs.append(
                    NcciPair(
                        column1=column1,
                        column2=column2,
                        effective_date=effective_date,
                        deletion_date=_yyyymmdd(deletion),
                        modifier_indicator=modifier,
                        source_file=path.name,
                    )
                )
    return pairs


def read_mue(codes: set[str]) -> dict[str, MueEntry]:
    entries = {}
    with MUE_CSV.open(encoding="latin-1", newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 3 and row[0] in codes:
                entries[row[0]] = MueEntry(row[0], int(row[1]), row[2])
    return entries


def _article_rows(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with archive.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"))


def read_article_diagnoses(article_ids: set[str]) -> dict[str, ArticleDiagnoses]:
    """Covered ICD-10-CM groups and non-covered codes of the current version of each billing
    article (IDs like "A56651"), from the MCD current-article CSV download."""
    numeric = {article_id.removeprefix("A") for article_id in article_ids}
    with zipfile.ZipFile(MCD_ARTICLES_ZIP) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read("current_article_csv.zip")))
    versions = {
        row["article_id"]: row["article_version"]
        for row in _article_rows(inner, "article.csv")
        if row["article_id"] in numeric
    }
    covered: dict[str, dict[int, set[str]]] = {a: {} for a in versions}
    noncovered: dict[str, set[str]] = {a: set() for a in versions}
    for row in _article_rows(inner, "article_x_icd10_covered.csv"):
        if versions.get(row["article_id"]) == row["article_version"]:
            group = int(row["icd10_covered_group"])
            code = row["icd10_code_id"].replace(".", "")
            covered[row["article_id"]].setdefault(group, set()).add(code)
    for row in _article_rows(inner, "article_x_icd10_noncovered.csv"):
        code = row["icd10_code_id"].replace(".", "")
        if versions.get(row["article_id"]) == row["article_version"] and code != "XX000":
            noncovered[row["article_id"]].add(code)
    return {
        f"A{a}": ArticleDiagnoses(
            article_id=f"A{a}",
            version=versions[a],
            covered={g: frozenset(c) for g, c in sorted(covered[a].items())},
            noncovered=frozenset(noncovered[a]),
        )
        for a in versions
    }


POS_ROW = re.compile(r"[0-9]{2}(?:-[0-9]{2})?")  # a code, or a range of unassigned codes
POS_NAME_X = (130.0, 262.0)  # the PDF's name column (points); descriptions start at 262


def _pos_name(words: list[tuple]) -> str:
    """Words of one name cell in reading order. A line that ends in a hyphenated word continues
    without a space ("On Campus-" + "Outpatient Hospital"); a lone dash keeps its spaces."""
    lines: list[list[tuple]] = []
    for word in sorted(words, key=lambda w: w[1]):
        if lines and abs(word[1] - lines[-1][0][1]) <= 3:
            lines[-1].append(word)
        else:
            lines.append([word])
    name = ""
    for line in lines:
        for word in sorted(line, key=lambda w: w[0]):
            text = word[4]
            glued = name.endswith("-") and len(name.split()[-1]) > 1
            name += text if not name or glued else f" {text}"
    return name


def read_place_of_service_codes() -> dict[str, str]:
    """Assigned place-of-service codes with their names (unassigned ranges are skipped). A name
    can wrap onto several lines of the PDF's name column, so it is every word in that column from
    its code's row down to the next code's row."""
    codes = {}
    with pymupdf.open(POS_PDF) as doc:
        for page in doc:
            words = page.get_text("words")
            rows = sorted(
                (w for w in words if w[0] < POS_NAME_X[0] and POS_ROW.fullmatch(w[4])),
                key=lambda w: w[1],
            )
            for k, row in enumerate(rows):
                bottom = rows[k + 1][1] - 2 if k + 1 < len(rows) else page.rect.height
                name = _pos_name(
                    [
                        w
                        for w in words
                        if POS_NAME_X[0] <= w[0] < POS_NAME_X[1] and row[1] - 2 <= w[1] < bottom
                    ]
                )
                if "-" not in row[4] and name and not name.lower().startswith("unassigned"):
                    codes[row[4]] = name
    return codes
