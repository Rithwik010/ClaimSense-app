"""Task V1d: write the reviewer's verdicts into the V1 review sheets, tally them, keep copies.

Report only: no data, label, policy or generator is changed. The verdicts below are the
reviewer's (Manideep3183, 2026-10-02), entered word for word. Only verdict, status and notes cells
are written; a cell that already holds a different value keeps the file's value and is reported as
a conflict, and running the script again changes nothing. The tally (D_summary.md) is read back
from the filled sheets. The three sheets and the summary are then copied to
data/verification/reviews/ (tracked), after a check that they hold no AMA CPT descriptor text.

    uv run python -m scripts.verify.review_verdicts
"""

import re
import shutil
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHEETS_DIR = ROOT / "data" / "generated" / "verification"
COPIES_DIR = ROOT / "data" / "verification" / "reviews"
SUMMARY = "D_summary.md"
PIPE = re.compile(r"(?<!\\)\|")  # a cell border; "\|" inside a cell is text
ENTRY = re.compile(r"^### (\d+)\. (.*)$")
VERDICT_LINE = "Your verdict ("
NOTES_LINE = "Notes:"

FREE: frozenset[str] = frozenset()  # free text
A_WORDS = frozenset({"REAL ERROR", "FALSE ALARM", "UNSURE"})
B1_WORDS = frozenset({"MATCHES", "DIFFERENT MEANING", "NOT IN SOURCE", "UNSURE"})
B2_WORDS = frozenset({"ADD IN V2", "NOT NEEDED", "UNSURE"})
STATUS_WORDS = frozenset({"MET", "NOT_MET", "NOT_DOCUMENTED", "NOT_APPLICABLE", "UNSURE"})
C_WORDS = frozenset({"LABEL RIGHT", "MODEL RIGHT", "BOTH WRONG", "UNSURE"})


@dataclass(frozen=True)
class TableVerdicts:
    """Values for named columns of the rows of "#"-numbered tables; "" leaves a cell alone."""

    columns: tuple[str, ...]
    rows: Mapping[int, tuple[str, ...]]
    allowed: tuple[frozenset[str], ...] = ()  # per column; an empty set means free text


@dataclass(frozen=True)
class BlockVerdicts:
    """(verdict, notes) for the "### N." entries."""

    rows: Mapping[int, tuple[str, str]]
    allowed: tuple[frozenset[str], ...] = ()


@dataclass(frozen=True)
class Review:
    file: str
    how: str  # how the verdicts were reached
    table: TableVerdicts | None = None
    blocks: BlockVerdicts | None = None


