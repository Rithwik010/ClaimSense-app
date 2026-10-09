"""P2.3b: the rules v2 curated data against its sources in data/raw/ (D-RULE-3, D-RULE-4): every
code role against the billing article's CPT list and the PFS add-on status, the diagnosis sets
against ICD-10-CM FY2027, and R15's groups and article versions against the MCD articles.

Skipped where data/raw/ is absent (CI). The tabular checks (Q4, Q5) also need the FY2027 ICD-10-CM
tabular in data/raw/icd10cm/FY2027/ and are skipped until it is there."""

import zipfile
from functools import cache
from pathlib import Path

import pytest

from app.db import raw
from app.db.curated import billing_articles, load_curated
from scripts.verify.rules_v2_impact import article_cpt_groups, pfs_global_days

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")

ARTICLE_OF_ROLE = {  # role -> (billing article, CPT group) that lists its codes
    "ESI_INTERLAMINAR": ("A56651", "1"),
    "ESI_TRANSFORAMINAL": ("A56651", "1"),
    "ESI_TRANSFORAMINAL_ADDON": ("A56651", "1"),
    "FACET_INJECTION": ("A57787", "1"),
    "FACET_INJECTION_ADDON": ("A57787", "1"),
    "FACET_THIRD_LEVEL": ("A57787", "2"),  # non-covered
    "FACET_DENERVATION": ("A57787", "1"),
    "FACET_DENERVATION_ADDON": ("A57787", "1"),
    "HOME_SLEEP_TEST": ("A56923", "1"),
    "NERVE_CONDUCTION": ("A57478", "1"),
    "NEEDLE_EMG": ("A57478", "1"),
    "TESTING_TIME": ("A57780", "1"),
}
ADD_ON = "ZZZ"  # PFS global days of an add-on code


@cache
def cpt_groups() -> dict:
    return article_cpt_groups({article for article, _ in ARTICLE_OF_ROLE.values()})


def test_every_role_code_is_listed_by_its_billing_article_and_in_the_code_table() -> None:
    roles = load_curated().code_roles
    table = raw.read_procedure_code_table()

    for code, role in roles.items():
        article, group = ARTICLE_OF_ROLE[role.role]
        assert code in table, code
        assert code in cpt_groups()[article][group], (code, role.role)


def test_add_on_roles_are_pfs_add_on_codes_and_primaries_are_not() -> None:
    roles = load_curated().code_roles
    days = pfs_global_days(set(roles))

    for code, role in roles.items():
        if role.role.endswith("_ADDON"):
            assert days[code] == ADD_ON, code
        elif role.role in {"ESI_INTERLAMINAR", "ESI_TRANSFORAMINAL", "FACET_INJECTION"}:
            assert days[code] != ADD_ON, code


def test_diagnosis_sets_are_fy2027_codes_and_the_cyst_codes_are_facet_covered() -> None:
    data = load_curated()
    icd10 = raw.read_icd10_codes()
    facet = raw.read_article_diagnoses({"A57787"})["A57787"]

    for codes in data.diagnosis_sets.values():
        assert codes <= set(icd10)
    assert data.diagnosis_sets["FACET_SYNOVIAL_CYST"] <= facet.covered[1]
    assert all(code.startswith("G475") for code in data.diagnosis_sets["PARASOMNIA"])


def test_r15_groups_exist_and_the_cited_article_versions_are_current() -> None:
    data = load_curated()
    articles = raw.read_article_diagnoses(billing_articles(data))

    for code, support in data.diagnosis_support.items():
        article = articles[support.billing_article]
        groups = {g for alternative in support.rule_alternatives for g in alternative}
        assert groups <= set(article.covered), code
        assert support.source.startswith(f"{article.article_id} v{article.version},"), code


# --- The FY2027 tabular (Q4, Q5) ---------------------------------------------------------------


def tabular_zip() -> zipfile.ZipFile | None:
    folder = raw.RAW_DIR / "icd10cm" / "FY2027"
    found = sorted(p for p in folder.glob("*.zip") if "index" in p.name.lower())
    return zipfile.ZipFile(found[0]) if found else None


