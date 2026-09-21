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
    return sorted(
        path for path in NCCI_DIR.glob(f"{NCCI_VERSION}-f*/*") if path.suffix.lower() == ".txt"
    )


def read_ncci_pairs(codes: set[str]) -> list[NcciPair]:
    """Practitioner PTP edits where both codes are in `codes` (all dates; filter with active_on)."""
    pairs = []
    for path in _ncci_files():
        with path.open(encoding="latin-1") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 6 or parts[0] not in codes or parts[1] not in codes:
                    continue
                effective = _yyyymmdd(parts[3])
                if effective is None:
                    continue
                pairs.append(
                    NcciPair(
                        column1=parts[0],
                        column2=parts[1],
                        effective_date=effective,
                        deletion_date=_yyyymmdd(parts[4]),
                        modifier_indicator=parts[5].strip(),
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


def read_place_of_service_codes() -> dict[str, str]:
    """Assigned place-of-service codes with their names (unassigned ranges are skipped)."""
    lines = []
    with pymupdf.open(POS_PDF) as doc:
        for page in doc:
            lines.extend(line.strip() for line in page.get_text().splitlines())
    codes = {}
    for index, line in enumerate(lines[:-1]):
        if re.fullmatch(r"[0-9]{2}", line):
            name = lines[index + 1]
            if name and not name.lower().startswith("unassigned"):
                codes[line] = name
    return codes