SAME_AS_ROW_2 = "same as row 2"
SAME_AS_ROW_9 = "same as row 9"
REVIEWS = (
    Review(
        "A_labels_review.md",
        "verdicts decided with Claude's help during V1a",
        table=TableVerdicts(
            ("Your verdict", "Notes"),
            {
                1: (
                    "REAL ERROR",
                    "c2 applies to repeats (LCD L33906, D-ESI-1); no baseline score; no prior "
                    "relief stated, so c5 not documented",
                ),
                2: (
                    "REAL ERROR",
                    "c2 applies to repeats (D-ESI-1); no baseline score; line should be PEND",
                ),
                3: ("REAL ERROR", SAME_AS_ROW_2),
                4: ("REAL ERROR", SAME_AS_ROW_2),
                5: (
                    "REAL ERROR",
                    "c2 applies to repeats (D-ESI-1); no baseline score and no prior relief stated",
                ),
            },
            (A_WORDS, FREE),
        ),
    ),
    Review(
        "B_policy_sources_review.md",
        "verdicts suggested by Claude and accepted by the reviewer",
        table=TableVerdicts(
            ("Your verdict", "Notes"),
            {
                1: ("MATCHES", "physician evaluation before ordering; fair reading"),
                2: (
                    "DIFFERENT MEANING",
                    "LCD list is for 48-hour recording only; criterion has no duration scope",
                ),
                3: (
                    "DIFFERENT MEANING",
                    "infrequent-symptom condition is for event monitors up to 15 days, not 30-day "
                    "monitoring; rule candidate: no other ECG monitoring code billed at the same "
                    "time",
                ),
                4: (
                    "DIFFERENT MEANING",
                    "drops the LCD's documented-exception clause to the 2-week wait",
                ),
                5: (
                    "MATCHES",
                    "drops one example (negative stool cultures >3 weeks); missing indications "
                    "are SURG-002.F1",
                ),
                6: (
                    "DIFFERENT MEANING",
                    "drops the >2 cm sessile adenoma threshold, the 3-6 month and 1-2 year "
                    "intervals (D-RULE-1) and the rectosigmoid exclusion",
                ),
                7: (
                    "NOT IN SOURCE",
                    "LCD only points to Benefit Policy Manual Ch. 15 §290, which is not in our "
                    "sources",
                ),
                8: ("MATCHES", "less specific; evaluation exception is F1, certification is F2"),
                9: ("MATCHES", "congenital/palsy exemption is F1"),
                10: (
                    "MATCHES",
                    '"eyelid surgery" is broader than "blepharoplasty"; reconstructive cases '
                    "are F1",
                ),
                11: (
                    "MATCHES",
                    "provider accreditation is not on claims; remove it from model criteria in v2",
                ),
                12: (
                    "UNSURE",
                    "high-blood-pressure exclusion matches; the coverage part needs L37379's "
                    "indication list",
                ),
                13: ("MATCHES", "control OK"),
                14: ("MATCHES", "control OK"),
            },
            (B1_WORDS, FREE),
        ),
        blocks=BlockVerdicts(
            {
                1: ("ADD IN V2", "0 v1 lines affected"),
                2: ("ADD IN V2", "0 v1 lines affected"),
                3: ("ADD IN V2", "6 v1 labels affected"),
                4: ("ADD IN V2", "also scope CAR-002.c1 by duration"),
                5: (
                    "ADD IN V2",
                    "firm rule only: no continuing care without improvement; revise the plan if "
                    "healing is not documented after 30 days",
                ),
                6: (
                    "NOT NEEDED",
                    "unrealistic in our claims; would mostly add NOT_APPLICABLE labels",
                ),
                7: (
                    "ADD IN V2",
                    "criteria must not be narrower than the billing article's covered diagnoses",
                ),
                8: (
                    "ADD IN V2",
                    "only the limitations diagnosis codes cannot catch; skip those R15 denies",
                ),
                9: (
                    "ADD IN V2",
                    "physician/NPP care and plan certification, for treatment lines only",
                ),
                10: ("NOT NEEDED", "control OK"),
                11: ("NOT NEEDED", "control OK"),
                12: ("NOT NEEDED", "control OK"),
            },
            (B2_WORDS, FREE),
        ),
    ),
    Review(
        "C_disagreements_review.md",
        "statuses are Claude's reading, accepted by the reviewer (not a blind review)",
        table=TableVerdicts(
            ("My status", "Who is right?", "Notes"),
            {
                1: (
                    "NOT_APPLICABLE",
                    "MODEL RIGHT",
                    "ultrasound is for a soft-tissue mass, not plantar fasciitis",
                ),
                2: ("MET", "LABEL RIGHT", "effusion vs cyst is a listed indication"),
                3: ("NOT_MET", "LABEL RIGHT", '"Std panel run, not tied to hx"'),
                4: (
                    "NOT_DOCUMENTED",
                    "UNSURE",
                    "depends on the line's diagnosis, which the sheet does not show",
                ),
                5: (
                    "MET",
                    "LABEL RIGHT",
                    '"43 allergens selected per exposure hx", within the 80 patch-test limit',
                ),
                6: (
                    "UNSURE",
                    "UNSURE",
                    'notes contradict: "exertional chest tightness" vs "No CP/SOB; stress echo '
                    'as routine screen"',
                ),
                7: ("NOT_MET", "LABEL RIGHT", '"Onset 3wk ago; no PT tried"'),
                8: ("MET", "LABEL RIGHT", "effusion vs cyst is a listed indication"),
                9: (
                    "NOT_APPLICABLE",
                    "MODEL RIGHT",
                    "exclusion criterion: the written NOT_APPLICABLE definition fits; gold MET "
                    "follows a different convention",
                ),
                10: ("NOT_APPLICABLE", "MODEL RIGHT", SAME_AS_ROW_9),
                11: (
                    "UNSURE",
                    "UNSURE",
                    "exclusion criterion: complaints documented, but visual-field loss only 5 "
                    "degrees (<12)",
                ),
                12: ("NOT_APPLICABLE", "MODEL RIGHT", SAME_AS_ROW_9),
            },
            (STATUS_WORDS, C_WORDS, FREE),
        ),
    ),
)

Conflict = tuple[str, str, str, str]  # (row or entry, column, file's value, recorded value)


