"""Train/live parity: the live pipeline (database -> context -> retrieval -> prompt) rebuilds the
generator's training prompts exactly. Uses a small dataset built through the retrieval path with
the fake embedder, and a fresh database seeded like `python -m app.db.seed`. Skipped when data/raw/
is absent (CI)."""

import pytest
from sqlalchemy.orm import Session

from app.db import raw
from app.db.models import Icd10Code
from app.db.seed import ICD10_FISCAL_YEAR, load_reference, upsert

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")


def test_live_pipeline_rebuilds_the_training_prompts(engine) -> None:  # noqa: ANN001
    from app.db.curated import load_curated
    from tests.unit.test_retrieval import retriever as fake_retriever
    from training.generate.common import DEFAULT_SEED
    from training.generate.decision_dataset import build_dataset
    from training.generate.reference import generate_reference
    from training.readiness import check_parity

    reference = generate_reference(DEFAULT_SEED)[0]
    with Session(engine) as session:
        load_reference(
            session,
            {
                "members": reference.members,
                "providers": reference.providers,
                "provider_networks": reference.provider_networks,
                "visit_usage": reference.visit_usage,
            },
        )
        upsert(
            session,
            Icd10Code,
            [
                {"code": c, "fiscal_year": ICD10_FISCAL_YEAR, "description": d}
                for c, d in raw.read_icd10_codes().items()
            ],
        )
        session.commit()
    search = fake_retriever()
    built = build_dataset(
        seed=17, sizes={"train": 30, "validation": 10, "test": 30}, retriever=search
    )
    curated = load_curated()
    data = {
        **built,
        "test_only": {p for p, x in curated.policies.items() if x.split == "TEST_ONLY"},
    }

    with Session(engine) as session:
        problems = check_parity(data, session, search, sample=30)

    assert problems == []

    records, inputs = data["splits"]["validation"]
    record = records[0]
    record["messages"][1]["content"] = record["messages"][1]["content"].replace(
        "PLAN_BENEFITS", "PLAN BENEFITS"
    )
    with Session(engine) as session:
        problems = check_parity(data, session, search, sample=30)

    assert len(problems) == 1 and record["metadata"]["record_id"] in problems[0]
