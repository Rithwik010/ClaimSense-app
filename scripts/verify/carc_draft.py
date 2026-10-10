"""CARC/RARC draft (D-CARC-1, §8.3, H6): every internal DENY and REJECT reason code with the CARC
and RARC numbers in data/curated/reason_code_map.csv, checked against the official X12 lists in
data/raw/carc-rarc/<date>/ (saved from x12.org/codes; see data/raw_manifest.csv).

For each number the draft shows the official description, its start date and, if any, its stop
date, and says when a number is missing from the list or stopped. The alternates named in the
map's notes (for example "RARC M76 when ...") are checked the same way. Pended codes are left out:
CARC/RARC codes appear only on DENY and REJECT lines (D-CARC-1). The draft is printed and written
to data/generated/carc/carc-rarc-draft.md; nothing is committed from it until it is approved.

    uv run python -m scripts.verify.carc_draft [--date 2026-10-11]
"""

import argparse
import csv
import html
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "carc-rarc"
MAP = ROOT / "data" / "curated" / "reason_code_map.csv"
OUT = ROOT / "data" / "generated" / "carc" / "carc-rarc-draft.md"
FILES = {
    "CARC": "claim-adjustment-reason-codes.html",
    "RARC": "remittance-advice-remark-codes.html",
}
STOP = re.compile(r"Stop:\s*(\d{2}/\d{2}/\d{4})")
START = re.compile(r"Start:\s*(\d{2}/\d{2}/\d{4})")
ALTERNATE = re.compile(r"\b(?:(CARC|RARC) )?([A-Z]{1,2}\d+|\d+)\b(?= (?:when|for|is))")


def official(path: Path) -> dict[str, dict[str, str | None]]:
    """Code -> description, start and stop date, from a saved x12.org code list page."""
    text = path.read_text(encoding="utf-8", errors="replace")
    codes: dict[str, dict[str, str | None]] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        cells = [
            " ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        ]
        if len(cells) < 2 or not re.fullmatch(r"[A-Z]{0,2}\d+", cells[0]):
            continue
        body = cells[1]
        start, stop = START.search(body), STOP.search(body)
        description = re.split(r"\s+Start:", body)[0].strip()
        codes[cells[0]] = {
            "description": description,
            "start": start.group(1) if start else None,
            "stop": stop.group(1) if stop else None,
        }
    return codes


def status(code: str, kind: str, lists: dict[str, dict], today: date) -> str:
    found = lists[kind].get(code)
    if found is None:
        return f"{kind} {code}: NOT IN THE OFFICIAL LIST"
    stop = found["stop"]
    stopped = stop and datetime.strptime(stop, "%m/%d/%Y").date() <= today
    note = f" (STOPPED {stop})" if stopped else (f" (stops {stop})" if stop else "")
    return f"{kind} {code}{note}: {found['description']}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", default="2026-10-11", help="folder under data/raw/carc-rarc/")
    folder = RAW / parser.parse_args().date
    lists = {kind: official(folder / name) for kind, name in FILES.items()}
    today = date.today()
    rows = [
        r for r in csv.DictReader(MAP.open(encoding="utf-8")) if r["outcome"] in ("DENY", "REJECT")
    ]
    lines = [
        "# CARC/RARC draft (needs approval; D-CARC-1)",
        "",
        f"Official lists: `data/raw/carc-rarc/{folder.name}/` ({len(lists['CARC'])} CARC,"
        f" {len(lists['RARC'])} RARC codes). Map: `data/curated/reason_code_map.csv`.",
        "",
        "| Internal code | Outcome | Group | CARC (official description)"
        " | RARC (official description) | Alternates in the notes |",
        "|---|---|---|---|---|---|",
    ]
    problems = 0
    for r in rows:
        carc = status(r["carc"], "CARC", lists, today) if r["carc"] else "(blank)"
        rarc = status(r["rarc"], "RARC", lists, today) if r["rarc"] else "(blank)"
        alternates = [
            status(c, k or ("CARC" if c.isdigit() else "RARC"), lists, today)
            for k, c in ALTERNATE.findall(r["notes"])
        ]
        cells = [carc, rarc, *alternates]
        problems += sum("NOT IN THE OFFICIAL LIST" in c or "STOPPED" in c for c in cells)
        lines.append(
            f"| {r['internal_code']} | {r['outcome']} | {r['group_code']} | {carc} | {rarc} | "
            + ("; ".join(alternates) or "")
            + " |"
        )
    lines += ["", f"Numbers missing from the official list or stopped: {problems}.", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