# --- filling ----------------------------------------------------------------------------------


def fill_table(
    lines: Sequence[str], verdicts: TableVerdicts
) -> tuple[list[str], list[Conflict], int]:
    """(lines, conflicts, cells written). Writes the named columns of the rows of every table
    whose header starts with "#" and has those columns; every other character of the line stays
    as it was. A row named in `verdicts` must appear exactly once."""
    out = list(lines)
    found: Counter[int] = Counter()
    conflicts: list[Conflict] = []
    written = 0
    columns: dict[str, int] | None = None
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            columns = None
            continue
        parts = PIPE.split(line)
        cells = [c.strip() for c in parts[1:-1]]
        if cells and cells[0] == "#":
            columns = (
                {name: k for k, name in enumerate(cells)}
                if all(c in cells for c in verdicts.columns)
                else None
            )
            continue
        if columns is None or not cells or not cells[0].isdigit():
            continue
        number = int(cells[0])
        if number not in verdicts.rows:
            continue
        found[number] += 1
        for name, value in zip(verdicts.columns, verdicts.rows[number], strict=True):
            current = cells[columns[name]]
            if not value or current == value:
                continue
            if current:
                conflicts.append((f"row {number}", name, current, value))
                continue
            parts[columns[name] + 1] = f" {value} "
            written += 1
        out[i] = "|".join(parts)
    problems = [f"row {n} not found" for n in sorted(set(verdicts.rows) - set(found))]
    problems += [f"row {n} found {c} times" for n, c in sorted(found.items()) if c > 1]
    if problems:
        raise ValueError("; ".join(problems))
    return out, conflicts, written


def fill_blocks(
    lines: Sequence[str], verdicts: BlockVerdicts
) -> tuple[list[str], list[Conflict], int]:
    """(lines, conflicts, lines written). Completes the first "Your verdict (...):" line and the
    first "Notes:" line of each "### N." entry named in `verdicts`."""
    out = list(lines)
    conflicts: list[Conflict] = []
    written = 0
    current: int | None = None
    done: set[tuple[int, str]] = set()
    for i, line in enumerate(lines):
        entry = ENTRY.match(line)
        if entry:
            current = int(entry.group(1))
            continue
        if current not in verdicts.rows:
            continue
        if line.startswith(VERDICT_LINE) and "):" in line and (current, "verdict") not in done:
            head, _, rest = line.partition("):")
            prefix, field, value = head + "):", "Your verdict", verdicts.rows[current][0]
            done.add((current, "verdict"))
        elif line.startswith(NOTES_LINE) and (current, "notes") not in done:
            prefix, rest = NOTES_LINE, line[len(NOTES_LINE) :]
            field, value = "Notes", verdicts.rows[current][1]
            done.add((current, "notes"))
        else:
            continue
        existing = rest.strip()
        if not value or existing == value:
            continue
        if existing:
            conflicts.append((f"entry {current}", field, existing, value))
            continue
        out[i] = f"{prefix} {value}"
        written += 1
    missing = [
        f"entry {n} has no {part} line"
        for n in sorted(verdicts.rows)
        for part in ("verdict", "notes")
        if (n, part) not in done
    ]
    if missing:
        raise ValueError("; ".join(missing))
    return out, conflicts, written


# --- reading back -----------------------------------------------------------------------------


def read_tables(lines: Sequence[str]) -> list[tuple[str, list[dict[str, str]]]]:
    """(heading, rows) of each table whose header starts with "#"; the heading is the nearest
    "## " heading above it, else the "# " title. Rows map header names to cell text."""
    tables: list[tuple[str, list[dict[str, str]]]] = []
    heading = ""
    header: list[str] | None = None
    for line in lines:
        if line.startswith("# ") and not heading:
            heading = line[2:].strip()
        elif line.startswith("## "):
            heading = line[3:].strip()
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in PIPE.split(line)[1:-1]]
        if cells and cells[0] == "#":
            header = cells
            tables.append((heading, []))
        elif header is not None and cells and cells[0].isdigit():
            tables[-1][1].append(dict(zip(header, cells, strict=True)))
    return tables


@dataclass(frozen=True)
class Entry:
    number: int
    title: str
    verdict: str
    notes: str


