"""Task V1b: do the coverage criteria come from their LCDs, and is anything in the LCDs missing?

Report only: nothing in `data/curated/coverage_policies/v1/` is changed (frozen for model v1).

Part 1 checks `data/curated/policy_sources.csv` (criterion_id, source_file, source_text): every
excerpt must appear in its LCD field (exact match, else the best `difflib` similarity, 0-1), and
the criterion is flagged when the excerpt is NOT FOUND, scores below 0.9, comes from a field other
than the LCD's coverage field, is composite (non-adjacent excerpts joined with " [...] "), differs
from the criterion in a number, duration, threshold or condition, or is far in meaning from the
criterion (embedding similarity, triage only).

Part 2 lists every item (paragraph or list item) of each cited LCD's coverage field and its
Associated Information field (documentation requirements), minus background, definitions and
abstracts, maps it to the criterion whose excerpt it contains, and otherwise classifies it: a
saved judgment (data/verification/B_completeness_classification.csv) first, else a keyword rule.
The items that affect decisions or are rule candidates are grouped into FINDINGS, one proposed
v2 change to one policy each; every such item must be in exactly one finding.

The review sheet has two sittings for one reviewer: Part 1 flagged criteria, then Part 2 findings
(WRONG CRITERION first, then the rest by impact). Everything else is in the full CSVs.

LCD text is read from `data/raw/mcd/.../current_lcd.zip` (lcd.csv, latest version). Extraction
only removes HTML tags and footnote-reference superscripts, decodes entities and collapses
whitespace; excerpts must match that text word for word.

    uv run python -m scripts.verify.policy_sources --candidates POL-DX-002.c1   # pick excerpts
    uv run python -m scripts.verify.policy_sources --save-judgments new.csv --force  # add/replace
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
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LCD_ZIP = ROOT / "data" / "raw" / "mcd" / "2026-09-21" / "current_lcd.zip"
SOURCES_CSV = ROOT / "data" / "curated" / "policy_sources.csv"
POLICIES_DIR = ROOT / "data" / "curated" / "coverage_policies" / "v1"
DATASET_DIR = ROOT / "data" / "generated" / "decision"
SPLITS = ("train", "validation", "test")
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
ITEMS_PER_EXTRA_MINUTE = 4  # a finding takes a minute longer per 4 LCD items after the first
SITTING_MINUTES = 35
SEED = 42
PART1_VERDICTS = "MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE"
PART2_VERDICTS = "ADD IN V2, NOT NEEDED or UNSURE"
INDEPENDENCE = (
    "The excerpts were selected, and the items classified and grouped, by the same model that "
    "wrote the criteria, so the human review of the flagged rows, the findings and the controls "
    "is the independent check."
)
CLASSES = ("affects decisions", "rule candidate", "out of scope")
GAP_CLASSES = CLASSES[:2]

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


def classify(
    mapping: Sequence[str],
    judgment: "Judgment | None",
    rule: tuple[str, str] | None,
    needs_judgment: bool,
) -> tuple[str, str, str, str] | None:
    """(classification, reason, by, codes) of an item: the criterion whose excerpt covers it, else
    its saved judgment (which overrides a keyword rule), else the keyword rule. None while an item
    that needs a judgment has none."""
    if mapping:
        return "mapped", "the criterion's source excerpt covers this item", "source excerpt", ""
    if judgment is not None:
        return judgment.classification, judgment.reason, judgment.by, judgment.codes
    if needs_judgment or rule is None:
        return None
    return rule[0], rule[1], "rule", ""


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


def merge_judgments(existing: Mapping[str, Judgment], new: Sequence[Judgment]) -> list[Judgment]:
    """The existing judgments in their order, each replaced by a new one for the same item, then
    the new judgments for items not judged before."""
    replacements = {j.item_id: j for j in new}
    merged = [replacements.pop(item_id, j) for item_id, j in existing.items()]
    return merged + [j for j in new if j.item_id in replacements]


# --- part 2: findings -------------------------------------------------------------------------

WRONG = "WRONG CRITERION"  # our criterion says something the LCD contradicts
MISSING = "MISSING CRITERION"  # the LCD has a condition our policy does not state
RULE = "RULE CANDIDATE"  # checkable from claim codes, units, dates or history: a rule, not the SLM
FINDING_KINDS = (WRONG, MISSING, RULE)


@dataclass(frozen=True)
class Finding:
    """One proposed v2 change to one policy and the LCD items behind it (Claude-proposed, pending
    human review)."""

    finding_id: str  # "POL-SURG-004.F1"
    kind: str
    change: str
    items: tuple[str, ...]  # item IDs without the LCD prefix: "cov-016"
    criteria: tuple[str, ...] = ()  # WRONG CRITERION: the criteria the LCD contradicts
    codes: tuple[str, ...] = ()  # WRONG CRITERION: the procedure codes the contradiction affects

    @property
    def policy_id(self) -> str:
        return self.finding_id.rsplit(".", 1)[0]


def _items(*spec: str) -> tuple[str, ...]:
    """ "cov-107..110" -> ("cov-107", "cov-108", "cov-109", "cov-110")."""
    out: list[str] = []
    for s in spec:
        tag, _, numbers = s.partition("-")
        first, _, last = numbers.partition("..")
        out += [f"{tag}-{n:03d}" for n in range(int(first), int(last or first) + 1)]
    return tuple(out)


FINDINGS: tuple[Finding, ...] = (
    # POL-BH-001 (L34520)
    Finding(
        "POL-BH-001.F1",
        MISSING,
        "c2: add the LCD's other non-covered testing situations: the patient cannot take part "
        "meaningfully; educational or vocational purposes; ongoing substance abuse or "
        "intoxication; mental-status questions that belong in the psychiatric evaluation; "
        "adjustment to nursing-home placement.",
        _items("cov-033", "cov-034", "cov-038", "cov-040", "cov-041"),
    ),
    Finding(
        "POL-BH-001.F2",
        MISSING,
        "Add: each test in a battery must be individually medically necessary.",
        _items("cov-042"),
    ),
    Finding(
        "POL-BH-001.F3",
        RULE,
        "Rule: testing hours billed above 8 need documented necessity for the extended testing.",
        _items("cov-046"),
    ),
    # POL-CAR-001 (L37379)
    Finding(
        "POL-CAR-001.F1",
        MISSING,
        "c1: add the LCD's echocardiogram uses without heart symptoms: monitoring exposure to a "
        "cardiotoxic agent (agent named in the record), cardiac donor evaluation, and a baseline "
        "study soon after a prosthetic valve implant.",
        _items("cov-017", "cov-019", "cov-023", "doc-005"),
    ),
    Finding(
        "POL-CAR-001.F2",
        MISSING,
        "Add echocardiogram limitations: for chest pain in the emergency room only with findings "
        "of myocardial dysfunction; as the first test for syncope only with documented findings of "
        "valvular disease or obstructive cardiomyopathy.",
        _items("cov-015", "doc-004", "doc-006"),
    ),
    Finding(
        "POL-CAR-001.F3",
        MISSING,
        "c3: extend stress echo beyond suspected coronary disease (cardiomyopathy, hypertrophic "
        "cardiomyopathy gradient, after heart transplant, valvular lesions, pre-operative risk "
        "with a documented at-risk condition); add that it is not typically done in the acute "
        "phase of a heart attack; state that a prior exercise stress test is not required.",
        _items(
            "cov-050", "cov-053", "cov-062", "cov-063", "cov-065", "cov-070", "cov-072", "doc-007"
        ),
    ),
    Finding(
        "POL-CAR-001.F4",
        MISSING,
        "Add stress echo test-selection documentation: pharmacologic stress only when exercise "
        "cannot reach the target heart rate, with the reason documented; and the reason a stress "
        "EKG could not be interpreted.",
        _items("cov-074", "doc-002", "doc-003"),
    ),
    Finding(
        "POL-CAR-001.F5",
        RULE,
        "Rule: a second stress imaging study (stress echo or nuclear) for the same assessment "
        "(needs the patient's history across claims).",
        _items("doc-010"),
    ),
    # POL-CAR-002 (L34636)
    Finding(
        "POL-CAR-002.F1",
        WRONG,
        "c2: limit the ejection fraction condition (40% or less) for heart attack survivors to "
        "48-hour monitoring; the LCD's 30-day event monitoring list covers heart attack survivors "
        "without it.",
        _items("cov-030"),
        ("POL-CAR-002.c2",),
        ("93268",),
    ),
    Finding(
        "POL-CAR-002.F2",
        MISSING,
        "c2: add acute and subacute forms of ischemic heart disease for 48-hour and 30-day "
        "monitoring.",
        _items("cov-017", "cov-031"),
    ),
    Finding(
        "POL-CAR-002.F3",
        MISSING,
        "Add: a full workup in the past month, with continuing symptoms, before monitoring.",
        _items("doc-003"),
    ),
    # POL-DX-001 (L35050)
    Finding(
        "POL-DX-001.F1",
        MISSING,
        "c2: state the home (out-of-center) sleep test conditions instead of referring to them: "
        "high likelihood of moderate to severe apnea from documented symptoms and examination, no "
        "contraindicating comorbidities, the situations where home testing fits, and documented "
        "patient education on the device.",
        _items("cov-107..113", "cov-120", "doc-021"),
    ),
    Finding(
        "POL-DX-001.F2",
        MISSING,
        "Add the non-covered uses: chronic insomnia, insomnia related to depression, circadian "
        "rhythm disorders, pre-operative evaluation for LAUP without suspected apnea, chronic lung "
        "disease, seizure disorders not ruled out, typical parasomnias, epilepsy without sleep "
        "complaints, and periodic limb movements or restless legs.",
        _items("cov-079", "cov-086..093"),
    ),
    Finding(
        "POL-DX-001.F3",
        MISSING,
        "c3: CPAP titration needs an apnea diagnosis meeting the LCD's AHI thresholds, and a "
        "split-night study the LCD's conditions (titration over 3 hours, events eliminated).",
        _items("cov-050", "cov-051", "cov-055..057"),
    ),
    Finding(
        "POL-DX-001.F4",
        MISSING,
        "c3: follow-up studies are not routine for patients doing well on CPAP; add the follow-up "
        "indications (substantial weight loss, or weight gain with returning symptoms).",
        _items("cov-063..065"),
    ),
    Finding(
        "POL-DX-001.F5",
        MISSING,
        "c1: add the parasomnia indication (seizure disorder ruled out, episodes causing harm), "
        "and that sleep-related epilepsy usually needs no polysomnography.",
        _items("cov-069..072"),
    ),
    Finding(
        "POL-DX-001.F6",
        MISSING,
        "c1: narcolepsy testing needs documentation that the condition is severe enough to "
        "interfere with well-being and health.",
        _items("doc-018"),
    ),
    Finding(
        "POL-DX-001.F7",
        RULE,
        "Rule: a home sleep test billed with a parasomnia diagnosis.",
        _items("cov-068"),
    ),
    Finding(
        "POL-DX-001.F8",
        RULE,
        "Rule: more than two nights of testing need documented necessity (needs the patient's "
        "history across claims).",
        _items("doc-019"),
    ),
    # POL-DX-002 (L34594)
    Finding(
        "POL-DX-002.F1",
        MISSING,
        "Add the EMG limitations: foot muscles alone for a proximal lesion; conclusions from "
        "paraspinal EMG in surgically scarred regions; limited limb exams without paraspinal "
        "testing for radiculopathy.",
        _items("cov-062..064"),
    ),
    Finding(
        "POL-DX-002.F2",
        RULE,
        "Rule: nerve conduction without needle EMG on the claim is usually not necessary, except "
        "carpal tunnel syndrome with high pre-test probability (codes plus diagnosis).",
        _items("cov-037"),
    ),
    Finding(
        "POL-DX-002.F3",
        RULE,
        "Rule: nerve conduction is paid once per nerve, whatever the number of sites or methods "
        "(units).",
        _items("cov-053"),
    ),
    Finding(
        "POL-DX-002.F4",
        RULE,
        "Rule: a separate paraspinal EMG code is not expected with the extremity EMG code for the "
        "paraspinals of that extremity (codes billed together).",
        _items("cov-061"),
    ),
    # POL-DX-003 (L33261)
    Finding(
        "POL-DX-003.F1",
        WRONG,
        "c1: remove foods from intradermal testing; the LCD covers foods by prick testing only and "
        "calls intradermal food testing not recommended.",
        _items("cov-058", "cov-080"),
        ("POL-DX-003.c1",),
        ("95024",),
    ),
    Finding(
        "POL-DX-003.F2",
        MISSING,
        "Add: food allergy tests are inappropriate for chronic idiopathic urticaria or angioedema.",
        _items("cov-059"),
    ),
    Finding(
        "POL-DX-003.F3",
        MISSING,
        "c3: routine annual testing without a discernible indication is not acceptable.",
        _items("cov-060"),
    ),
    # POL-IMG-001 (L37373)
    Finding(
        "POL-IMG-001.F1",
        MISSING,
        "c3: contrast after head trauma only when documented symptoms suggest intracranial "
        "bleeding.",
        _items("cov-029"),
    ),
    Finding(
        "POL-IMG-001.F2",
        RULE,
        "Any same-day imaging rule must allow scans of different body areas on the same day.",
        _items("cov-042"),
    ),
    # POL-IMG-002 (L33619)
    Finding(
        "POL-IMG-002.F1",
        RULE,
        "Rule: ultrasound of the same extremity more than twice in six months (needs the patient's "
        "history across claims and laterality).",
        _items("cov-021"),
    ),
    # POL-PAIN-001 (L33906); D-ESI-1 to D-ESI-7 already cover its other gaps
    Finding(
        "POL-PAIN-001.F1",
        MISSING,
        "Add: ESIs are given together with conservative treatment, with the patient in an active "
        "rehabilitation, home exercise or functional restoration program.",
        _items("cov-021", "cov-022"),
    ),
    Finding(
        "POL-PAIN-001.F2",
        MISSING,
        "Add the investigational uses not named in D-ESI-4: complex regional pain syndrome, "
        "widespread diffuse pain, neuropathy from other causes, cervicogenic headache.",
        _items("cov-029"),
    ),
    Finding(
        "POL-PAIN-001.F3",
        MISSING,
        "Add the contraindications: suspected or active spinal infection, significant systemic "
        "infection, compressive lesions of the cord, conus or cauda equina, suspicion or major "
        "risk factors for cancer.",
        _items("cov-042"),
    ),
    Finding(
        "POL-PAIN-001.F4",
        MISSING,
        "Add: no predetermined series of ESIs; continuing ESIs needs a documented rationale.",
        _items("cov-035", "cov-040"),
    ),
    Finding(
        "POL-PAIN-001.F5",
        RULE,
        "Rule: at most 4 ESI sessions per spinal region in a rolling 12 months, and the LCD's "
        "conditions for treatment beyond 12 months (needs the patient's history across claims).",
        _items("cov-030", "cov-037"),
    ),
    Finding(
        "POL-PAIN-001.F6",
        RULE,
        "Rule: same-session levels from codes and units: transforaminal at most 2 levels; caudal "
        "or interlaminar 1 level and not bilateral.",
        _items("cov-032..034"),
    ),
    # POL-PAIN-002 (L33930)
    Finding(
        "POL-PAIN-002.F1",
        MISSING,
        "c4: add the relief thresholds: at least 80% relief from each diagnostic block before a "
        "second block, a therapeutic injection or a first ablation; at least 50% for 3 months "
        "before a repeat therapeutic injection, and for 6 months before a repeat ablation.",
        _items("cov-028", "cov-032", "cov-033", "cov-038", "cov-039"),
    ),
    Finding(
        "POL-PAIN-002.F2",
        MISSING,
        "Add: pain scores at baseline and after each diagnostic block on the same scale, and a "
        "baseline disability scale.",
        _items("cov-020"),
    ),
    Finding(
        "POL-PAIN-002.F3",
        MISSING,
        "Add: therapeutic facet injections only with a documented reason why ablation cannot be "
        "done.",
        _items("cov-034", "cov-055"),
    ),
    Finding(
        "POL-PAIN-002.F4",
        MISSING,
        "Add: intra-articular diagnostic blocks only when medial branch blocks are anatomically "
        "impossible or a therapeutic intra-articular injection is planned.",
        _items("cov-022"),
    ),
    Finding(
        "POL-PAIN-002.F5",
        MISSING,
        "Add: facet procedures need CT or fluoroscopic guidance (not ultrasound, MRI or none).",
        _items("cov-047"),
    ),
    Finding(
        "POL-PAIN-002.F6",
        MISSING,
        "Add the facet cyst aspiration conditions: imaging confirming nerve-root compression by "
        "the cyst, documented symptoms, and one repeat only after 50% improvement for 3 months.",
        _items("cov-043..045"),
    ),
    Finding(
        "POL-PAIN-002.F7",
        MISSING,
        "Add the limitations: generalized or centralized pain (such as fibromyalgia), after "
        "anterior lumbar interbody fusion, non-thermal or low-temperature denervation, and repeat "
        "diagnostic blocks when the source of recurrent pain is in question.",
        _items("cov-054", "cov-056", "cov-060", "cov-062"),
    ),
    Finding(
        "POL-PAIN-002.F8",
        RULE,
        "Rule: per spinal region in a rolling 12 months at most 4 diagnostic sessions, 4 "
        "therapeutic sessions and 2 ablation sessions (needs the patient's history across claims).",
        _items("cov-029", "cov-035", "cov-040"),
    ),
    Finding(
        "POL-PAIN-002.F9",
        RULE,
        "Rule: one spinal region and at most 2 levels per session; other blocks on the same day "
        "need their own documented necessity.",
        _items("cov-050", "cov-051", "cov-053"),
    ),
    # POL-REHAB-001 (L34428)
    Finding(
        "POL-REHAB-001.F1",
        WRONG,
        "c2: an initial evaluation or re-evaluation can be covered even when it finds that "
        "therapy is not needed, so the plan-of-care requirement applies to treatment only.",
        _items("cov-112"),
        ("POL-REHAB-001.c2",),
        ("97161", "97162"),
    ),
    Finding(
        "POL-REHAB-001.F2",
        MISSING,
        "c2: the patient is under the care of a physician or NPP, who certifies and recertifies "
        "the plan.",
        _items("cov-018", "doc-007", "doc-019"),
    ),
    Finding(
        "POL-REHAB-001.F3",
        MISSING,
        "Add the evaluation documentation: the initial examination's components, functional "
        "limitations in objective, measurable terms, and complexity factors that support the "
        "evaluation level billed.",
        _items("cov-021", "cov-107..111"),
    ),
    Finding(
        "POL-REHAB-001.F4",
        MISSING,
        "Add: timed procedures need one-on-one direct patient contact.",
        _items("cov-188"),
    ),
    Finding(
        "POL-REHAB-001.F5",
        MISSING,
        "Add the therapeutic exercise indications: one of the listed documented conditions, with "
        "objective measures.",
        _items("cov-191..195"),
    ),
    Finding(
        "POL-REHAB-001.F6",
        MISSING,
        "Add the manual therapy indications: documented restricted joint or soft-tissue motion or "
        "painful spasm, or lymphedema for lymphatic drainage.",
        _items("cov-232..244"),
    ),
    Finding(
        "POL-REHAB-001.F7",
        MISSING,
        "Add the therapeutic activities indications: a need for a broad range of movement-based "
        "techniques, clearly related to the condition treated.",
        _items("cov-263", "cov-267"),
    ),
    Finding(
        "POL-REHAB-001.F8",
        MISSING,
        "c3: documented objective progress toward goals, the rationale for continued treatment, "
        "ongoing reassessment, and a justification for services more extensive than typical.",
        _items("doc-015", "doc-025", "doc-026", "doc-028"),
    ),
    Finding(
        "POL-REHAB-001.F9",
        RULE,
        "Rule: a progress report at least every 10 treatment days, and plan recertification (needs "
        "the patient's visit and plan dates).",
        _items("doc-012", "doc-016"),
    ),
    # POL-SURG-001 (L33558)
    Finding(
        "POL-SURG-001.F1",
        MISSING,
        "c3: add a high probability of cataract acceleration from a planned procedure or "
        "irradiation.",
        _items("cov-008"),
    ),
    Finding(
        "POL-SURG-001.F2",
        MISSING,
        "Add: when both eyes are planned before the first surgery, each eye needs its own "
        "documented necessity.",
        _items("cov-014"),
    ),
    Finding(
        "POL-SURG-001.F3",
        MISSING,
        "Add complex cataract criteria: the listed intra- or post-operative factors (miotic pupil "
        "needing devices, weak or absent lens support, pediatric surgery, extreme post-operative "
        "inflammation).",
        _items("cov-017..021"),
    ),
    # POL-SURG-002 (L34005)
    Finding(
        "POL-SURG-002.F1",
        MISSING,
        "c1: add the missing covered indications: synchronous cancer or polyps, inflammatory "
        "bowel disease when it changes management, intraoperative localization, colonic "
        "ischemia, Streptococcus bovis endocarditis, refractory new-onset constipation, anorectal "
        "adenomatous polyp, infectious colitis.",
        _items("cov-014", "cov-022", "cov-024..026", "cov-032", "cov-033", "doc-001"),
    ),
    Finding(
        "POL-SURG-002.F2",
        MISSING,
        "Add: excision of colonic polyps as the indication for polyp removal.",
        _items("cov-029"),
    ),
    Finding(
        "POL-SURG-002.F3",
        MISSING,
        "Add the LCD's limitations: chronic stable irritable bowel or abdominal pain, acute "
        "diarrhea, hemorrhoids, metastatic cancer of unknown primary without colonic symptoms, "
        "routine follow-up of inflammatory bowel disease, routine pre-operative examination, upper "
        "GI bleeding with an upper source, fulminant colitis, possible perforation, acute severe "
        "diverticulitis, diverticulosis.",
        _items("cov-037..043", "cov-046..049"),
    ),
    # POL-SURG-003 (L34209)
    Finding(
        "POL-SURG-003.F1",
        MISSING,
        "c1: name the qualifying symptoms (one or more): pain or burning impairing mobility, "
        "recurrent superficial phlebitis, non-healing ulcer, bleeding varicosity, stasis "
        "dermatitis, refractory dependent edema.",
        _items("cov-010..015"),
    ),
    Finding(
        "POL-SURG-003.F2",
        MISSING,
        "Add the anatomical requirements for ablation: no aneurysm in the target segment, a "
        "maximum vein diameter (12 mm radiofrequency, 20 mm laser), no thrombosis or tortuosity, "
        "no significant arterial disease.",
        _items("cov-017..020"),
    ),
    Finding(
        "POL-SURG-003.F3",
        MISSING,
        "Add: the record documents the tests confirming the vascular pathology.",
        _items("doc-002"),
    ),
    Finding(
        "POL-SURG-003.F4",
        RULE,
        "Any same-day rule must allow stab phlebectomy of the same vein with ablation when the "
        "criteria are met.",
        _items("cov-028"),
    ),
    # POL-SURG-004 (L33944)
    Finding(
        "POL-SURG-004.F1",
        WRONG,
        "c2-c3: exempt the reconstructive conditions of the LCD's groups 2 and 3 (defects from "
        "disease, palsy, trauma or tumor surgery; congenital ptosis) from the functional-complaint "
        "and visual-field requirements.",
        _items("cov-016", "cov-030", "cov-038"),
        ("POL-SURG-004.c2", "POL-SURG-004.c3"),
        ("15822", "15823", "67904"),
    ),
    Finding(
        "POL-SURG-004.F2",
        MISSING,
        "Add the other reconstructive indications: prosthesis problems with an anophthalmic, "
        "microphthalmic or enophthalmic socket (with the listed documentation), and chronic "
        "dermatitis of pretarsal skin from redundant upper eyelid skin.",
        _items("cov-029", "cov-040"),
    ),
    # POL-WOUND-001 (L38902)
    Finding(
        "POL-WOUND-001.F1",
        MISSING,
        "Add criteria that separate surgical from selective or non-selective debridement: "
        "surgical only when tissue was excised to viable margins and the record supports it; "
        "extensive eczematous or infected skin is not a localized debridement; the conditions "
        "that may need extensive surgical debridement.",
        _items("cov-057..062", "cov-080", "cov-088"),
    ),
    Finding(
        "POL-WOUND-001.F2",
        MISSING,
        "Add the documentation requirements: wound status and response at each visit, "
        "measurements, signs of infection, tissue removed and depth, and the procedure note.",
        _items(
            "doc-004..007",
            "doc-009..011",
            "doc-015",
            "doc-016",
            "doc-019",
            "doc-020",
            "doc-022",
            "doc-024",
        ),
    ),
    Finding(
        "POL-WOUND-001.F3",
        MISSING,
        "c3: expect measurable healing (smaller wound, granulation); allow 30 days to set up the "
        "plan; revise the plan when healing is not documented after 30 days; do not continue a "
        "type of care that shows no improvement.",
        _items("cov-082", "cov-093", "cov-112", "cov-113", "cov-117", "cov-118"),
    ),
    Finding(
        "POL-WOUND-001.F4",
        MISSING,
        "Add: cleansing, dressing, paring of corns and the other listed services are not "
        "debridement.",
        _items("cov-097..099", "cov-102..108"),
    ),
    Finding(
        "POL-WOUND-001.F5",
        MISSING,
        "Add: care for cosmetic purposes is excluded.",
        _items("cov-094"),
    ),
    Finding(
        "POL-WOUND-001.F6",
        MISSING,
        "Add an indication for multi-layer compression, particularly venous leg ulcers.",
        _items("cov-076"),
    ),
    Finding(
        "POL-WOUND-001.F7",
        RULE,
        "Rule: more than 12 surgical debridements (5 involving muscle, fascia or bone) in 360 "
        "days is unusual (needs the patient's history across claims).",
        _items("doc-033"),
    ),
)


def group_findings(
    rows: Sequence[Mapping[str, Any]],
    findings: Sequence[Finding],
    lcd_of: Mapping[str, str],
    counts: Mapping[str, int],
    codes_by_policy: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    """One row per finding with its item IDs, codes and impact (decided dataset lines of those
    codes). Every gap item ("affects decisions" or "rule candidate") must be in exactly one
    finding, and a finding's items must be gap items of its policy and of its kind."""
    gaps = {r["item_id"]: r for r in rows if r["classification"] in GAP_CLASSES}
    seen: Counter[str] = Counter()
    problems: list[str] = []
    out = []
    for f in findings:
        ids = [f"{lcd_of.get(f.policy_id, '?')}-{i}" for i in f.items]
        seen.update(ids)
        expected = "rule candidate" if f.kind == RULE else "affects decisions"
        codes: set[str] = set()
        for item_id in ids:
            row = gaps.get(item_id)
            if row is None or row["policy_id"] != f.policy_id:
                problems.append(f"{f.finding_id}: {item_id} is not a gap item of {f.policy_id}")
                continue
            if row["classification"] != expected:
                problems.append(
                    f"{f.finding_id}: {item_id} is {row['classification']!r}, not {expected!r}"
                )
            codes.update(row["codes"].split() or codes_by_policy.get(f.policy_id, []))
        out.append(
            {
                "finding_id": f.finding_id,
                "policy_id": f.policy_id,
                "kind": f.kind,
                "change": f.change,
                "criteria": " ".join(f.criteria),
                "affected_codes": " ".join(f.codes),
                "items": " ".join(ids),
                "n_items": len(ids),
                "codes": " ".join(sorted(codes)),
                "impact": sum(counts.get(c, 0) for c in codes),
            }
        )
    problems += [f"{i}: in {n} findings" for i, n in seen.items() if n > 1]
    problems += [f"{i}: not in any finding" for i in gaps if i not in seen]
    if problems:
        raise ValueError("findings table: " + "; ".join(sorted(problems)))
    return out


