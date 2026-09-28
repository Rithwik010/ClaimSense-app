"""Task V1b: do the coverage criteria come from their LCDs, and is anything in the LCDs missing?

Report only: nothing in `data/curated/coverage_policies/` is changed (frozen for model v1).

Part 1 checks `data/curated/policy_sources.csv` (criterion_id, source_file, source_text): every
excerpt must appear in its LCD field (exact match, else the best `difflib` similarity, 0-1), and
the criterion is flagged when the excerpt is NOT FOUND, scores below 0.9, comes from a field other
than the LCD's coverage field, is composite (non-adjacent excerpts joined with " [...] "), differs
from the criterion in a number, duration, threshold or condition, or is far in meaning from the
criterion (embedding similarity, triage only).

Part 2 lists every item (paragraph or list item) of each cited LCD's coverage field and its
Associated Information field (documentation requirements), minus background, definitions and
abstracts, maps it to the criterion whose excerpt it contains, and otherwise classifies it.

LCD text is read from `data/raw/mcd/.../current_lcd.zip` (lcd.csv, latest version). Extraction
only removes HTML tags and footnote-reference superscripts, decodes entities and collapses
whitespace; excerpts must match that text word for word.

    uv run python -m scripts.verify.policy_sources --candidates POL-DX-002.c1   # pick excerpts
    uv run python -m scripts.verify.policy_sources                              # reports
"""

import argparse
import csv
import difflib
import html
import io
import json
import math
import random
import re
import sys
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LCD_ZIP = ROOT / "data" / "raw" / "mcd" / "2026-09-21" / "current_lcd.zip"
SOURCES_CSV = ROOT / "data" / "curated" / "policy_sources.csv"
POLICIES_DIR = ROOT / "data" / "curated" / "coverage_policies"
DATASET_DIR = ROOT / "data" / "generated" / "decision"
OUT_DIR = ROOT / "data" / "generated" / "verification"
# The Part 2 judgments are Claude-proposed, pending human review, and cannot be regenerated (the
# code that first wrote them was lost with a session scratchpad), so they are tracked in git and
# written only through save_judgments(), which will not overwrite them without --force.
CLASSIFICATION_CSV = ROOT / "data" / "verification" / "B_completeness_classification.csv"
JUDGMENT_FIELDS = ("item_id", "classification", "reason", "codes", "by")

COVERAGE_FIELD = "indication"  # MCD: "Coverage Indications, Limitations, and/or Medical Necessity"
ASSOCIATED_FIELD = "associated_info"  # MCD: "Associated Information" (documentation requirements)
ITEM_FIELDS = (COVERAGE_FIELD, ASSOCIATED_FIELD)
SEARCH_FIELDS = (COVERAGE_FIELD, ASSOCIATED_FIELD, "summary_of_evidence", "analysis_of_evidence")
JOIN = " [...] "
NOT_FOUND = "NOT FOUND"
MIN_SIMILARITY = 0.9
MINUTES_PER_ROW = 2
CAP_MINUTES = 45
SEED = 42
PART1_TITLE = (
    "Part 1 rows: write MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE.\n"
    "Part 2 rows: write ADD IN V2, NOT NEEDED or UNSURE."
)
INDEPENDENCE = (
    "The excerpts were selected by the same model that wrote the criteria, so the human review "
    "of the flagged rows and the controls is the independent check."
)
CLASSES = ("affects decisions", "rule candidate", "out of scope")

# --- LCD text ---------------------------------------------------------------------------------

BLOCK_SPLIT = re.compile(r"<(?:p|li|br|h[1-6]|div|tr|td|table|ul|ol)\b[^>]*>", re.IGNORECASE)
EMPHASIS = re.compile(r"<(strong|b|u|h[1-6])\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
SUPERSCRIPT = re.compile(r"<sup\b[^>]*>.*?</sup>", re.IGNORECASE | re.DOTALL)
TAG = re.compile(r"<[^>]+>")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"“])")
CONNECTOR = re.compile(r"^(?:and|or|and/or)$", re.IGNORECASE)
FOOTNOTE_ONLY = re.compile(r"^[\d\s,\-–]+$")
COVERAGE_HEADING = re.compile(
    r"^(?:covered indications|indications|limitations|non-?covered|coverage|indications and "
    r"limitations|documentation requirements|utilization guidelines|criteria)\b",
    re.IGNORECASE,
)
ENUMERATED_HEADING = re.compile(r"^(?:[A-Z][.)]|\d+[.)]|[IVX]+\.)\s")
BACKGROUND_HEADING = re.compile(r"^(?:history/background|definitions?\b|abstract\b)", re.IGNORECASE)


def clean(fragment: str) -> str:
    """Text as the checks see it: no superscript footnote references, no tags, entities decoded,
    whitespace collapsed."""
    text = TAG.sub(" ", SUPERSCRIPT.sub("", fragment))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


@dataclass(frozen=True)
class Block:
    field: str
    index: int
    text: str
    heading: bool
    section: str  # the headings above it, outermost first
    background: bool


def blocks(field_name: str, raw: str) -> list[Block]:
    out: list[Block] = []
    headings: list[str] = []
    background = False
    for fragment in BLOCK_SPLIT.split(raw or ""):
        text = clean(fragment)
        if not text or CONNECTOR.match(text) or FOOTNOTE_ONLY.match(text):
            continue
        outside_emphasis = clean(EMPHASIS.sub("", SUPERSCRIPT.sub("", fragment)))
        is_heading = len(text) <= 150 and (
            not outside_emphasis
            or (text.endswith(":") and len(text) <= 100)
            or bool(COVERAGE_HEADING.match(text) and len(text) <= 60)
            or bool(BACKGROUND_HEADING.match(text) and len(text) <= 60)
        )
        if is_heading:
            if BACKGROUND_HEADING.match(text):
                background = True
            elif COVERAGE_HEADING.match(text) or ENUMERATED_HEADING.match(text):
                background = False
            if COVERAGE_HEADING.match(text) or BACKGROUND_HEADING.match(text):
                headings = [text]
            else:
                headings = [*headings[:1], text]
        out.append(Block(field_name, len(out), text, is_heading, " > ".join(headings), background))
    return out


