"""The seed's fee schedule (D6) matches the fee values in the golden calculator cases, which the
end-to-end tests load in its place. Skipped when data/raw/ is absent (CI)."""

import pytest

from app.db import raw
from app.db.curated import load_curated
from app.db.seed import curated_rows, fee_rows
from tests.e2e.support import golden_fee_rows

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")


def test_fee_rows_cover_the_scope_and_match_the_golden_fees() -> None:
    curated = load_curated()
    rows = {row["procedure_code"]: row for row in fee_rows(curated)}

    assert set(rows) == set(curated.scope)
    for golden in golden_fee_rows():
        row = rows[golden["procedure_code"]]
        assert (row["inn_allowed_cents"], row["oon_allowed_cents"]) == (
            golden["inn_allowed_cents"],
            golden["oon_allowed_cents"],
        ), golden["procedure_code"]


def test_curated_rows_follow_the_curated_files() -> None:
    curated = load_curated()
    tables = {model.__tablename__: rows for model, rows in curated_rows(curated)}

    assert len(tables["plans"]) == len(curated.plans)
    assert len(tables["benefits"]) == len(curated.benefits)
    assert {row["code"] for row in tables["procedure_codes"]} == set(curated.scope)
    hmo = next(row for row in tables["plans"] if row["plan_id"] == "PLN-HMO")
    assert hmo["oon_covered"] is False and hmo["oon_deductible_cents"] is None