@dataclass(frozen=True)
class DatasetLine:
    split: str
    code: str
    decision: str  # gold line decision
    criteria: Mapping[str, str]  # criterion ID -> gold status
    record_id: str = ""
    diagnoses: tuple[str, ...] = ()  # the line's ICD-10-CM codes (through its diagnosis pointers)
    scenario: str = ""  # the record's generator scenario type


@dataclass
class Usage:
    lines: int = 0  # lines where a finding's criterion has a status other than NOT_APPLICABLE
    on_codes: int = 0  # of those, lines of the codes the contradiction affects
    decisions: Counter[str] = field(default_factory=Counter)  # gold decisions, on_codes lines
    statuses: Counter[str] = field(default_factory=Counter)  # "c2 NOT_MET", on_codes lines


def criterion_usage(finding: Finding, lines: Iterable[DatasetLine]) -> dict[str, Usage]:
    """Per split: the decision-dataset lines that use a WRONG CRITERION finding's criteria."""
    usage = {s: Usage() for s in SPLITS}
    for line in lines:
        used = {
            cid: status
            for cid, status in line.criteria.items()
            if cid in finding.criteria and status != "NOT_APPLICABLE"
        }
        if not used:
            continue
        u = usage[line.split]
        u.lines += 1
        if line.code in finding.codes:
            u.on_codes += 1
            u.decisions[line.decision] += 1
            for cid, status in sorted(used.items()):
                u.statuses[f"{cid.rsplit('.', 1)[1]} {status}"] += 1
    return usage