def sentences(text: str) -> list[str]:
    return [s for s in SENTENCE.split(text) if s]


@dataclass(frozen=True)
class Lcd:
    lcd_id: str  # "L33906"
    version: str
    fields: Mapping[str, str]  # field -> raw HTML

    def text(self, field_name: str) -> str:
        return " ".join(b.text for b in blocks(field_name, self.fields.get(field_name, "")))

    def source_file(self, field_name: str) -> str:
        return f"{LCD_ZIP.relative_to(ROOT)}:lcd.csv:{self.lcd_id}v{self.version}:{field_name}"


def load_lcds(lcd_ids: Iterable[str], path: Path = LCD_ZIP) -> dict[str, Lcd]:
    wanted = {i.removeprefix("L") for i in lcd_ids}
    csv.field_size_limit(sys.maxsize)
    with zipfile.ZipFile(path) as outer:
        name = next(n for n in outer.namelist() if n.endswith("csv.zip"))
        inner = zipfile.ZipFile(io.BytesIO(outer.read(name)))
    latest: dict[str, dict[str, str]] = {}
    with inner.open("lcd.csv") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1")):
            i = row["lcd_id"]
            if i in wanted and (
                i not in latest or int(row["lcd_version"]) > int(latest[i]["lcd_version"])
            ):
                latest[i] = row
    return {
        f"L{i}": Lcd(f"L{i}", row["lcd_version"], {k: row.get(k) or "" for k in SEARCH_FIELDS})
        for i, row in latest.items()
    }


# --- policies ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    policy_id: str
    text: str
    source: str  # the policy file's "Source:" line
    lcd_id: str


def load_criteria(directory: Path = POLICIES_DIR) -> dict[str, Criterion]:
    criteria: dict[str, Criterion] = {}
    for path in sorted(directory.glob("POL-*.md")):
        current, lines = None, []
        for line in [*path.read_text(encoding="utf-8").splitlines(), "## END"]:
            if line.startswith("## "):
                if current:
                    body = [x for x in lines if x.strip()]
                    source = next((x for x in body if x.startswith("Source:")), "")
                    lcd = re.search(r"\bL\d{5}\b", source)
                    criteria[current] = Criterion(
                        current,
                        path.stem,
                        " ".join(x for x in body if not x.startswith("Source:")),
                        source,
                        lcd.group(0) if lcd else "",
                    )
                current, lines = line[3:].strip(), []
            elif current:
                lines.append(line.strip())
    return criteria


# --- part 1: values and similarity ------------------------------------------------------------

