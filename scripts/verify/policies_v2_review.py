"""Policies v2, checkpoint 1: merge the pass 1 verdicts into the review sheet and pick the rows
for pass 2.

Pass 1 (P2_policies_v2_pass1_answers.md) was returned on 2026-10-09 by a normal Claude chat with no
repository access, which saw only the pasted sheet and the pass 1 prompt. It is a Claude
recomputation, not a human check: independent of the repository by construction, not of the author
model (the criteria were also written by Claude). Pass 2 is the reviewer's: every row whose pass 1
verdict is not MATCHES, AGREE or COMPLETE, plus 5 Part A MATCHES rows drawn with a fixed seed.

The merge writes only the two pass 1 columns of the sheet's verdict tables, after checking that
every row ID and criterion matches and every verdict is one the part allows; it never overwrites a
different pass 1 cell, and leaves the pass 2 columns alone.

    uv run python -m scripts.verify.policies_v2_review merge
    # fills the sheet and writes data/verification/reviews/P2_policies_v2_pass1_summary.md
"""

import argparse
import random
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.verify.policies_v2_sources import SHEET, ama_hits

ROOT = Path(__file__).resolve().parents[2]
ANSWERS = SHEET.parent / "P2_policies_v2_pass1_answers.md"
SUMMARY = SHEET.parent / "P2_policies_v2_pass1_summary.md"
SEED = 42
SAMPLE_SIZE = 5
VERDICTS = {
    "A": ("MATCHES", "DIFFERENT MEANING", "NOT IN SOURCE", "UNSURE"),
    "B": ("AGREE", "DISAGREE", "UNSURE"),
    "C": ("COMPLETE", "GAPS", "UNSURE"),
}
PASSED = {"MATCHES", "AGREE", "COMPLETE"}
PROVENANCE = (
    "Pass 1 (2026-10-09): a normal Claude chat with no repository access, which saw only the "
    "pasted sheet and the pass 1 prompt (answers as returned: P2_policies_v2_pass1_answers.md). "
    "A Claude recomputation, not a human check; independent of the repository by construction, "
    "not of the author model (the criteria were also written by Claude). Pass 2 is the "
    "reviewer's: the rows listed in P2_policies_v2_pass1_summary.md."
)
ROW = re.compile(r"^\| (?P<row>[ABC][0-9]+) \| (?P<criterion>[^|]+?) \|")


@dataclass(frozen=True)
class Verdict:
    row: str
    criterion: str
    verdict: str
    notes: str


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def read_verdicts(text: str) -> dict[str, Verdict]:
    """Pass 1 verdicts by row ID, from the answer tables. A row may appear only once."""
    out: dict[str, Verdict] = {}
    for line in text.splitlines():
        if not ROW.match(line):
            continue
        row, criterion, verdict, notes, *_ = cells(line)
        if row in out:
            raise SystemExit(f"row {row} answered twice")
        out[row] = Verdict(row, criterion, verdict, notes)
    return out


def merge(sheet: str, verdicts: Mapping[str, Verdict]) -> tuple[str, list[str]]:
    """(the sheet with the pass 1 columns filled, problems)."""
    problems: list[str] = []
    lines = sheet.splitlines()
    start = lines.index("## Verdicts")  # Part B's own table above uses the same row IDs
    seen = set()
    for i, line in enumerate(lines):
        match = ROW.match(line)
        if i < start or not match:
            continue
        row, criterion, pass1, notes1, pass2, notes2 = cells(line)
        seen.add(row)
        answer = verdicts.get(row)
        if answer is None:
            problems.append(f"{row}: no pass 1 answer")
            continue
        if answer.criterion != criterion:
            problems.append(f"{row}: answer names {answer.criterion}, the sheet {criterion}")
            continue
        if answer.verdict not in VERDICTS[row[0]]:
            problems.append(f"{row}: verdict {answer.verdict!r} is not one of {VERDICTS[row[0]]}")
            continue
        if not answer.notes and answer.verdict not in PASSED:
            problems.append(f"{row}: {answer.verdict} without notes")
        if (pass1 or notes1) and (pass1, notes1) != (answer.verdict, answer.notes):
            problems.append(f"{row}: the sheet already holds a different pass 1 verdict")
            continue
        lines[i] = (
            f"| {row} | {criterion} | {answer.verdict} | {answer.notes} | {pass2} | {notes2} |"
        )
    problems += [f"{row}: answered but not on the sheet" for row in sorted(set(verdicts) - seen)]
    if PROVENANCE not in lines:
        at = lines.index("## Verdicts")
        lines[at + 1 : at + 1] = ["", PROVENANCE]
    return "\n".join(lines) + "\n", problems