@dataclass(frozen=True)
class Refinement:
    """The lines of a WRONG CRITERION finding whose label the error could change: lines of the
    affected codes that use the finding's criteria and also meet this condition."""

    condition: str
    # A line diagnosis among the billing article's covered codes whose ICD-10-CM FY2027 description
    # matches (a diagnosis the article does not cover is denied by R15 before the SLM sees it).
    diagnosis_pattern: str = ""
    diagnosis_exclude: str = ""
    statuses: tuple[str, ...] = ()  # a gold status of one of the finding's criteria


REFINEMENTS: dict[str, Refinement] = {
    "POL-SURG-004.F1": Refinement(
        "a congenital ptosis or palsy diagnosis (LCD L33944 items cov-030 and cov-038)",
        diagnosis_pattern=r"congenital ptosis|palsy|paralytic",
    ),
    "POL-DX-003.F1": Refinement(
        "a food-allergy diagnosis on the intradermal test line (LCD L33261 items cov-058 and "
        "cov-080)",
        diagnosis_pattern=r"\b(?:foods?|peanuts|milk|eggs?|shellfish|seafood|tree nuts|mammalian "
        r"meats)\b",
        diagnosis_exclude=r"contact dermatitis|except food",  # contact allergy: patch testing
    ),
    "POL-REHAB-001.F1": Refinement(
        "c2 (plan of care) NOT_MET or NOT_DOCUMENTED on the evaluation line",
        statuses=("NOT_MET", "NOT_DOCUMENTED"),
    ),
    "POL-CAR-002.F1": Refinement("none: every 30-day monitoring line that uses c2 counts"),
}


