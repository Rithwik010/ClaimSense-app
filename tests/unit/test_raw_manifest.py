"""D-DATA-1: every file in data/raw/ is listed with its size and SHA-256 in data/raw_manifest.csv,
and a missing or changed file fails. The data check is skipped where data/raw/ does not exist
(CI); the other tests use temporary folders."""

import hashlib
import warnings
from pathlib import Path

import pytest

from scripts.verify.raw_manifest import (
    MANIFEST,
    RAW_DIR,
    Entry,
    compare,
    keep_source_urls,
    read_manifest,
    scan,
    write_manifest,
)


def _raw(root: Path) -> Path:
    (root / "ncci-ptp" / "f1").mkdir(parents=True)
    (root / "ncci-ptp" / "f1" / "f1.xlsx").write_bytes(b"official xlsx")
    (root / "pos.pdf").write_bytes(b"place of service")
    (root / ".DS_Store").write_bytes(b"finder")
    (root / "ncci-ptp" / "._f1.xlsx").write_bytes(b"apple double")
    return root


def test_scan_lists_every_data_file_with_size_and_sha256_but_not_finder_metadata(
    tmp_path: Path,
) -> None:
    entries = scan(_raw(tmp_path / "raw"))

    assert [(e.path, e.size) for e in entries] == [("ncci-ptp/f1/f1.xlsx", 13), ("pos.pdf", 16)]
    assert entries[1].sha256 == hashlib.sha256(b"place of service").hexdigest()


def test_the_manifest_round_trips(tmp_path: Path) -> None:
    entries = scan(_raw(tmp_path / "raw"))
    path = tmp_path / "manifest.csv"

    write_manifest(entries, path)

    assert read_manifest(path) == entries


def test_missing_changed_and_unlisted_files_are_reported(tmp_path: Path) -> None:
    raw = _raw(tmp_path / "raw")
    listed = [*scan(raw), Entry("mue/gone.csv", 3, "0" * 64)]
    (raw / "pos.pdf").write_bytes(b"place of servicE")  # same size, different content
    (raw / "ncci-ptp" / "f1" / "f1.txt").write_bytes(b"new")

    report = compare(listed, raw)

    assert report.missing == ["mue/gone.csv"]
    assert report.changed == ["pos.pdf: SHA-256 differs"]
    assert report.unlisted == ["ncci-ptp/f1/f1.txt"]
    assert not report.ok


def test_an_unchanged_folder_passes(tmp_path: Path) -> None:
    raw = _raw(tmp_path / "raw")

    report = compare(scan(raw), raw)

    assert report.ok and not report.unlisted


@pytest.mark.skipif(not RAW_DIR.exists(), reason="data/raw/ not present (CI has no raw data)")
def test_data_raw_matches_the_manifest() -> None:
    report = compare(read_manifest(MANIFEST), RAW_DIR)

    assert not report.missing, f"listed in {MANIFEST.name} but missing: {report.missing}"
    assert not report.changed, f"changed since {MANIFEST.name} was written: {report.changed}"
    if report.unlisted:
        warnings.warn(f"in data/raw/ but not in {MANIFEST.name}: {report.unlisted}", stacklevel=1)


def test_source_urls_round_trip_and_survive_an_update(tmp_path: Path) -> None:
    path = tmp_path / "manifest.csv"
    url = "https://www.cms.gov/files/zip/2027-code-tables-tabular-index.zip"
    old = [Entry("icd10cm/a.zip", 3, "a" * 64, url), Entry("mue/b.csv", 4, "b" * 64)]
    write_manifest(old, path)

    scanned = [Entry("icd10cm/a.zip", 3, "a" * 64), Entry("pos/c.pdf", 5, "c" * 64)]

    assert read_manifest(path) == old
    assert keep_source_urls(scanned, old) == [
        Entry("icd10cm/a.zip", 3, "a" * 64, url),
        Entry("pos/c.pdf", 5, "c" * 64),
    ]
