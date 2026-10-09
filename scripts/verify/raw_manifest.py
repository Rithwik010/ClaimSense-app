"""Checksums of the public source files in data/raw/ (never committed), kept in
data/raw_manifest.csv (committed), so a lost or changed file is noticed (D-DATA-1).

Without --update the script only checks: every listed file must exist with its listed size and
SHA-256, and files present but not listed are reported. --update rewrites the manifest from the
files on disk; do it only deliberately and record it in the progress log. A file's download URL
(`source_url`, optional, set by hand) is kept across updates. macOS Finder metadata (.DS_Store,
._* files) is not data and is ignored.

    uv run python -m scripts.verify.raw_manifest            # check
    uv run python -m scripts.verify.raw_manifest --update   # rewrite the manifest
"""

import argparse
import csv
import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "raw_manifest.csv"
FIELDS = ("path", "bytes", "sha256", "source_url")
FINDER_METADATA = re.compile(r"(^|/)(\.DS_Store|\._[^/]*)$")


@dataclass(frozen=True)
class Entry:
    path: str  # relative to data/raw/, "/"-separated
    size: int
    sha256: str
    source_url: str = ""  # where the file was downloaded, when recorded


@dataclass
class Report:
    missing: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unlisted: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.changed


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_files(raw_dir: Path) -> dict[str, Path]:
    """Every file under raw_dir by its relative path, without Finder metadata."""
    files = {}
    for path in sorted(raw_dir.rglob("*")):
        relative = path.relative_to(raw_dir).as_posix()
        if path.is_file() and not FINDER_METADATA.search(relative):
            files[relative] = path
    return files


def scan(raw_dir: Path = RAW_DIR) -> list[Entry]:
    return [
        Entry(relative, path.stat().st_size, sha256(path))
        for relative, path in data_files(raw_dir).items()
    ]


def read_manifest(path: Path = MANIFEST) -> list[Entry]:
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Entry(r["path"], int(r["bytes"]), r["sha256"], r.get("source_url") or "")
            for r in csv.DictReader(f)
        ]


def write_manifest(entries: Sequence[Entry], path: Path = MANIFEST) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows((e.path, e.size, e.sha256, e.source_url) for e in entries)


def keep_source_urls(scanned: Sequence[Entry], old: Sequence[Entry]) -> list[Entry]:
    """The scanned entries with the source URL each path had in the previous manifest."""
    urls = {e.path: e.source_url for e in old}
    return [replace(e, source_url=urls.get(e.path, "")) for e in scanned]


def compare(listed: Sequence[Entry], raw_dir: Path = RAW_DIR) -> Report:
    """Listed files that are missing or changed (size or SHA-256), and files present but not
    listed."""
    present = data_files(raw_dir)
    report = Report()
    for entry in listed:
        path = present.get(entry.path)
        if path is None:
            report.missing.append(entry.path)
        elif path.stat().st_size != entry.size:
            report.changed.append(f"{entry.path}: size {path.stat().st_size} != {entry.size}")
        elif sha256(path) != entry.sha256:
            report.changed.append(f"{entry.path}: SHA-256 differs")
    names = {e.path for e in listed}
    report.unlisted = [relative for relative in present if relative not in names]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite data/raw_manifest.csv from the files on disk (record it in the log)",
    )
    update = parser.parse_args().update
    if not RAW_DIR.exists():
        raise SystemExit(f"{RAW_DIR} does not exist")
    if update:
        old = {e.path: e for e in read_manifest()} if MANIFEST.exists() else {}
        entries = keep_source_urls(scan(), list(old.values()))
        write_manifest(entries)
        new = {e.path: e for e in entries}
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(p for p in set(new) & set(old) if new[p] != old[p])
        print(
            f"wrote {MANIFEST.relative_to(ROOT)}: {len(entries)} files, "
            f"{sum(e.size for e in entries):,} bytes; since the previous manifest: added "
            f"{len(added)}, removed {len(removed)}, changed {len(changed)}"
        )
        for label, paths in (("added", added), ("removed", removed), ("changed", changed)):
            for p in paths:
                print(f"  {label}: {p}")
        return
    if not MANIFEST.exists():
        raise SystemExit(f"{MANIFEST.relative_to(ROOT)} does not exist; run with --update")
    listed = read_manifest()
    report = compare(listed)
    print(
        f"{len(listed)} listed files: missing {len(report.missing)}, changed "
        f"{len(report.changed)}; present but not listed: {len(report.unlisted)}"
    )
    for label, paths in (
        ("missing", report.missing),
        ("changed", report.changed),
        ("not listed", report.unlisted),
    ):
        for p in paths:
            print(f"  {label}: {p}")
    if not report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