def diagnosis_codes(
    refinement: Refinement, article_codes: Iterable[str], icd10: Mapping[str, str]
) -> list[str]:
    """The billing article's covered codes whose ICD-10-CM description matches the refinement."""
    return sorted(
        code
        for code in set(article_codes)
        if code in icd10
        and re.search(refinement.diagnosis_pattern, icd10[code], re.IGNORECASE)
        and not (
            refinement.diagnosis_exclude
            and re.search(refinement.diagnosis_exclude, icd10[code], re.IGNORECASE)
        )
    )


@dataclass
class RefinedCounts:
    decisions: dict[str, Counter[str]]  # per split: gold decisions of the lines counted
    supported: dict[str, int]  # per split: of those, lines whose diagnoses satisfy the billing
    # article, so R15 (D-DX-1) would not deny them before the SLM sees them
    scenarios: Counter[str]
    examples: list[str]  # two record IDs, lines with a supported diagnosis first


def refined_usage(
    finding: Finding,
    refinement: Refinement,
    codes: Collection[str],
    lines: Iterable[DatasetLine],
    dx_supported: Callable[[DatasetLine], bool] | None = None,
) -> RefinedCounts:
    """The lines whose label the error could change: lines of the affected codes that use the
    finding's criteria and meet the refinement's condition."""
    counts = RefinedCounts({s: Counter() for s in SPLITS}, dict.fromkeys(SPLITS, 0), Counter(), [])
    records = set()
    for line in lines:
        used = {
            status
            for cid, status in line.criteria.items()
            if cid in finding.criteria and status != "NOT_APPLICABLE"
        }
        if line.code not in finding.codes or not used:
            continue
        if refinement.statuses and not used & set(refinement.statuses):
            continue
        if refinement.diagnosis_pattern and not set(line.diagnoses) & set(codes):
            continue
        supported = dx_supported is None or dx_supported(line)
        counts.decisions[line.split][line.decision] += 1
        counts.supported[line.split] += supported
        counts.scenarios[line.scenario] += 1
        records.add((not supported, SPLITS.index(line.split), line.record_id))
    counts.examples = list(dict.fromkeys(record_id for *_, record_id in sorted(records)))[:2]
    return counts


