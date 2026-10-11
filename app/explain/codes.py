"""External reason codes (CARC/RARC) for DENY and REJECT lines (D-CARC-1, D-CARC-2; §8.3, H6).

Looked up by the record's internal reason code in `data/curated/reason_code_map.csv` (code numbers
only); each code's official description is read at run time from the X12 lists saved in
`data/raw/carc-rarc/<date>/` (the latest folder), without the "Usage:" note. A denial by R15 also
names its billing article (by procedure code, `data/curated/diagnosis_support.csv`) and the LCDs
the article's current MCD record relates it to; RARC N115 ("based on an LCD") is shown only when
there is one. Without `data/raw/` (CI) the codes are shown without descriptions and R15 without
N115. Pended lines get no codes. No contract change: the record keeps internal codes only.
"""

import csv
import html
import io
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.domain.contracts import DecisionRecord, LineDecision, RuleOutcomeValue

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "data" / "curated" / "reason_code_map.csv"
SUPPORT = ROOT / "data" / "curated" / "diagnosis_support.csv"
LISTS = ROOT / "data" / "raw" / "carc-rarc"
MCD_ARTICLES = ROOT / "data" / "raw" / "mcd" / "2026-09-21" / "current_article.zip"
FILES = {
    "CARC": "claim-adjustment-reason-codes.html",
    "RARC": "remittance-advice-remark-codes.html",
}
R15_CODE = "DN_DX_NOT_SUPPORTED"
LCD_REMARK = "N115"


@dataclass(frozen=True)
class Code:
    kind: str  # CARC or RARC
    code: str
    description: str | None  # None without the official list


@dataclass(frozen=True)
class Adjustment:
    """The external codes of one DENY or REJECT reason on a line (line_no None: the claim)."""

    line_no: int | None
    reason_code: str
    group_code: str
    codes: list[Code]
    billing_article: str | None = None
    lcds: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def _map() -> dict[str, dict[str, str]]:
    with MAP.open(encoding="utf-8") as f:
        return {row["internal_code"]: row for row in csv.DictReader(f)}


@lru_cache(maxsize=1)
def official() -> dict[str, dict[str, str]]:
    """CARC and RARC code -> official description (without the "Usage:" note), from the latest
    saved X12 lists; empty without data/raw/."""
    folders = sorted(p for p in LISTS.glob("*") if p.is_dir()) if LISTS.exists() else []
    if not folders:
        return {"CARC": {}, "RARC": {}}
    found: dict[str, dict[str, str]] = {}
    for kind, name in FILES.items():
        text = (folders[-1] / name).read_text(encoding="utf-8", errors="replace")
        codes = {}
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
            cells = [
                " ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            ]
            if len(cells) >= 2 and re.fullmatch(r"[A-Z]{0,2}\d+", cells[0]):
                body = re.split(r"\s+Start:", cells[1])[0]
                codes[cells[0]] = re.split(r"\s+Usage:", body)[0].strip()
        found[kind] = codes
    return found


@lru_cache(maxsize=1)
def _articles() -> dict[str, str]:
    with SUPPORT.open(encoding="utf-8") as f:
        return {
            r["procedure_code"]: r["billing_article"]
            for r in csv.DictReader(f)
            if r["billing_article"]
        }


@lru_cache(maxsize=1)
def related_lcds() -> dict[str, list[str]]:
    """Billing article ID -> the LCD IDs its current MCD record relates it to (data/raw/)."""
    if not MCD_ARTICLES.exists():
        return {}
    csv.field_size_limit(1 << 30)  # article descriptions run past the default 128 KB
    with zipfile.ZipFile(MCD_ARTICLES) as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read("current_article_csv.zip"))) as inner:
            articles = list(
                csv.DictReader(io.StringIO(inner.read("article.csv").decode("latin-1")))
            )
            related = list(
                csv.DictReader(
                    io.StringIO(inner.read("article_related_documents.csv").decode("latin-1"))
                )
            )
    current: dict[str, int] = {}
    for a in articles:
        current[a["article_id"]] = max(current.get(a["article_id"], 0), int(a["article_version"]))
    lcds: dict[str, set[str]] = {}
    for r in related:
        if r["r_lcd_id"] not in ("", "0") and int(r["article_version"]) == current.get(
            r["article_id"]
        ):
            lcds.setdefault(f"A{r['article_id']}", set()).add(f"L{r['r_lcd_id']}")
    return {article: sorted(ids) for article, ids in lcds.items()}


def adjustment(
    reason_code: str, line_no: int | None, procedure_code: str | None
) -> Adjustment | None:
    row = _map().get(reason_code)
    if row is None or row["outcome"] not in ("DENY", "REJECT") or not row["carc"]:
        return None
    descriptions = official()
    codes = [Code("CARC", row["carc"], descriptions["CARC"].get(row["carc"]))]
    article, lcds = None, []
    if reason_code == R15_CODE and procedure_code:
        article = _articles().get(procedure_code)
        lcds = related_lcds().get(article, []) if article else []
    if row["rarc"] and (reason_code != R15_CODE or lcds):
        codes.append(Code("RARC", row["rarc"], descriptions["RARC"].get(row["rarc"])))
    return Adjustment(line_no, reason_code, row["group_code"], codes, article, lcds)


def adjustments(
    record: DecisionRecord, procedure_codes: Mapping[int, str] | None = None
) -> list[Adjustment]:
    """The external codes of every DENY line and every REJECT or DENY rule failure of a record.
    `procedure_codes` (line -> code, from the claim) names R15's article when the record has no
    context package (a claim the rules decided)."""
    procedure = dict(procedure_codes or {})
    procedure.update(
        {
            c.line_no: c.procedure_code
            for c in (record.context_refs.lines if record.context_refs else [])
        }
    )
    found: list[Adjustment] = []
    seen: set[tuple[int | None, str]] = set()

    def add(code: str, line_no: int | None, procedure_code: str | None) -> None:
        if (line_no, code) in seen:
            return
        seen.add((line_no, code))
        item = adjustment(code, line_no, procedure_code)
        if item is not None:
            found.append(item)

    for line in sorted(record.line_decisions, key=lambda d: d.line_no):
        if line.decision is LineDecision.DENY:
            for code in line.reason_codes:
                add(code, line.line_no, procedure.get(line.line_no))
    for rule in record.rules_outcome.rule_results:
        if (
            not rule.passed
            and rule.reason_code
            and rule.outcome
            in (
                RuleOutcomeValue.REJECT,
                RuleOutcomeValue.DENY,
            )
        ):
            add(
                rule.reason_code,
                rule.line_no,
                procedure.get(rule.line_no) if rule.line_no else None,
            )
    return found
