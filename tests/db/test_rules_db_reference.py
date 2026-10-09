"""P2.1: the database-backed rules reference (app.db.rules_reference.reference_for_claim) gives
exactly what the file-backed one gives.

- NCCI: with several edits for one pair, the same "first edit active on the date".
- The 121 golden rules cases: the same RulesOutcome, equal to the expected values, on a database
  loaded from the committed fixture (runs in CI, D-CI-1) and, where data/raw/ is present, from
  data/raw/ in full.
- The 2,600 dataset records (where the dataset and data/raw/ are present): the same RulesOutcome
  as the file-backed reference, and the generator's rule mirror and RULES_RESULT text
  (scripts/verify/rules_parity.py)."""

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.db import raw
from app.db.curated import load_curated
from app.db.rules_reference import reference_for_claim
from app.db.seed import (
    GENERATED_DIR,
    copy_ncci,
    load_reference,
    load_rule_tables,
    raw_rule_tables,
    seed,
    seed_curated,
)
from app.rules.engine import evaluate
from app.rules.reference import NcciEdit, RulesReference
from scripts.verify.rules_parity import DECISION_DIR, dataset_reference, db_differences
from scripts.verify.rules_parity import load_records as load_dataset
from tests.database import alembic_config, fresh_database
from tests.e2e.support import claim_on_file
from tests.rule_tables import fixture_rule_tables
from tests.unit.rules_support import reference as file_reference
from tests.unit.test_rules_golden import (
    CASES,
    CONFIDENCE_MIN,
    SHARED,
    STATUS,
    failures,
    reference_for,
)

SOURCES = ["fixture", "raw"] if raw.raw_available() else ["fixture"]


def migrated_database(name: str) -> Iterator[Engine]:
    with fresh_database(name) as url:
        command.upgrade(alembic_config(url), "head")
        engine = create_engine(url)
        yield engine
        engine.dispose()


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    yield from migrated_database("claimsense_rules_reference")


# --- NCCI: the first edit active on the date -----------------------------------------------------

D = date
EDITS = [  # (effective, deletion, indicator), in published order
    (D(2020, 1, 1), D(2026, 9, 30), "0"),
    (D(2026, 10, 1), None, "1"),
    (D(2026, 10, 1), D(2026, 10, 1), "9"),  # a same-day deletion overlapping the edit above
    (D(2027, 1, 1), None, "0"),
    (D(2026, 11, 1), D(2026, 11, 30), "0"),
]
DAYS = [D(2019, 12, 31), D(2026, 9, 30), D(2026, 10, 1), D(2026, 11, 15), D(2027, 2, 1)]


@pytest.mark.parametrize("order", [[0, 1, 2, 3, 4], [2, 4, 3, 1, 0]], ids=["as-listed", "shuffled"])
def test_the_database_picks_the_same_first_active_ncci_edit(
    engine: Engine, order: list[int]
) -> None:
    edits = [EDITS[i] for i in order]
    claim = {"service_lines": [{"procedure_code": "11042"}, {"procedure_code": "97597"}]}
    with Session(engine) as session:
        copy_ncci(session, [("11042", "97597", *edit) for edit in edits])
        session.flush()
        from_db = reference_for_claim(session, claim)
        session.rollback()
    from_files = file_reference(
        ncci={("11042", "97597"): tuple(NcciEdit("11042", "97597", *edit) for edit in edits)}
    )

    picked = [from_db.ncci_indicator("11042", "97597", day) for day in DAYS]

    assert picked == [from_files.ncci_indicator("11042", "97597", day) for day in DAYS]
    assert picked[0] is None and picked[1] == "0"  # before any edit; the first edit alone
    expected_overlap = "1" if order[0] == 0 else "9"  # on 2026-10-01 the earlier listed wins
    assert picked[2] == expected_overlap


# --- The 121 golden rules cases -------------------------------------------------------------------


@pytest.fixture(scope="module", params=SOURCES)
def golden_database(request: pytest.FixtureRequest) -> Iterator[tuple[str, Engine]]:
    """A database with the curated data, the rule tables from `source` and reference.json."""
    source = request.param
    for engine in migrated_database(f"claimsense_rules_golden_{source}"):
        with Session(engine) as session:
            seed_curated(session)
            tables = fixture_rule_tables() if source == "fixture" else raw_rule_tables()
            load_rule_tables(session, tables)
            load_reference(
                session,
                {key: SHARED[key] for key in ("members", "providers", "provider_networks")},
            )
            session.commit()
        yield source, engine


def _add_case_records(session: Session, additions: dict[str, Any]) -> None:
    load_reference(session, {"authorizations": additions.get("authorizations", [])})
    session.add_all(claim_on_file(row) for row in additions.get("existing_claims", []))
    session.flush()


def claim_coverage(claim: dict[str, Any], reference: RulesReference) -> dict:
    """The file reference's article coverage for the claim's codes and diagnoses (what the
    database reference loads for one claim)."""
    lines = [line for line in claim.get("service_lines") or [] if isinstance(line, dict)]
    codes = {line.get("procedure_code") for line in lines}
    diagnoses = {
        d.replace(".", "").strip().upper()
        for d in claim.get("diagnoses") or []
        if isinstance(d, str)
    }
    articles = {s.billing_article for c, s in reference.diagnosis_support.items() if c in codes}
    covered = {
        article: {
            group: found & diagnoses
            for group, found in reference.article_covered.get(article, {}).items()
            if found & diagnoses
        }
        for article in articles
    }
    return {article: groups for article, groups in covered.items() if groups}


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_golden_rules_case_with_the_database_reference(
    golden_database: tuple[str, Engine], case: dict[str, Any]
) -> None:
    source, engine = golden_database
    given, expected = case["given"], case["expected"]
    with Session(engine) as session:
        _add_case_records(session, given["reference_additions"])
        db_reference = reference_for_claim(session, given["claim"])
        from_db = evaluate(
            given["claim"],
            given["field_confidences"],
            db_reference,
            confidence_min=CONFIDENCE_MIN,
        )
        session.rollback()
    file_reference_ = reference_for(case, source)
    assert db_reference.article_covered == claim_coverage(given["claim"], file_reference_)
    assert db_reference.diagnosis_support == file_reference_.diagnosis_support
    assert db_reference.code_roles == file_reference_.code_roles
    from_files = evaluate(
        given["claim"],
        given["field_confidences"],
        reference_for(case, source),
        confidence_min=CONFIDENCE_MIN,
    )

    assert from_db == from_files
    assert from_db.claim_outcome.value == expected["claim_outcome"]
    assert STATUS[from_db.claim_outcome.value] == expected["status"]
    assert failures(from_db.rule_results) == expected["failures"]
    if expected["line_outcomes"] is None:
        assert from_db.line_outcomes == []
    else:
        assert [o.model_dump() for o in from_db.line_outcomes] == expected["line_outcomes"]
    assert from_db.flags == expected["flags"]


# --- The 2,600 dataset records -------------------------------------------------------------------

DATASET_PRESENT = (DECISION_DIR / "train_inputs.jsonl").exists() and raw.raw_available()


@pytest.mark.skipif(not DATASET_PRESENT, reason="model v1 dataset or data/raw/ not present")
def test_every_dataset_record_gives_the_same_rules_from_the_database() -> None:
    records = load_dataset()
    for engine in migrated_database("claimsense_rules_dataset"):
        with Session(engine) as session:
            seed(session, GENERATED_DIR / "reference")
            session.commit()
            found = db_differences(records, session, dataset_reference(), load_curated())

    assert len(records) == 2600
    assert not found, list(found.items())[:5]