def billing_article(policy_id: str, directory: Path = POLICIES_DIR) -> str:
    """The policy file's billing_article (front matter), e.g. "A56439"."""
    text = (directory / f"{policy_id}.md").read_text(encoding="utf-8")
    found = re.search(r"^billing_article:\s*(A\d+)\s*$", text, re.MULTILINE)
    return found.group(1) if found else ""


@dataclass(frozen=True)
class Refined:
    refinement: Refinement
    source: str  # where the diagnosis codes come from ("" when the refinement uses none)
    codes: list[str]
    counts: RefinedCounts


def refine_wrong_criteria(
    findings: Sequence[Finding], lines: Sequence[DatasetLine]
) -> dict[str, Refined]:
    """REFINEMENTS applied to the WRONG CRITERION findings. Diagnosis codes come from data/raw/:
    the policy's billing article (current version, covered groups) and ICD-10-CM FY2027. Whether
    a line's diagnoses satisfy its code's article rule uses the V1a check (label_checks)."""
    from app.db.curated import load_curated
    from app.db.raw import read_article_diagnoses, read_icd10_codes
    from scripts.verify.label_checks import Support, supported

    icd10 = read_icd10_codes()
    support = {
        code: Support(s.billing_article, s.alternatives)
        for code, s in load_curated().diagnosis_support.items()
    }
    articles = read_article_diagnoses({s.article for s in support.values()})
    covered_by_article = {a: dict(d.covered) for a, d in articles.items()}

    def dx_supported(line: DatasetLine) -> bool:
        rule = support.get(line.code)
        return rule is None or supported(line.diagnoses, rule, covered_by_article)

    out = {}
    for f in findings:
        refinement = REFINEMENTS[f.finding_id]
        source, codes = "", []
        if refinement.diagnosis_pattern:
            article_id = billing_article(f.policy_id)
            article = articles.get(article_id) or read_article_diagnoses({article_id})[article_id]
            covered = {c for group in article.covered.values() for c in group}
            codes = diagnosis_codes(refinement, covered, icd10)
            source = (
                f"billing article {article_id} v{article.version} covered codes whose ICD-10-CM "
                f"FY2027 description matches /{refinement.diagnosis_pattern}/"
                + (
                    f" but not /{refinement.diagnosis_exclude}/"
                    if refinement.diagnosis_exclude
                    else ""
                )
            )
        counts = refined_usage(f, refinement, set(codes), lines, dx_supported)
        out[f.finding_id] = Refined(refinement, source, codes, counts)
    return out