def read_blocks(lines: Sequence[str]) -> list[Entry]:
    """The "### N." entries with the text after their first verdict and notes lines."""
    entries: list[dict[str, str | int]] = []
    for line in lines:
        found = ENTRY.match(line)
        if found:
            entries.append({"number": int(found.group(1)), "title": found.group(2).strip()})
        elif entries and line.startswith(VERDICT_LINE) and "verdict" not in entries[-1]:
            entries[-1]["verdict"] = line.partition("):")[2].strip()
        elif entries and line.startswith(NOTES_LINE) and "notes" not in entries[-1]:
            entries[-1]["notes"] = line[len(NOTES_LINE) :].strip()
    return [
        Entry(int(e["number"]), str(e["title"]), str(e.get("verdict", "")), str(e.get("notes", "")))
        for e in entries
    ]


# --- summary ----------------------------------------------------------------------------------


def _counts(values: Sequence[str]) -> str:
    return ", ".join(f"{v} {n}" for v, n in Counter(values).most_common()) or "-"


def _short(heading: str) -> str:
    return re.sub(r"(: review sheet|, about \d+ minutes)$", "", heading)


def _untimed(title: str) -> str:
    """An entry title without its "(impact N lines; about N minutes)" tail."""
    return re.sub(r" \(impact [^)]*\)$", "", title)


def summarize(sheets: Mapping[str, Sequence[str]], reviews: Sequence[Review] = REVIEWS) -> str:
    a_file, b_file, c_file = (r.file for r in reviews)
    (a_heading, a_rows), *_ = read_tables(sheets[a_file])
    (b_heading, b_rows), *_ = read_tables(sheets[b_file])
    b_entries = read_blocks(sheets[b_file])
    c_tables = read_tables(sheets[c_file])
    c_rows = [row for _, rows in c_tables for row in rows]

    def a_id(row: Mapping[str, str]) -> str:
        return f"{row['Record ID']}, {row['What was flagged'].split()[0]}"

    def b_id(row: Mapping[str, str]) -> str:
        return row["Criterion ID (why shown)"].split()[0]

    def c_id(row: Mapping[str, str]) -> str:
        return f"{row['Record ID']}, {row['Criterion ID']}"

    lines = [
        "# V1 review verdicts: summary (Task V1d)",
        "",
        "Verdicts by Manideep3183, entered 2026-10-02. The filled sheets are in "
        "`data/verification/reviews/`; this summary is read back from them by "
        "`scripts/verify/review_verdicts.py`. How each review was done:",
        "",
        *[f"- {r.file}: {r.how}." for r in reviews],
        "",
        "## Verdict counts",
        "",
        "| Sheet | Table | Rows | Verdicts |",
        "|---|---|---|---|",
        f"| {a_file} | {_short(a_heading)} | {len(a_rows)} | "
        f"{_counts([r['Your verdict'] for r in a_rows])} |",
        f"| {b_file} | {_short(b_heading)} | {len(b_rows)} | "
        f"{_counts([r['Your verdict'] for r in b_rows])} |",
        f"| {b_file} | Sitting 2: completeness findings | {len(b_entries)} | "
        f"{_counts([e.verdict for e in b_entries])} |",
        *[
            f"| {c_file} | {_short(heading)} | {len(rows)} | "
            f"{_counts([r['Who is right?'] for r in rows])} |"
            for heading, rows in c_tables
        ],
        "",
        f"{c_file} by error type (gold -> model):",
        "",
        "| Error type | Rows | LABEL RIGHT | MODEL RIGHT | BOTH WRONG | UNSURE |",
        "|---|---|---|---|---|---|",
    ]
    by_type: dict[str, list[str]] = {}
    for row in c_rows:
        by_type.setdefault(f"{row['Gold status']} -> {row['Model status']}", []).append(
            row["Who is right?"]
        )
    for error_type, verdicts in by_type.items():
        counted = Counter(verdicts)
        lines.append(
            f"| {error_type} | {len(verdicts)} | {counted['LABEL RIGHT']} | "
            f"{counted['MODEL RIGHT']} | {counted['BOTH WRONG']} | {counted['UNSURE']} |"
        )
    lines += [
        "",
        "## Rows that are not MATCHES or LABEL RIGHT",
        "",
        f"{a_file} (verdicts other than FALSE ALARM):",
        "",
        *[
            f"- Row {r['#']}, {a_id(r)}: {r['Your verdict']}. {r['Notes']}"
            for r in a_rows
            if r["Your verdict"] != "FALSE ALARM"
        ],
        "",
        f"{b_file}, sitting 1 (verdicts other than MATCHES):",
        "",
        *[
            f"- Row {r['#']}, {b_id(r)}: {r['Your verdict']}. {r['Notes']}"
            for r in b_rows
            if r["Your verdict"] != "MATCHES"
        ],
        "",
        f"{b_file}, sitting 2 (every entry; its verdicts are decisions, not matches):",
        "",
        *[f"- {e.number}. {_untimed(e.title)}: {e.verdict}. {e.notes}" for e in b_entries],
        "",
        f"{c_file} (verdicts other than LABEL RIGHT):",
        "",
        *[
            f"- Row {r['#']}, {c_id(r)}, gold {r['Gold status']}, model {r['Model status']}: "
            f"{r['Who is right?']} (reviewer's status {r['My status']}). {r['Notes']}"
            for r in c_rows
            if r["Who is right?"] != "LABEL RIGHT"
        ],
        "",
        "## Controls",
        "",
    ]
    b_controls = [r for r in b_rows if "(control" in r["Criterion ID (why shown)"]]
    entry_controls = [e for e in b_entries if e.title.startswith("Control:")]
    lines += [
        f"- {b_file}, sitting 1, unflagged criteria (expected MATCHES): "
        + "; ".join(f"row {r['#']} {b_id(r)} {r['Your verdict']}" for r in b_controls)
        + (
            " - as expected."
            if all(r["Your verdict"] == "MATCHES" for r in b_controls)
            else " - NOT as expected."
        ),
        f"- {b_file}, sitting 2, items a keyword rule put out of scope (expected NOT NEEDED): "
        + "; ".join(f"entry {e.number} {e.verdict}" for e in entry_controls)
        + (
            " - as expected."
            if all(e.verdict == "NOT NEEDED" for e in entry_controls)
            else " - NOT as expected."
        ),
        f"- {a_file} and {c_file} have no controls.",
        "",
        "## Known limitations (UNSURE)",
        "",
        "These keep their current labels (D-LIM-1):",
        "",
        *[
            f"- {b_file}, sitting 1 row {r['#']}, {b_id(r)}: {r['Notes']}"
            for r in b_rows
            if r["Your verdict"] == "UNSURE"
        ],
        *[
            f"- {c_file} row {r['#']}, {c_id(r)} (gold {r['Gold status']}, model "
            f"{r['Model status']}): {r['Notes']}"
            for r in c_rows
            if "UNSURE" in (r["Who is right?"], r["My status"])
        ],
    ]
    return "\n".join(lines) + "\n"