def row_number(row: str) -> tuple[str, int]:
    return row[0], int(row[1:])


def sample_matches(verdicts: Mapping[str, Verdict]) -> list[str]:
    """SAMPLE_SIZE Part A MATCHES rows, drawn with random.Random(SEED) from the rows in order."""
    matches = sorted(
        (r for r, v in verdicts.items() if r.startswith("A") and v.verdict == "MATCHES"),
        key=row_number,
    )
    return sorted(random.Random(SEED).sample(matches, SAMPLE_SIZE), key=row_number)


def summary(verdicts: Mapping[str, Verdict], drawn: Sequence[str]) -> str:
    counts = Counter((r[0], v.verdict) for r, v in verdicts.items())
    flagged = sorted((r for r, v in verdicts.items() if v.verdict not in PASSED), key=row_number)
    out = [
        "# Policies v2 review sheet: pass 1 summary and the pass 2 rows",
        "",
        PROVENANCE,
        "",
        "Pass 1 verdicts: "
        + "; ".join(
            f"Part {part}: "
            + ", ".join(f"{word} {counts[(part, word)]}" for word in words if counts[(part, word)])
            for part, words in VERDICTS.items()
        )
        + ".",
        "",
        f"## Pass 2: rows whose pass 1 verdict is not MATCHES, AGREE or COMPLETE ({len(flagged)})",
        "",
        "| Row | Criterion | Pass 1 verdict | Pass 1 notes |",
        "|---|---|---|---|",
    ]
    out += [
        f"| {r} | {verdicts[r].criterion} | {verdicts[r].verdict} | {verdicts[r].notes} |"
        for r in flagged
    ]
    out += [
        "",
        f"## Pass 2: {SAMPLE_SIZE} random Part A MATCHES rows",
        "",
        f"Drawn with random.Random({SEED}).sample from the "
        f"{sum(1 for r, v in verdicts.items() if r.startswith('A') and v.verdict == 'MATCHES')} "
        "Part A MATCHES rows in row order.",
        "",
        "| Row | Criterion | Pass 1 notes |",
        "|---|---|---|",
    ]
    out += [f"| {r} | {verdicts[r].criterion} | {verdicts[r].notes} |" for r in drawn]
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("merge",))
    parser.parse_args()
    verdicts = read_verdicts(ANSWERS.read_text(encoding="utf-8"))
    merged, problems = merge(SHEET.read_text(encoding="utf-8"), verdicts)
    drawn = sample_matches(verdicts)
    written = summary(verdicts, drawn)
    texts = {ANSWERS.name: ANSWERS.read_text(encoding="utf-8"), SHEET.name: merged}
    texts[SUMMARY.name] = written
    hits = {name: n for name, n in ama_hits(texts).items() if n}
    if hits:
        problems.append(f"AMA CPT descriptor text found: {hits}")
    if problems:
        raise SystemExit("not merged:\n  " + "\n  ".join(problems))
    SHEET.write_text(merged, encoding="utf-8")
    SUMMARY.write_text(written, encoding="utf-8")
    flagged = [r for r, v in verdicts.items() if v.verdict not in PASSED]
    print(
        f"merged {len(verdicts)} pass 1 verdicts into {SHEET.name}; "
        f"{len(flagged)} rows for pass 2, plus {', '.join(drawn)}; wrote {SUMMARY.name}"
    )


if __name__ == "__main__":
    main()