def fill_sitting(
    required: Sequence[Any], optional: Sequence[Any], minutes: Any, budget: int = SITTING_MINUTES
) -> tuple[list[Any], list[Any], int]:
    """(shown, left, minutes): every required row, then optional rows in their order while the
    estimated time stays within the budget. Stops at the first row that does not fit, so a later
    (lower-impact) row never jumps ahead of it."""
    shown = list(required)
    total = sum(minutes(r) for r in shown)
    left = list(optional)
    while left and total + minutes(left[0]) <= budget:
        total += minutes(left[0])
        shown.append(left.pop(0))
    return shown, left, total


def finding_minutes(n_items: int) -> int:
    return MINUTES_PER_ROW + math.ceil((n_items - 1) / ITEMS_PER_EXTRA_MINUTE)


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


def dataset_lines(directory: Path = DATASET_DIR) -> list[DatasetLine]:
    """Every labelled line of the decision dataset: its code, gold decision, the gold criterion
    statuses in the target, its record and its diagnoses."""
    out = []
    for split in SPLITS:
        inputs = {}
        with (directory / f"{split}_inputs.jsonl").open(encoding="utf-8") as f:
            for line in f:
                i = json.loads(line)
                inputs[i["record_id"]] = i
        with (directory / f"{split}.jsonl").open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                record_id = r["metadata"]["record_id"]
                claim = inputs[record_id]["claim"]
                letters = {chr(ord("A") + k): d for k, d in enumerate(claim["diagnoses"])}
                service = {s["line_no"]: s for s in claim["service_lines"]}
                target = {
                    t["line_no"]: t for t in json.loads(r["messages"][-1]["content"])["lines"]
                }
                for label in r["metadata"]["line_labels"]:
                    n = label["line_no"]
                    statuses = {
                        c["criterion_id"]: c["status"]
                        for c in target.get(n, {}).get("criteria", [])
                    }
                    diagnoses = tuple(
                        letters[p] for p in service[n]["diagnosis_pointers"] if p in letters
                    )
                    out.append(
                        DatasetLine(
                            split,
                            service[n]["procedure_code"],
                            label["decision"],
                            statuses,
                            record_id,
                            diagnoses,
                            r["metadata"].get("scenario_type", ""),
                        )
                    )
    return out


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
        help=f"add the judgments in CSV to {CLASSIFICATION_CSV.relative_to(ROOT)}, replacing "
        "any for the same items",
    )
    parser.add_argument(
        "--force", action="store_true", help="allow --save-judgments to rewrite saved judgments"
    )
    args = parser.parse_args()
    if args.save_judgments:
        with args.save_judgments.open(encoding="utf-8", newline="") as f:
            new = [Judgment(**{k: r[k] for k in JUDGMENT_FIELDS}) for r in csv.DictReader(f)]
        existing = read_judgments()
        merged = merge_judgments(existing, new)
        try:
            n = save_judgments(merged, force=args.force)
        except JudgmentsExist as exc:
            raise SystemExit(str(exc)) from exc
        replaced = sum(j.item_id in existing for j in new)
        print(
            f"saved {n} judgments to {CLASSIFICATION_CSV} "
            f"({len(existing)} before; {replaced} replaced, {len(new) - replaced} added)"
        )
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


def _composite_only(flags: str) -> bool:
    parts = [f for f in flags.split("; ") if f]
    return bool(parts) and all(f.startswith("composite") for f in parts)


def _counts(counter: Counter[str]) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(counter.items())) or "-"