# --- run --------------------------------------------------------------------------------------


def check_descriptors(paths: Sequence[Path]) -> int:
    """Stop before copying if a sheet holds AMA CPT descriptor text (the V1b list). Returns the
    number of descriptor texts checked."""
    from app.db.curated import load_curated
    from scripts.verify.policy_sources import cpt_descriptors, redact

    descriptors = cpt_descriptors(set(load_curated().scope))
    hits = {p.name: redact(p.read_text(encoding="utf-8"), descriptors)[1] for p in paths}
    if any(hits.values()):
        raise SystemExit(f"AMA CPT descriptor text found, nothing copied: {hits}")
    return len(descriptors)


def main() -> None:
    sheets: dict[str, list[str]] = {}
    conflicts: list[tuple[str, ...]] = []  # (file, row or entry, column, file's, recorded)
    for review in REVIEWS:
        path = SHEETS_DIR / review.file
        text = path.read_text(encoding="utf-8")
        lines, written = text.splitlines(), 0
        for verdicts, fill in ((review.table, fill_table), (review.blocks, fill_blocks)):
            if verdicts is not None:
                lines, found, n = fill(lines, verdicts)
                conflicts += [(review.file, *c) for c in found]
                written += n
        new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
        sheets[review.file] = lines
        print(f"{review.file}: {written} cells written")
    (SHEETS_DIR / SUMMARY).write_text(summarize(sheets), encoding="utf-8")
    paths = [SHEETS_DIR / r.file for r in REVIEWS] + [SHEETS_DIR / SUMMARY]
    checked = check_descriptors(paths)
    COPIES_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        shutil.copyfile(path, COPIES_DIR / path.name)
    print(
        f"no AMA CPT descriptor text ({checked} checked); copied {len(paths)} files to "
        f"{COPIES_DIR.relative_to(ROOT)}"
    )
    print("conflicts (file's value kept):", conflicts or "none")


if __name__ == "__main__":
    main()