NUMBER_WORDS = {
    w: n
    for n, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen nineteen twenty".split()
    )
} | {"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90, "once": 1, "twice": 2}
QUALIFIERS = {
    "at least": "at least",
    "minimum of": "at least",
    "a minimum of": "at least",
    "a minimum": "at least",
    "minimum": "at least",
    "or more": "at least",
    "more than": "more than",
    "greater than": "more than",
    "over": "more than",
    "less than": "less than",
    "fewer than": "less than",
    "no more than": "at most",
    "up to": "at most",
    "maximum of": "at most",
    "a maximum of": "at most",
    "limited to": "at most",
    "within": "within",
    "every": "every",
    "per": "per",
}
UNITS = {
    "%": "%",
    "percent": "%",
    "week": "week",
    "month": "month",
    "day": "day",
    "hour": "hour",
    "year": "year",
    "degree": "degree",
    "level": "level",
    "session": "session",
    "minute": "minute",
    "time": "time",
    "nerve": "nerve",
    "test": "test",
    "region": "region",
    "joint": "joint",
    "/10": "/10",
}
VALUE = re.compile(
    r"(?P<qual>at least|a minimum of|minimum of|a minimum|minimum|more than|greater than|over|"
    r"less than|fewer than|no more than|up to|a maximum of|maximum of|limited to|within|every|"
    r"per)?\s*"
    r"(?P<num>\d+(?:\.\d+)?|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"
    r"(?:\s*\(\d+\))?"
    r"(?:\s*-\s*|\s+)?(?P<unit>%|/10|(?:percent|weeks?|months?|days?|hours?|years?|degrees?|levels?|"
    r"sessions?|minutes?|times|nerves?|tests?|regions?|joints?)\b)"  # no \b after "%"
    r"(?P<after>\s+or more|\s+or less|\s+intervals?)?",
    re.IGNORECASE,
)
# "only" is not checked: all 10 of its hits on the V1b criteria were paraphrase equivalents
# ("purely on the basis", "should be reserved for", "sole purpose"), so it added only false alarms.
CONDITION_WORDS = ("unless", "except")


def values(text: str) -> set[str]:
    found = set()
    for m in VALUE.finditer(text):
        raw = m.group("num").lower()
        number = NUMBER_WORDS.get(raw, raw)
        unit = (
            m.group("unit").lower().rstrip("s")
            if m.group("unit") not in ("%", "/10")
            else m.group("unit")
        )
        unit = UNITS.get(unit, unit)
        qualifier = QUALIFIERS.get((m.group("qual") or "").lower().strip(), "")
        after = (m.group("after") or "").strip().lower()
        if after == "or more":
            qualifier = "at least"
        elif after == "or less":
            qualifier = "at most"
        elif after.startswith("interval"):
            qualifier = "every"
        number = str(float(number)).removesuffix(".0")
        found.add(f"{qualifier} {number} {unit}".strip())
    return found


def conditions(text: str) -> set[str]:
    """Condition words, also inside glued words (the LCD text has "contrastunless")."""
    lowered = text.lower()
    return {w for w in CONDITION_WORDS if w in lowered}


def differing_values(criterion: str, source: str) -> list[str]:
    """Numbers, durations and thresholds (with their qualifier) and condition words that appear on
    one side only. Heuristic: listed for a human to judge."""
    ours, theirs = values(criterion), values(source)
    out = [f"criterion: {v}" for v in sorted(ours - theirs)]
    out += [f"source: {v}" for v in sorted(theirs - ours)]
    c_ours, c_theirs = conditions(criterion), conditions(source)
    out += [f"condition word in criterion only: {w}" for w in sorted(c_ours - c_theirs)]
    out += [f"condition word in source only: {w}" for w in sorted(c_theirs - c_ours)]
    return out


def best_similarity(excerpt: str, text: str) -> float:
    """1.0 when the excerpt is in the text word for word, else the best difflib ratio against a
    window of consecutive sentences of about the excerpt's length."""
    if excerpt and excerpt in text:
        return 1.0
    parts = sentences(text)
    size = max(1, len(sentences(excerpt)))
    best = 0.0
    for width in {max(1, size - 1), size, size + 1}:
        for start in range(max(1, len(parts) - width + 1)):
            window = " ".join(parts[start : start + width])
            best = max(best, difflib.SequenceMatcher(None, excerpt, window).ratio())
    return round(best, 4)


@dataclass(frozen=True)
class SourceRow:
    criterion_id: str
    source_file: str
    source_text: str


def read_sources(path: Path = SOURCES_CSV) -> dict[str, SourceRow]:
    with path.open(encoding="utf-8", newline="") as f:
        return {r["criterion_id"]: SourceRow(**r) for r in csv.DictReader(f)}


def field_of(source_file: str) -> str:
    return source_file.rsplit(":", 1)[-1]


@dataclass
class Part1Result:
    criterion_id: str
    policy_id: str
    criterion_text: str
    source_file: str
    source_text: str
    similarity: float | None
    meaning: float | None
    differing: list[str]
    flags: list[str] = field(default_factory=list)


def check_source(
    criterion: Criterion,
    row: SourceRow | None,
    field_texts: Mapping[str, str],
    meaning: float | None = None,
    meaning_threshold: float | None = None,
) -> Part1Result:
    """field_texts: field name -> extracted text of the criterion's LCD."""
    result = Part1Result(
        criterion.criterion_id,
        criterion.policy_id,
        criterion.text,
        row.source_file if row else "",
        row.source_text if row else NOT_FOUND,
        None,
        meaning,
        [],
    )
    if row is None or row.source_text.strip() == NOT_FOUND:
        result.flags.append("NOT FOUND")
        return result
    excerpts = row.source_text.split(JOIN)
    files = row.source_file.split(JOIN)
    files = files if len(files) == len(excerpts) else files[:1] * len(excerpts)
    scores = []
    for excerpt, source_file in zip(excerpts, files, strict=True):
        name = field_of(source_file)
        scores.append(best_similarity(excerpt, field_texts.get(name, "")))
        if name != COVERAGE_FIELD:
            result.flags.append(f"outside the coverage field ({name})")
    result.similarity = min(scores)
    if result.similarity < MIN_SIMILARITY:
        result.flags.append(f"similarity {result.similarity:.2f} < {MIN_SIMILARITY}")
    if len(excerpts) > 1:
        result.flags.append(f"composite ({len(excerpts)} excerpts)")
    result.differing = differing_values(criterion.text, row.source_text.replace(JOIN, " "))
    if result.differing:
        result.flags.append("differing values")
    if meaning is not None and meaning_threshold is not None and meaning < meaning_threshold:
        result.flags.append(f"low meaning similarity {meaning:.3f} < {meaning_threshold:.3f}")
    result.flags = list(dict.fromkeys(result.flags))
    return result


# --- part 2: items, mapping, classification ---------------------------------------------------


@dataclass(frozen=True)
class Item:
    item_id: str
    policy_id: str
    lcd_id: str
    field: str
    section: str
    text: str
    start: int = 0  # position of the item in the field's text (Lcd.text)
    end: int = 0


def items_of(policy_id: str, lcd: Lcd) -> tuple[list[Item], int]:
    """(items, background blocks skipped) of the coverage and Associated Information fields."""
    out, skipped = [], 0
    for field_name in ITEM_FIELDS:
        position = 0
        for b in blocks(field_name, lcd.fields.get(field_name, "")):
            start, position = position, position + len(b.text) + 1  # blocks are joined by " "
            if b.heading:
                continue
            if b.background:
                skipped += 1
                continue
            tag = "cov" if field_name == COVERAGE_FIELD else "doc"
            out.append(
                Item(
                    f"{lcd.lcd_id}-{tag}-{b.index:03d}",
                    policy_id,
                    lcd.lcd_id,
                    field_name,
                    b.section,
                    b.text,
                    start,
                    start + len(b.text),
                )
            )
    return out, skipped


def excerpt_spans(row: SourceRow, field_texts: Mapping[str, str]) -> list[tuple[str, int, int]]:
    """(field, start, end) of each excerpt part in its field's text (first occurrence)."""
    if row.source_text == NOT_FOUND:
        return []
    parts = row.source_text.split(JOIN)
    files = row.source_file.split(JOIN)
    files = files if len(files) == len(parts) else files[:1] * len(parts)
    spans = []
    for part, source_file in zip(parts, files, strict=True):
        name = field_of(source_file)
        at = field_texts.get(name, "").find(part)
        if part and at >= 0:
            spans.append((name, at, at + len(part)))
    return spans


def mapped_criteria(
    item: Item,
    sources: Mapping[str, SourceRow],
    criteria: Mapping[str, Criterion],
    field_texts: Mapping[str, str],
) -> list[str]:
    """Criteria of the item's policy whose excerpt covers the item's position in the LCD text.
    Position, not wording: a short item such as "Palpitations" that the LCD repeats under another
    heading maps only where it was cited."""
    hits = []
    for cid, row in sources.items():
        if criteria.get(cid) is None or criteria[cid].policy_id != item.policy_id:
            continue
        for name, start, end in excerpt_spans(row, field_texts):
            if name == item.field and start < item.end and item.start < end:
                hits.append(cid)
                break
    return sorted(hits)


# Keyword rules: (pattern, classification, reason). The first match wins. Listed in the report.
RULES: list[tuple[str, str, str]] = [
    (
        r"\b(?:physician|provider|practitioner|therapist|technologist|staff|personnel)s?\b[^.]*\b"
        r"(?:qualif|certif|credential|licens|train|board)",
        "out of scope",
        "provider qualification; claims do not carry it",
    ),
    (
        r"\b(?:accredit|certified (?:lab|laboratory|facility|center)|"
        r"facility must|laboratory must)",
        "out of scope",
        "facility accreditation; claims do not carry it",
    ),
    (
        r"\b(?:sedation|anesthesia|anesthetic care|monitored anesthesia)\b",
        "out of scope",
        "sedation or anesthesia; not a service in our scope",
    ),
    (
        r"\b(?:supervision|supervised by|direct supervision|general supervision)\b",
        "out of scope",
        "supervision level; claims do not carry it",
    ),
    (
        r"\b(?:bill(?:ed|ing)?|report(?:ed)? (?:with|using)|modifier|claim form|units? of service|"
        r"CPT code|HCPCS code|ICD-10(?:-CM)? code)\b",
        "rule candidate",
        "coding or billing instruction checkable from claim codes",
    ),
    (
        r"\b(?:per (?:day|session|year|region)|in (?:a|any|one) (?:rolling )?\d+|within \d+|"
        r"(?:once|twice) (?:a|per|every)|frequency|same (?:day|session|date)|maximum of|more than "
        r"(?:one|\d+) (?:region|session|level|time))",
        "rule candidate",
        "frequency or same-session limit checkable from codes and dates",
    ),
]
BACKGROUND_REASON = "background, definitions or abstract (not an indication or limitation)"


def rule_classification(item: Item) -> tuple[str, str] | None:
    for pattern, classification, reason in RULES:
        if re.search(pattern, item.text, re.IGNORECASE):
            return classification, reason
    return None


@dataclass
class Judgment:
    item_id: str
    classification: str  # affects decisions | rule candidate | out of scope | covered by <id>
    reason: str
    codes: str = ""  # in-scope procedure codes the item concerns, space-separated ("" = policy's)
    by: str = "judgment"  # judgment | section


def read_judgments(path: Path = CLASSIFICATION_CSV) -> dict[str, Judgment]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {r["item_id"]: Judgment(**r) for r in csv.DictReader(f)}


class JudgmentsExist(RuntimeError):
    """The judgments file already holds judgments; replacing them needs --force."""


def valid_classification(value: str) -> bool:
    return value in CLASSES or value.startswith(("covered by POL-", "already decided ("))


def save_judgments(
    judgments: Sequence[Judgment], path: Path = CLASSIFICATION_CSV, force: bool = False
) -> int:
    """Write the judgments file. Refuses to overwrite a file that already holds judgments unless
    `force` is set, and refuses rows with an unknown classification or a repeated item."""
    existing = read_judgments(path)
    if existing and not force:
        raise JudgmentsExist(
            f"{path} already holds {len(existing)} judgments, which cannot be regenerated; "
            "run with --force to replace them"
        )
    seen: set[str] = set()
    for j in judgments:
        if not valid_classification(j.classification):
            raise ValueError(f"{j.item_id}: unknown classification {j.classification!r}")
        if j.item_id in seen:
            raise ValueError(f"{j.item_id}: judged twice")
        seen.add(j.item_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(
        path, [{k: getattr(j, k) for k in JUDGMENT_FIELDS} for j in judgments], JUDGMENT_FIELDS
    )
    return len(judgments)


# --- self-test --------------------------------------------------------------------------------

PLANTED_HTML = (
    "<p><strong>History/Background and/or General Information</strong></p>"
    "<p>Background text that is not a requirement.</p>"
    "<p><strong>Covered Indications</strong></p>"
    "<ul><li>Pain must have lasted at least four (4) weeks despite conservative care.</li>"
    "<li>Imaging must show nerve root compression<sup>3</sup>.</li></ul>"
    "<p><strong>Limitations</strong></p>"
    "<p>Injections are limited to a maximum of four (4) sessions per spinal region in a "
    "rolling twelve (12) month period.</p>"
)
PLANTED_EVIDENCE = "<p>Guidelines suggest a two of four criteria approach.</p>"


@dataclass(frozen=True)
class PlantedCase:
    name: str
    criterion_text: str
    source: SourceRow | None
    expect_flag: str  # a substring of the expected flag, or "" for no flag


def planted_lcd() -> Lcd:
    return Lcd(
        "L00001", "1", {COVERAGE_FIELD: PLANTED_HTML, "summary_of_evidence": PLANTED_EVIDENCE}
    )


def planted_cases() -> list[PlantedCase]:
    lcd = planted_lcd()
    cov, ev = lcd.source_file(COVERAGE_FIELD), lcd.source_file("summary_of_evidence")
    text = "Pain must have lasted at least four (4) weeks despite conservative care."
    return [
        PlantedCase(
            "an exact excerpt passes",
            "Pain has lasted at least 4 weeks despite conservative care.",
            SourceRow("P.c1", cov, text),
            "",
        ),
        PlantedCase(
            "a made-up source sentence is flagged",
            "Pain has lasted at least 4 weeks.",
            SourceRow(
                "P.c2",
                cov,
                "Pain must be treated with acupuncture for six months "
                "before any injection is considered.",
            ),
            "similarity",
        ),
        PlantedCase(
            "NOT FOUND is flagged", "Anything.", SourceRow("P.c3", cov, NOT_FOUND), "NOT FOUND"
        ),
        PlantedCase(
            "a different duration is flagged",
            "Pain has lasted at least 6 weeks despite conservative care.",
            SourceRow("P.c4", cov, text),
            "differing values",
        ),
        PlantedCase(
            "an excerpt from the evidence summary is flagged",
            "Two of four criteria.",
            SourceRow("P.c5", ev, "Guidelines suggest a two of four criteria approach."),
            "outside the coverage field",
        ),
        PlantedCase(
            "a composite excerpt is flagged",
            "Pain for 4 weeks and root compression.",
            SourceRow("P.c6", cov, text + JOIN + "Imaging must show nerve root compression."),
            "composite",
        ),
    ]


def run_planted(case: PlantedCase) -> list[str]:
    lcd = planted_lcd()
    texts = {f: lcd.text(f) for f in lcd.fields}
    criterion = Criterion(
        case.source.criterion_id if case.source else "P.x",
        "POL-P",
        case.criterion_text,
        "",
        lcd.lcd_id,
    )
    return check_source(criterion, case.source, texts).flags


def self_test() -> tuple[str, bool]:
    results = []
    for case in planted_cases():
        flags = run_planted(case)
        ok = (not flags) if not case.expect_flag else any(case.expect_flag in f for f in flags)
        results.append((case.name, ok))
    items, skipped = items_of("POL-P", planted_lcd())
    results.append(("background blocks are skipped", skipped == 1 and len(items) == 3))
    results.append(
        (
            "footnote superscripts are removed",
            any(i.text == "Imaging must show nerve root compression." for i in items),
        )
    )
    passed = sum(ok for _, ok in results)
    text = (
        f"Checker self-test: {passed}/{len(results)} planted cases behaved as expected ("
        + "; ".join(f"{name}{'' if ok else ' FAILED'}" for name, ok in results)
        + ")."
    )
    return text, passed == len(results)


# --- run --------------------------------------------------------------------------------------


def dataset_line_counts() -> Counter[str]:
    counts: Counter[str] = Counter()
    for split in ("train", "validation", "test"):
        inputs = {}
        with (DATASET_DIR / f"{split}_inputs.jsonl").open(encoding="utf-8") as f:
            for line in f:
                i = json.loads(line)
                inputs[i["record_id"]] = i
        with (DATASET_DIR / f"{split}.jsonl").open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                claim = inputs[r["metadata"]["record_id"]]["claim"]
                codes = {s["line_no"]: s["procedure_code"] for s in claim["service_lines"]}
                for label in r["metadata"]["line_labels"]:
                    counts[codes[label["line_no"]]] += 1
    return counts


def candidates(criterion: Criterion, lcd: Lcd, top: int = 6) -> list[tuple[float, str, str]]:
    """(score, sentence ID, sentence) of the LCD sentences closest to the criterion, for choosing
    excerpts by ID."""
    from app.core.settings import get_settings
    from app.rag.embedding import FastEmbedder

    settings = get_settings()
    embedder = FastEmbedder(settings.embedding_model, settings.embedding_cache_dir)
    pool = []
    for field_name in SEARCH_FIELDS:
        for b in blocks(field_name, lcd.fields.get(field_name, "")):
            for n, s in enumerate(sentences(b.text)):
                pool.append((f"{field_name}:{b.index}:{n}", s))
    vectors = embedder.embed_documents([criterion.text, *[s for _, s in pool]])
    q = vectors[0]
    scored = [(cosine(q, v), sid, s) for (sid, s), v in zip(pool, vectors[1:], strict=True)]
    return sorted(scored, reverse=True)[:top]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / ((math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1.0)


def resolve(lcd: Lcd, sentence_ids: Sequence[str]) -> tuple[str, str]:
    """(source_file, source_text) for sentence IDs "field:block:sentence" or "field:block:a-b".
    Spans that follow each other in the field (the next sentence of the same block, or the first
    sentence of the next block) are joined with a space, so the result is one stretch of the field's
    text; non-adjacent spans are joined with " [...] "."""
    parts, files = [], []
    previous: tuple[str, int, int, int] | None = None  # field, block, last sentence, sentences
    for sid in sentence_ids:
        field_name, block_index, span = sid.split(":")
        block = blocks(field_name, lcd.fields.get(field_name, ""))[int(block_index)]
        first, _, last = span.partition("-")
        start, end = int(first), int(last or first)
        all_sentences = sentences(block.text)
        chosen = " ".join(all_sentences[start : end + 1])
        adjacent = (
            previous is not None
            and previous[0] == field_name
            and (
                (previous[1] == int(block_index) and previous[2] + 1 == start)
                or (
                    previous[1] + 1 == int(block_index)
                    and previous[2] + 1 == previous[3]
                    and start == 0
                )
            )
        )
        if adjacent:
            parts[-1] = f"{parts[-1]} {chosen}"
        else:
            parts.append(chosen)
            files.append(lcd.source_file(field_name))
        previous = (field_name, int(block_index), end, len(all_sentences))
    source_file = files[0] if len(set(files)) == 1 else JOIN.join(files)
    return source_file, JOIN.join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--candidates",
        nargs="*",
        metavar="CRITERION_ID",
        help="print the closest LCD sentences with their IDs, for choosing excerpts",
    )
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--queue",
        action="store_true",
        help="only write B_completeness_queue.csv (items that need a judgment)",
    )
    parser.add_argument(
        "--save-judgments",
        type=Path,
        metavar="CSV",
        help=f"replace the judgments in {CLASSIFICATION_CSV.relative_to(ROOT)} with this file",
    )
    parser.add_argument(
        "--force", action="store_true", help="allow --save-judgments to overwrite judgments"
    )
    args = parser.parse_args()
    if args.save_judgments:
        with args.save_judgments.open(encoding="utf-8", newline="") as f:
            rows = [Judgment(**{k: r[k] for k in JUDGMENT_FIELDS}) for r in csv.DictReader(f)]
        try:
            n = save_judgments(rows, force=args.force)
        except JudgmentsExist as exc:
            raise SystemExit(str(exc)) from exc
        print(f"saved {n} judgments to {CLASSIFICATION_CSV}")
        return
    criteria = load_criteria()
    lcds = load_lcds({c.lcd_id for c in criteria.values()})
    if args.candidates is not None:
        for cid in args.candidates or sorted(criteria):
            c = criteria[cid]
            print(f"\n## {cid} ({c.source})\n   {c.text}")
            for score, sid, s in candidates(c, lcds[c.lcd_id]):
                print(f"   {score:.3f}  {sid:28}  {s[:220]}")
        return
    write_reports(criteria, lcds, args.out, queue_only=args.queue)


MEANING_PERCENTILE = 0.10  # triage: flag the lowest tenth of criterion-to-excerpt similarity
PARAPHRASE_PERCENTILE = 0.05  # an unmapped item this close to a criterion is checked by hand
DESCRIPTOR_OMITTED = "[AMA CPT descriptor omitted]"
SCOPE_CSV = ROOT / "data" / "curated" / "procedure_scope.csv"


class Embeddings:
    """Cosine similarity with the project's local embedding model (bge-small), cached."""

    def __init__(self) -> None:
        from app.core.settings import get_settings
        from app.rag.embedding import FastEmbedder

        settings = get_settings()
        self.name = settings.embedding_model
        self._embedder = FastEmbedder(settings.embedding_model, settings.embedding_cache_dir)
        self._cache: dict[str, list[float]] = {}

    def prepare(self, texts: Iterable[str]) -> None:
        todo = sorted({t for t in texts if t and t not in self._cache})
        if todo:
            for text, vector in zip(todo, self._embedder.embed_documents(todo), strict=True):
                self._cache[text] = vector

    def cos(self, a: str, b: str) -> float:
        self.prepare([a, b])
        return round(cosine(self._cache[a], self._cache[b]), 4)


def nearest_rank(values: Sequence[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[max(1, math.ceil(p * len(ordered))) - 1]


def scope_codes(path: Path = SCOPE_CSV) -> dict[str, list[str]]:
    """Policy ID -> procedure codes in our scope."""
    out: dict[str, list[str]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["policy_id"]:
                out[row["policy_id"]].append(row["procedure_code"])
    return out


def cpt_descriptors(codes: Iterable[str]) -> list[str]:
    """AMA CPT descriptor texts (long and short, 3 words or more) of our codes, from the MCD article
    download, so that no excerpt copies them and no displayed item shows them."""
    from app.db.raw import MCD_ARTICLES_ZIP

    wanted = set(codes)
    with zipfile.ZipFile(MCD_ARTICLES_ZIP) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read("current_article_csv.zip")))
    found = set()
    with inner.open("article_x_hcpc_code.csv") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1")):
            if row["hcpc_code_id"] in wanted:
                for key in ("long_description", "short_description"):
                    text = (row.get(key) or "").strip()
                    if len(text.split()) >= 3:
                        found.add(text)
    return sorted(found, key=len, reverse=True)


def redact(text: str, descriptors: Sequence[str]) -> tuple[str, int]:
    count = 0
    for d in descriptors:
        text, n = re.subn(re.escape(d), DESCRIPTOR_OMITTED, text, flags=re.IGNORECASE)
        count += n
    return text, count


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def round_robin(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Highest impact first within each policy; policies take turns, highest impact first."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: (-r["impact"], r["item_id"])):
        groups[row["policy_id"]].append(row)
    order = sorted(groups, key=lambda p: (-groups[p][0]["impact"], p))
    out = []
    while any(groups[p] for p in order):
        for p in order:
            if groups[p]:
                out.append(groups[p].pop(0))
    return out


ALREADY_DECIDED_POLICY = "POL-PAIN-001"  # V1a: D-ESI-1 to D-ESI-7 and the v2-bundle notes
SEVERITY = (
    "NOT FOUND",
    "similarity",
    "outside the coverage field",
    "differing values",
    "low meaning similarity",
    "composite",
)


def _severity(flags: Sequence[str]) -> int:
    return min((i for i, s in enumerate(SEVERITY) for f in flags if f.startswith(s)), default=99)


def write_reports(criteria, lcds, out, queue_only: bool = False) -> None:  # noqa: ANN001, C901, PLR0912, PLR0915
    out.mkdir(parents=True, exist_ok=True)
    sources = read_sources()
    field_texts = {lid: {f: lcd.text(f) for f in SEARCH_FIELDS} for lid, lcd in lcds.items()}
    emb = Embeddings()

    # part 1
    found = {cid: r for cid, r in sources.items() if r.source_text != NOT_FOUND and cid in criteria}
    emb.prepare(
        [c.text for c in criteria.values()]
        + [r.source_text.replace(JOIN, " ") for r in found.values()]
    )
    meaning = {
        cid: emb.cos(criteria[cid].text, r.source_text.replace(JOIN, " "))
        for cid, r in found.items()
    }
    threshold = nearest_rank(list(meaning.values()), MEANING_PERCENTILE)
    part1 = [
        check_source(c, sources.get(cid), field_texts[c.lcd_id], meaning.get(cid), threshold)
        for cid, c in sorted(criteria.items())
    ]
    codes_by_policy = scope_codes()
    descriptors = cpt_descriptors({c for codes in codes_by_policy.values() for c in codes})
    leaked = [cid for cid, r in sources.items() if redact(r.source_text, descriptors)[1]]

    # part 2
    by_policy: dict[str, list[str]] = defaultdict(list)
    for cid, c in criteria.items():
        by_policy[c.policy_id].append(cid)
    policy_lcd = {c.policy_id: c.lcd_id for c in criteria.values()}
    items: list[Item] = []
    skipped = 0
    for policy, lcd_id in sorted(policy_lcd.items()):
        found_items, n = items_of(policy, lcds[lcd_id])
        items += found_items
        skipped += n
    mapping = {
        i.item_id: mapped_criteria(i, sources, criteria, field_texts[i.lcd_id]) for i in items
    }
    emb.prepare([i.text for i in items])
    closest = {
        i.item_id: max((emb.cos(i.text, criteria[cid].text), cid) for cid in by_policy[i.policy_id])
        for i in items
    }
    mapped_sims = [emb.cos(i.text, criteria[cid].text) for i in items for cid in mapping[i.item_id]]
    t_para = nearest_rank(mapped_sims, PARAPHRASE_PERCENTILE)
    judgments = read_judgments()
    counts = dataset_line_counts()
    rows, queue = [], []
    for i in items:
        sim, near = closest[i.item_id]
        rule = rule_classification(i)
        shown, hidden = redact(i.text, descriptors)
        base = {
            "item_id": i.item_id,
            "policy_id": i.policy_id,
            "lcd": i.lcd_id,
            "field": i.field,
            "section": i.section,
            "text": shown,
            "descriptors_omitted": hidden,
            "closest_criterion": near,
            "closest_similarity": sim,
        }
        needs_judgment = not mapping[i.item_id] and (sim >= t_para or rule is None)
        if needs_judgment:  # every such item is listed, judged or not, so the queue is stable
            queue.append(
                {
                    **base,
                    "why": (
                        f"close to {near} ({sim:.3f} >= {t_para:.3f})"
                        if sim >= t_para
                        else "no rule matched"
                    ),
                    "rule_hit": rule[0] if rule else "",
                    "judged": "yes" if i.item_id in judgments else "no",
                }
            )
        if mapping[i.item_id]:
            row = {
                **base,
                "mapping": "; ".join(mapping[i.item_id]),
                "classification": "mapped",
                "reason": "the criterion's source excerpt covers this item",
                "by": "source excerpt",
                "codes": "",
            }
        elif needs_judgment and i.item_id in judgments:
            j = judgments[i.item_id]
            row = {
                **base,
                "mapping": "NOT IN POLICY"
                if not j.classification.startswith(("covered by", "already decided"))
                else "",
                "classification": j.classification,
                "reason": j.reason,
                "by": j.by,
                "codes": j.codes,
            }
        elif needs_judgment:
            continue  # waiting for a judgment
        else:
            row = {
                **base,
                "mapping": "NOT IN POLICY",
                "classification": rule[0],
                "reason": rule[1],
                "by": "rule",
                "codes": "",
            }
        codes = row["codes"].split() or codes_by_policy.get(i.policy_id, [])
        row["impact"] = sum(counts[c] for c in codes)
        rows.append(row)

    queue_fields = [
        "item_id",
        "policy_id",
        "lcd",
        "field",
        "section",
        "text",
        "descriptors_omitted",
        "closest_criterion",
        "closest_similarity",
        "why",
        "rule_hit",
        "judged",
    ]
    _write_csv(out / "B_completeness_queue.csv", queue, queue_fields)
    print(
        f"part 1: {sum(bool(r.flags) for r in part1)} of {len(part1)} criteria flagged; "
        f"meaning threshold {threshold:.4f}; descriptor leaks {leaked}"
    )
    print(
        f"part 2: {len(items)} items ({skipped} background blocks skipped); mapped "
        f"{sum(bool(v) for v in mapping.values())}; paraphrase threshold {t_para:.4f}; "
        f"classified {len(rows)}; needing judgment {len(queue)}, of which not yet judged "
        f"{sum(q['judged'] == 'no' for q in queue)}"
    )
    if queue_only or any(q["judged"] == "no" for q in queue):
        return

    # full CSVs
    part1_fields = [
        "criterion_id",
        "policy_id",
        "criterion_text",
        "source_file",
        "source_text",
        "similarity",
        "meaning_similarity",
        "differing_values",
        "flags",
        "status",
    ]
    part1_rows = [
        {
            "criterion_id": r.criterion_id,
            "policy_id": r.policy_id,
            "criterion_text": r.criterion_text,
            "source_file": r.source_file,
            "source_text": r.source_text,
            "similarity": r.similarity,
            "meaning_similarity": r.meaning,
            "differing_values": "; ".join(r.differing),
            "flags": "; ".join(r.flags),
            "status": (
                "already decided (D-ESI-1 to D-ESI-7)"
                if r.flags and r.policy_id == ALREADY_DECIDED_POLICY
                else "flagged"
                if r.flags
                else ""
            ),
        }
        for r in part1
    ]
    _write_csv(out / "B_policy_sources_full.csv", part1_rows, part1_fields)
    full_fields = [
        "item_id",
        "policy_id",
        "lcd",
        "field",
        "section",
        "text",
        "mapping",
        "classification",
        "reason",
        "by",
        "codes",
        "impact",
        "closest_criterion",
        "closest_similarity",
        "descriptors_omitted",
    ]
    _write_csv(out / "B_completeness_full.csv", rows, full_fields)

    # review rows
    rng = random.Random(SEED)
    flagged = [r for r in part1_rows if r["status"] == "flagged"]
    flagged.sort(key=lambda r: (_severity(r["flags"].split("; ")), r["criterion_id"]))
    unflagged = [r for r in part1_rows if not r["flags"]]
    controls1 = rng.sample(unflagged, min(2, len(unflagged)))
    gaps = [r for r in rows if r["classification"] in ("affects decisions", "rule candidate")]
    ordered_gaps = round_robin(gaps)
    rule_out = [r for r in rows if r["by"] == "rule" and r["classification"] == "out of scope"]
    controls2 = rng.sample(rule_out, min(3, len(rule_out)))
    cap_rows = CAP_MINUTES // MINUTES_PER_ROW
    part1_review = [*flagged, *[{**c, "control": True} for c in controls1]]
    part2_review = [*[{**c, "control": True} for c in controls2], *ordered_gaps]
    room = max(0, cap_rows - len(part1_review))
    part2_shown = part2_review[:room]
    part1_shown = part1_review[:cap_rows]
    left1 = len(part1_review) - len(part1_shown)
    left2 = len(part2_review) - len(part2_shown)

    self_line, self_ok = self_test()
    flag_counts = Counter(
        f.split(" (")[0].split(" <")[0].split(" 0")[0] for r in part1 for f in r.flags
    )
    classes = Counter(r["classification"] for r in rows)
    by = Counter(r["by"] for r in rows)
    covered = sum(v for k, v in classes.items() if k.startswith("covered by"))
    decided = sum(v for k, v in classes.items() if k.startswith("already decided"))
    dist = sorted(meaning.values())
    minutes = MINUTES_PER_ROW * (len(part1_shown) + len(part2_shown))
    decided_part1 = sum(r["status"].startswith("already") for r in part1_rows)
    lines = [
        "# Policy source and completeness check (Task V1b): review sheet",
        "",
        *PART1_TITLE.split("\n"),
        "",
        f"- **{INDEPENDENCE}**",
        f"- Criteria: {len(part1)}; flagged: {len(flagged) + decided_part1} "
        f"({', '.join(f'{k} {v}' for k, v in sorted(flag_counts.items()))}); "
        f"POL-PAIN-001 flags listed as already decided (D-ESI-1 to D-ESI-7), not reviewed again: "
        f"{sum(r['status'].startswith('already') for r in part1_rows)}.",
        f"- Meaning similarity (criterion vs its excerpt, {emb.name} cosine, triage only): min "
        f"{dist[0]:.3f}, 10th percentile {nearest_rank(dist, 0.10):.3f}, "
        f"median {nearest_rank(dist, 0.5):.3f}, "
        f"max {dist[-1]:.3f}; flagged below {threshold:.3f} (the 10th percentile).",
        f"- {self_line}",
        f"- LCD items: {len(items)} ({skipped} background, definition and abstract blocks "
        "skipped); "
        f"mapped to a criterion by its excerpt: {classes['mapped']}; covered by a criterion "
        f"(paraphrase): {covered}; already decided (POL-PAIN-001): {decided}.",
        "- NOT IN POLICY items per classification: "
        + ", ".join(f"{c} {classes[c]}" for c in CLASSES)
        + ".",
        f"- Classified by keyword rules: {by['rule']}; by section: {by['section']}; by item-level "
        f"judgment: {by['judgment']}. Unmapped items at least {t_para:.3f} similar to a criterion "
        "(5th percentile of mapped items) were judged by hand before any rule.",
        f"- AMA CPT descriptor text: excerpts containing it {len(leaked)}; displayed items with it "
        f"replaced by {DESCRIPTOR_OMITTED}: {sum(1 for r in rows if r['descriptors_omitted'])}.",
        f"- Estimated review time: {minutes} minutes ({MINUTES_PER_ROW} minutes per row; cap "
        f"{CAP_MINUTES}). Rows not shown here: Part 1 {left1}, Part 2 {left2}; they are in "
        "B_policy_sources_full.csv and B_completeness_full.csv.",
        "",
        "## Part 1: source check",
        "",
        "| # | Criterion ID | Our criterion text | Source file | Source text found (or NOT FOUND) "
        "| Similarity | Differing values | Your verdict | Notes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for n, r in enumerate(part1_shown, start=1):
        label = (
            f"{r['criterion_id']} ({'control' if r.get('control') else 'flagged: ' + r['flags']})"
        )
        lines.append(
            f"| {n} | {_cell(label)} | {_cell(r['criterion_text'])} | {_cell(r['source_file'])} | "
            f"{_cell(r['source_text'])} | {r['similarity']} | "
            f"{_cell(r['differing_values'] or '-')} |  |  |"
        )
    lines += [
        "",
        "## Part 2: completeness check",
        "",
        "| # | Policy | LCD section and item | LCD text (word for word) | Classification | Reason "
        "| Your verdict | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n, r in enumerate(part2_shown, start=1):
        cls = f"{r['classification']} (control)" if r.get("control") else r["classification"]
        where = f"{r['lcd']} {r['field']}: {r['section'] or '(top)'} > {r['item_id']}"
        lines.append(
            f"| {n} | {r['policy_id']} | {_cell(where)} | {_cell(r['text'])} | {_cell(cls)} | "
            f"{_cell(r['reason'])} (impact {r['impact']} lines) |  |  |"
        )
    (out / "B_policy_sources_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"review rows: part 1 {len(part1_shown)} (+{left1} in CSV), part 2 {len(part2_shown)} "
        f"(+{left2} in CSV), {minutes} minutes; {self_line}"
    )
    if not self_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