def write_reports(criteria, lcds, out, queue_only: bool = False) -> None:  # noqa: ANN001
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
    lines = dataset_lines()
    counts = Counter(line.code for line in lines)
    rows, queue = [], []
    overridden = 0
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
        judgment = judgments.get(i.item_id)
        result = classify(mapping[i.item_id], judgment, rule, needs_judgment)
        if result is None:
            continue  # waiting for a judgment
        classification, reason, by, codes = result
        if not mapping[i.item_id] and not needs_judgment and judgment is not None:
            overridden += 1  # a saved judgment replaced the keyword rule's classification
        row = {
            **base,
            "mapping": "; ".join(mapping[i.item_id])
            if mapping[i.item_id]
            else ""
            if classification.startswith(("covered by", "already decided"))
            else "NOT IN POLICY",
            "classification": classification,
            "reason": reason,
            "by": by,
            "rule_hit": rule[0] if rule else "",
            "codes": codes,
        }
        row["impact"] = sum(
            counts[c] for c in (codes.split() or codes_by_policy.get(i.policy_id, []))
        )
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
        f"{sum(q['judged'] == 'no' for q in queue)}; saved judgments overriding a keyword rule "
        f"{overridden}"
    )
    if queue_only or any(q["judged"] == "no" for q in queue):
        return

    # findings (raises when a gap item is in no finding or in two)
    finding_rows = group_findings(rows, FINDINGS, policy_lcd, counts, codes_by_policy)
    finding_of = {item_id: f["finding_id"] for f in finding_rows for item_id in f["items"].split()}
    for r in rows:
        r["finding"] = finding_of.get(r["item_id"], "")
    usage = {f.finding_id: (f, criterion_usage(f, lines)) for f in FINDINGS if f.kind == WRONG}
    refined = refine_wrong_criteria([f for f, _ in usage.values()], lines)

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
        "rule_hit",
        "finding",
        "codes",
        "impact",
        "closest_criterion",
        "closest_similarity",
        "descriptors_omitted",
    ]
    _write_csv(out / "B_completeness_full.csv", rows, full_fields)
    usage_rows = [
        {
            "finding_id": fid,
            "criteria": " ".join(f.criteria),
            "affected_codes": " ".join(f.codes),
            "split": split,
            "lines_using_criteria": u.lines,
            "lines_on_affected_codes": u.on_codes,
            "gold_decisions": _counts(u.decisions),
            "criterion_statuses": _counts(u.statuses),
            "refined_condition": refined[fid].refinement.condition,
            "refined_diagnosis_source": refined[fid].source,
            "refined_diagnosis_codes": " ".join(refined[fid].codes),
            "refined_lines": sum(refined[fid].counts.decisions[split].values()),
            "refined_gold_decisions": _counts(refined[fid].counts.decisions[split]),
            "refined_lines_dx_supported": refined[fid].counts.supported[split],
            "refined_scenarios_all_splits": _counts(refined[fid].counts.scenarios),
            "refined_examples": " ".join(refined[fid].counts.examples),
        }
        for fid, (f, by_split) in sorted(usage.items())
        for split, u in by_split.items()
    ]
    _write_csv(out / "B_wrong_criterion_lines.csv", usage_rows, list(usage_rows[0]))

    # sitting 1: part 1
    rng = random.Random(SEED)
    flagged = sorted(
        (r for r in part1_rows if r["status"] == "flagged"),
        key=lambda r: (_severity(r["flags"].split("; ")), r["criterion_id"]),
    )
    composite_only = [r for r in flagged if _composite_only(r["flags"])]
    samples = rng.sample(composite_only, min(2, len(composite_only)))
    decided_rows = [r for r in part1_rows if r["policy_id"] == ALREADY_DECIDED_POLICY]
    unflagged = [r for r in part1_rows if not r["flags"] and r not in decided_rows]
    controls1 = rng.sample(unflagged, min(2, len(unflagged)))
    sitting1 = [
        *[{**r, "why": f"flagged: {r['flags']}"} for r in flagged if r not in composite_only],
        *[
            {**r, "why": f"sample of {len(composite_only)} composite-only flags: {r['flags']}"}
            for r in samples
        ],
        *[{**r, "why": "control (not flagged)"} for r in controls1],
    ]
    minutes1 = MINUTES_PER_ROW * len(sitting1)
    decided_part1 = sum(r["status"].startswith("already") for r in part1_rows)

    # sitting 2: findings
    def by_impact(f: Mapping[str, Any]) -> tuple[int, str]:
        return -f["impact"], f["finding_id"]

    wrong = sorted((f for f in finding_rows if f["kind"] == WRONG), key=by_impact)
    rest = sorted((f for f in finding_rows if f["kind"] != WRONG), key=by_impact)
    rule_out = [r for r in rows if r["by"] == "rule" and r["classification"] == "out of scope"]
    controls2 = rng.sample(rule_out, min(3, len(rule_out)))

    def minutes2(entry: Mapping[str, Any]) -> int:
        return finding_minutes(entry["n_items"]) if "finding_id" in entry else MINUTES_PER_ROW

    shown2, left2, minutes_2 = fill_sitting([*wrong, *controls2], rest, minutes2)
    sitting2 = [*wrong, *shown2[len(wrong) + len(controls2) :], *controls2]
    in_review = {f["finding_id"] for f in sitting2 if "finding_id" in f}
    for f in finding_rows:
        f["in_review"] = "sitting 2" if f["finding_id"] in in_review else "full CSV only"
    _write_csv(out / "B_findings_full.csv", finding_rows, list(finding_rows[0]))

    # review sheet
    self_line, self_ok = self_test()
    flag_counts = Counter(
        f.split(" (")[0].split(" <")[0].split(" 0")[0] for r in part1 for f in r.flags
    )
    classes = Counter(r["classification"] for r in rows)
    by = Counter(r["by"] for r in rows)
    kinds = Counter(f["kind"] for f in finding_rows)
    covered = sum(v for k, v in classes.items() if k.startswith("covered by"))
    decided = sum(v for k, v in classes.items() if k.startswith("already decided"))
    dist = sorted(meaning.values())
    gap_items = sum(f["n_items"] for f in finding_rows)
    left_items = sum(f["n_items"] for f in left2)
    row_of = {r["item_id"]: r for r in rows}
    text_of = {cid: c.text for cid, c in criteria.items()}
    lines_out = [
        "# Policy source and completeness check (Task V1b): review sheet",
        "",
        f"For one reviewer, in two sittings of about {SITTING_MINUTES} minutes each. Sitting 1 "
        f"verdicts: {PART1_VERDICTS}. Sitting 2 verdicts: {PART2_VERDICTS}.",
        "",
        f"- **{INDEPENDENCE}**",
        f"- **Only in the full CSVs.** Part 1: {len(part1_rows) - len(sitting1)} of "
        f"{len(part1_rows)} criteria are only in B_policy_sources_full.csv "
        f"({len(composite_only) - len(samples)} composite-only flags not sampled, "
        f"{len(unflagged) - len(controls1)} unflagged criteria, and the {len(decided_rows)} "
        f"{ALREADY_DECIDED_POLICY} criteria, whose {decided_part1} flags were decided in V1a). "
        f"Part 2: {len(left2)} of {len(finding_rows)} findings ({left_items} LCD items) are only "
        f"in B_findings_full.csv, and the {len(rows) - gap_items} items that are in no finding "
        f"(mapped, covered, already decided or out of scope), apart from the {len(controls2)} "
        "controls, are only in B_completeness_full.csv.",
        f"- Criteria: {len(part1)}; flagged: {len(flagged) + decided_part1} "
        f"({', '.join(f'{k} {v}' for k, v in sorted(flag_counts.items()))}); composite-only: "
        f"{len(composite_only)}; POL-PAIN-001 flags already decided (D-ESI-1 to D-ESI-7), not "
        f"reviewed again: {decided_part1}.",
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
        f"judgment: {by['judgment']}, of which {overridden} replace a keyword rule that misfired. "
        f"Unmapped items at least {t_para:.3f} similar to a criterion (5th percentile of mapped "
        "items) were judged by hand before any rule.",
        f"- Findings: {len(finding_rows)} ({', '.join(f'{k} {kinds[k]}' for k in FINDING_KINDS)})"
        f", holding all {gap_items} items classified as affecting decisions or rule candidates, "
        "each in exactly one finding. Impact = dataset lines (all splits) of the finding's codes.",
        f"- AMA CPT descriptor text: excerpts containing it {len(leaked)}; displayed items with it "
        f"replaced by {DESCRIPTOR_OMITTED}: {sum(1 for r in rows if r['descriptors_omitted'])}.",
        f"- Estimated time: sitting 1 {minutes1} minutes ({len(sitting1)} rows, "
        f"{MINUTES_PER_ROW} minutes each); sitting 2 {minutes_2} minutes ({MINUTES_PER_ROW} "
        f"minutes per finding plus 1 per {ITEMS_PER_EXTRA_MINUTE} LCD items after the first; "
        f"{MINUTES_PER_ROW} per control).",
        "",
        f"## Sitting 1: source check (Part 1), about {minutes1} minutes",
        "",
        "Does the source text say what our criterion says? Write "
        f"{PART1_VERDICTS}. POL-PAIN-001 is left out (decided in V1a).",
        "",
        "| # | Criterion ID (why shown) | Our criterion text | Source file | Source text found (or "
        "NOT FOUND) | Similarity | Differing values | Your verdict | Notes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for n, r in enumerate(sitting1, start=1):
        lines_out.append(
            f"| {n} | {_cell(r['criterion_id'] + ' (' + r['why'] + ')')} | "
            f"{_cell(r['criterion_text'])} | {_cell(r['source_file'])} | "
            f"{_cell(r['source_text'])} | {r['similarity']} | "
            f"{_cell(r['differing_values'] or '-')} |  |  |"
        )
    lines_out += [
        "",
        f"## Sitting 2: completeness findings (Part 2), about {minutes_2} minutes",
        "",
        "Each finding is one proposed v2 change to one policy, with the LCD items behind it. "
        f"Write {PART2_VERDICTS}. WRONG CRITERION findings come first, then the others by impact; "
        f"the last {len(controls2)} entries are controls (items a keyword rule classified as out "
        "of scope: write ADD IN V2 if one should change a policy).",
        "",
        "Decision-dataset lines that use each WRONG CRITERION finding's criteria (status other "
        "than NOT_APPLICABLE in the gold target), report only:",
        "",
        "| Finding | Criteria | Affected codes | Split | Lines using the criteria "
        "| On affected codes | Gold decisions (affected codes) "
        "| Criterion status (affected codes) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for u in usage_rows:
        lines_out.append(
            f"| {u['finding_id']} | {u['criteria']} | {u['affected_codes']} | {u['split']} | "
            f"{u['lines_using_criteria']} | {u['lines_on_affected_codes']} | "
            f"{u['gold_decisions']} | {u['criterion_statuses']} |"
        )
    lines_out += [
        "",
        "Refined: only the lines where the error could change the label, i.e. lines of the "
        "affected codes that use the criteria and also meet the condition below (gold decisions; "
        'report only). "R15 would not deny first" counts the lines whose diagnoses satisfy the '
        "billing article (the V1a check); the others are diagnosis mismatches that R15 (D-DX-1) "
        "denies before the SLM sees them. Example records show those lines first.",
        "",
        "| Finding | Condition | Train | Validation | Test | R15 would not deny first "
        "(train / validation / test) | Scenario types | Example records |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fid, r in sorted(refined.items()):
        c = r.counts
        cells = [
            f"{sum(c.decisions[s].values())} ({_counts(c.decisions[s])})" if c.decisions[s] else "0"
            for s in SPLITS
        ]
        lines_out.append(
            f"| {fid} | {_cell(r.refinement.condition)} | {' | '.join(cells)} | "
            f"{' / '.join(str(c.supported[s]) for s in SPLITS)} | {_counts(c.scenarios)} | "
            f"{', '.join(c.examples) or 'none'} |"
        )
    lines_out += ["", "Diagnosis codes used (ICD-10-CM, no dots):", ""]
    lines_out += [
        f"- {fid}: {' '.join(r.codes) or 'none'} ({r.source})"
        for fid, r in sorted(refined.items())
        if r.source
    ]
    for n, entry in enumerate(sitting2, start=1):
        lines_out.append("")
        if "finding_id" in entry:
            lines_out += [
                f"### {n}. {entry['finding_id']}: {entry['kind']} (impact {entry['impact']} "
                f"lines; about {finding_minutes(entry['n_items'])} minutes)",
                "",
                f"**Proposed v2 change:** {entry['change']}",
                "",
            ]
            if entry["kind"] == WRONG:
                for cid in entry["criteria"].split():
                    lines_out += [f"**Our criterion now:** {cid}: {text_of[cid]}", ""]
                lines_out += [f"Affected codes: {entry['affected_codes']}.", ""]
            first = row_of[entry["items"].split()[0]]
            lines_out.append(f"LCD {first['lcd']} items, word for word:")
            lines_out.append("")
            for item_id in entry["items"].split():
                r = row_of[item_id]
                lines_out.append(
                    f"- `{item_id}` ({r['field']}; {r['section'] or '(top)'}): {r['text']}"
                )
        else:
            lines_out += [
                f"### {n}. Control: {entry['item_id']} ({entry['policy_id']})",
                "",
                f"Classified out of scope by a keyword rule: {entry['reason']}.",
                "",
                f"- `{entry['item_id']}` ({entry['field']}; {entry['section'] or '(top)'}): "
                f"{entry['text']}",
            ]
        lines_out += ["", f"Your verdict ({PART2_VERDICTS}):", "", "Notes:"]
    (out / "B_policy_sources_review.md").write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(
        f"findings {len(finding_rows)} ({_counts(kinds)}); sitting 1: {len(sitting1)} rows, "
        f"{minutes1} min; sitting 2: {len(sitting2)} entries, {minutes_2} min; only in full CSVs: "
        f"{len(left2)} findings; {self_line}"
    )
    if not self_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