@pytest.mark.skipif(tabular_zip() is None, reason="FY2027 ICD-10-CM tabular not in data/raw/")
def test_the_tabular_confirms_the_parasomnia_and_synovial_cyst_codes() -> None:
    """Q5: G47.5 Parasomnia has exactly the codes G47.50-G47.59 of the PARASOMNIA set. Q4: M71.3
    lists "Synovial cyst NOS" as an inclusion term, and the FACET_SYNOVIAL_CYST codes are under
    it."""
    import xml.etree.ElementTree as ET

    archive = tabular_zip()
    name = next(
        n
        for n in archive.namelist()
        if n.endswith("icd10cm_tabular_2027.xml") and "__MACOSX" not in n
    )
    root = ET.fromstring(archive.read(name))
    diagnoses = {d.findtext("name"): d for d in root.iter("diag")}

    def children(code: str) -> set[str]:
        return {c.findtext("name").replace(".", "") for c in diagnoses[code].findall("diag")}

    inclusions = [
        note.text or ""
        for term in diagnoses["M71.3"].findall("inclusionTerm")
        for note in term.findall("note")
    ]
    data = load_curated()
    assert children("G47.5") == data.diagnosis_sets["PARASOMNIA"]
    assert "Synovial cyst NOS" in inclusions
    assert data.diagnosis_sets["FACET_SYNOVIAL_CYST"] <= children("M71.3")


# --- The NCCI add-on code edits and the Policy Manual (P2.3c) -------------------------------------

AOC_PRESENT = raw.AOC_ZIP.exists()
MANUAL = (
    raw.RAW_DIR
    / "ncci-policy-manual"
    / "2026"
    / "2026_ncci_medicare_policy_manual_all-chapters.pdf"
)


@pytest.mark.skipif(not AOC_PRESENT, reason="NCCI add-on code edits not in data/raw/")
def test_the_add_on_code_edits_text_equals_the_excel_file() -> None:
    """The fixed-width text reader (app/db/raw.py) against the Excel copy in the same zip."""
    import tempfile

    with zipfile.ZipFile(raw.AOC_ZIP) as archive, tempfile.TemporaryDirectory() as folder:
        name = next(n for n in archive.namelist() if n.lower().endswith(".xlsx"))
        path = Path(folder) / "aoc.xlsx"
        path.write_bytes(archive.read(name))
        rows = list(raw._xlsx_rows(path))
    header = rows.index(next(r for r in rows if r and r[0] == "AOC_Edit_Type"))
    excel = []
    for row in rows[header + 1 :]:
        row = (row + [""] * 8)[:8]
        deleted = [d for d in (raw._julian(row[2]), raw._julian(row[4]), raw._julian(row[6])) if d]
        excel.append(
            (row[0], row[1], row[3], raw._julian(row[5]), min(deleted) if deleted else None)
        )
    text = [
        (e.edit_type, e.add_on, e.primary, e.effective, e.deleted) for e in raw.read_add_on_edits()
    ]

    assert text == excel and len(text) == 9003


@pytest.mark.skipif(not AOC_PRESENT, reason="NCCI add-on code edits not in data/raw/")
def test_every_curated_add_on_primary_is_in_the_add_on_code_edits() -> None:
    from datetime import date

    day = date(2026, 10, 1)
    primaries: dict[str, set[str]] = {}
    for edit in raw.read_add_on_edits():
        if edit.active_on(day):
            primaries.setdefault(edit.add_on, set()).add(edit.primary)
    roles = load_curated().code_roles

    for code, role in roles.items():
        if role.role.endswith("_ADDON"):
            assert role.primary_code in primaries[code], code


@pytest.mark.skipif(not MANUAL.exists(), reason="NCCI Policy Manual not in data/raw/")
def test_the_curated_modifiers_are_the_manuals_list() -> None:
    """Page I-14 (Chapter I section E): the NCCI PTP-associated modifiers, group by group."""
    import re

    import pymupdf

    with pymupdf.open(MANUAL) as doc:
        text = " ".join(re.sub(r"\s+", " ", page.get_text()) for page in doc.pages(29, 30))
    listing = text[text.index("Anatomic modifiers") : text.index("These modifiers are referred to")]

    def expand(part: str) -> set[str]:
        out = set()
        for item in re.findall(r"[A-Z0-9]{2}(?:-[A-Z0-9]{2})?", part):
            if "-" in item:
                first, last = item.split("-")
                out |= {f"{first[0]}{n}" for n in range(int(first[1]), int(last[1]) + 1)}
            else:
                out.add(item)
        return out

    anatomic, rest = listing.split("Global surgery modifiers")
    global_surgery, other = rest.split("Other modifiers")
    modifiers = load_curated().ptp_modifiers
    by_group = {
        g: {m for m, x in modifiers.items() if x.group == g}
        for g in ("ANATOMIC", "GLOBAL_SURGERY", "OTHER")
    }

    assert expand(anatomic.split(":", 1)[1]) == by_group["ANATOMIC"]
    assert expand(global_surgery.split(":", 1)[1]) == by_group["GLOBAL_SURGERY"]
    assert expand(other.split(":", 1)[1]) == by_group["OTHER"]
