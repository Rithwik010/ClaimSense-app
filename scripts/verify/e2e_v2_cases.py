"""Policies v2, checkpoint 4: the v2 versions of the golden end-to-end cases that cite a retired v1
criterion (D-GOLD-8, D-GOLD-9), with engine-derived expected values.

Inputs, mapped mechanically from each v1 case: the same claim, reference additions and review
action, and the stub model answer rewritten for the v2 criteria the exact lookup returns for each
line's code (D-RAG-2):

- a kept criterion keeps its status and evidence;
- a criterion that replaces retired v1 criteria cited on the line takes their most decisive status
  (NOT_MET, then NOT_DOCUMENTED, MET, NOT_APPLICABLE) with that criterion's evidence;
- any other criterion is NOT_APPLICABLE with the fixed evidence;
- an exclusion is never MET (D-GEN-3): MET becomes NOT_APPLICABLE;
- in an indication group with a MET member, the members that are not MET become NOT_APPLICABLE
  (another indication; D-POL-3);
- a cited criterion that is neither shown in v2 nor retired stays as cited (E2E-27's invalid
  citation);
- one exception by the author (OVERRIDES; Claude Code, not reviewed): E2E-32 line 1 (93350).
  v2 moved v1 c1's signs-or-symptoms condition into c7 for stress echocardiography (c1's
  replacements c4 and c5 are not shown on 93350), and the notes say "no heart symptoms", so c7
  is NOT_MET, which keeps the case's model denial (D-GOLD-6);
- the line decision follows the statuses (D-POL-3), keeping the model's PEND under NCCI_BYPASS
  (the bypass check is not a criterion); reasons and missing information are kept when the
  decision is unchanged.

Expected values are the engine's output (D-GOLD-9): the pipeline on policy set v2 with the exact
lookup (in-memory Qdrant built from the v2 files), the mapped stub answer and the case's review
action, each case on a fresh database seeded like the end-to-end tests'. They are labelled
engine-derived and were not checked on a sheet (D-GOLD-10). Needs Postgres.

    uv run python -m scripts.verify.e2e_v2_cases write   # tests/golden/e2e_v2/cases.json
    uv run python -m scripts.verify.e2e_v2_cases check   # recompute; exit 1 when it differs
"""

import argparse
import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

from app.db.curated import CoveragePolicy, Criterion, load_curated
from app.ml.prompt import NOT_APPLICABLE

ROOT = Path(__file__).resolve().parents[2]
V1_CASES = ROOT / "tests" / "golden" / "e2e" / "cases.json"
V2_CASES = ROOT / "tests" / "golden" / "e2e_v2" / "cases.json"
SUFFIX = "-V2"
DECISIVE = {"NOT_MET": 3, "NOT_DOCUMENTED": 2, "MET": 1, "NOT_APPLICABLE": 0}
NO_INDICATION = "No covered indication documented."
OVERRIDES = {  # (v1 case, line, v2 criterion) -> (status, evidence); see the docstring
    ("E2E-32", 1, "POL-CAR-001.c7"): (
        "NOT_MET",
        "Blood pressure is high, but there are no heart symptoms and the heart exam is normal.",
    ),
}
SOURCE_NOTE = (
    "engine-derived (D-GOLD-9): the pipeline on policy set v2 (exact lookup, rules "
    "{rules}, calculator {calculator}) with the mapped stub answer and the case's review action; "
    "not checked on a sheet (D-GOLD-10). Built by scripts/verify/e2e_v2_cases.py on {day}."
)


def retired_map() -> dict[str, tuple[str, ...]]:
    return {
        old: new for p in load_curated("v2").policies.values() for old, new in p.replaces.items()
    }


def cited_ids(case: dict[str, Any]) -> list[str]:
    answer = case["given"].get("model_answer") or {}
    return [c["criterion_id"] for line in answer.get("lines", []) for c in line.get("criteria", [])]


def cases_to_version() -> list[dict[str, Any]]:
    retired = retired_map()
    cases = json.loads(V1_CASES.read_text(encoding="utf-8"))["cases"]
    return [c for c in cases if any(i in retired for i in cited_ids(c))]


def shown(code: str) -> list[tuple[CoveragePolicy, Criterion]]:
    """The v2 criteria shown on a code, in policy-file order: what the exact lookup returns for
    plan ALL policies effective 2026-01-01 (tests/unit/test_retrieval_v2.py checks the lookup)."""
    return [
        (policy, criterion)
        for policy in load_curated("v2").policies.values()
        for criterion in policy.criteria
        if code in policy.criterion_codes(criterion)
    ]


def derive_decision(
    criteria: list[dict[str, str]], kinds: dict[str, Criterion], bypass: bool, model: str
) -> tuple[str, bool]:
    """D-POL-3 on the v2 statuses: (decision, whether an indication group is unsatisfied)."""
    outside = [
        c["status"]
        for c in criteria
        if not (kinds.get(c["criterion_id"]) and kinds[c["criterion_id"]].group)
    ]
    group = [
        c["status"]
        for c in criteria
        if kinds.get(c["criterion_id"]) and kinds[c["criterion_id"]].group
    ]
    unsatisfied = bool(group) and "MET" not in group
    if "NOT_MET" in outside:
        return "DENY", unsatisfied
    if unsatisfied or "NOT_DOCUMENTED" in outside:
        return "PEND", unsatisfied
    if bypass and model == "PEND":
        return "PEND", False
    return "APPROVE", False


def map_line(
    line: dict[str, Any],
    code: str,
    bypass: bool,
    retired: dict[str, tuple[str, ...]],
    overrides: dict[str, tuple[str, str]],
) -> tuple[dict[str, Any], list[str]]:
    """The v2 version of one answer line, and a note of what was mapped."""
    cited = {c["criterion_id"]: c for c in line["criteria"]}
    found = shown(code)
    kinds = {criterion.criterion_id: criterion for _, criterion in found}
    criteria, notes = [], []
    for _, criterion in found:
        cid = criterion.criterion_id
        if cid in cited:
            result = dict(cited[cid])
        else:
            before = [old for old, new in retired.items() if cid in new and old in cited]
            if before:
                old = max(before, key=lambda o: DECISIVE[cited[o]["status"]])
                result = {"criterion_id": cid, **{k: cited[old][k] for k in ("status", "evidence")}}
                notes.append(f"{cid} from {', '.join(sorted(before))} ({result['status']})")
            else:
                result = {
                    "criterion_id": cid,
                    "status": "NOT_APPLICABLE",
                    "evidence": NOT_APPLICABLE,
                }
                notes.append(f"{cid} new: NOT_APPLICABLE")
        if cid in overrides:
            status, evidence = overrides[cid]
            notes.append(f"{cid} {result['status']} -> {status} (author's exception)")
            result = {"criterion_id": cid, "status": status, "evidence": evidence}
        if criterion.criterion_type == "exclusion" and result["status"] == "MET":
            result = {"criterion_id": cid, "status": "NOT_APPLICABLE", "evidence": NOT_APPLICABLE}
            notes.append(f"{cid} exclusion MET -> NOT_APPLICABLE (D-GEN-3)")
        criteria.append(result)
    members = [c for c in criteria if kinds[c["criterion_id"]].group]
    if any(c["status"] == "MET" for c in members):
        for c in members:
            if c["status"] != "MET" and c["status"] != "NOT_APPLICABLE":
                notes.append(f"{c['criterion_id']} {c['status']} -> NOT_APPLICABLE (group met)")
                c.update(status="NOT_APPLICABLE", evidence=NOT_APPLICABLE)
    kept = {c["criterion_id"] for c in criteria}
    for cid, c in cited.items():  # an invalid citation stays invalid
        if cid not in kept and cid not in retired:
            criteria.append(dict(c))
            notes.append(f"{cid} cited, not shown in v2: kept")
    decision, unsatisfied = derive_decision(criteria, kinds, bypass, line["decision"])
    mapped = {**line, "criteria": criteria, "decision": decision}
    if decision != line["decision"]:
        notes.append(f"decision {line['decision']} -> {decision}")
        if decision == "APPROVE":
            mapped |= {"reasons": [], "missing_information": []}
        elif decision == "DENY":
            exclusion = any(
                c["status"] == "NOT_MET"
                and kinds.get(c["criterion_id"])
                and kinds[c["criterion_id"]].criterion_type == "exclusion"
                for c in criteria
            )
            reason = "DN_CONDITIONAL_EXCLUSION" if exclusion else "DN_NOT_MEDICALLY_NECESSARY"
            mapped |= {"reasons": [reason], "missing_information": []}
        else:
            missing = (
                [NO_INDICATION]
                if unsatisfied
                else [
                    f"{c['criterion_id']}: {kinds[c['criterion_id']].text[:80]}"
                    for c in criteria
                    if c["status"] == "NOT_DOCUMENTED"
                ]
            )
            mapped |= {"reasons": ["PD_MISSING_DOCUMENTATION"], "missing_information": missing}
    return mapped, notes


def version_case(case: dict[str, Any]) -> dict[str, Any]:
    """The v2 case's inputs (expected values come from the engine)."""
    retired = retired_map()
    given = copy.deepcopy(case["given"])
    codes = {line["line_no"]: line["procedure_code"] for line in given["claim"]["service_lines"]}
    flags = {
        o["line_no"]: o.get("flags", []) for o in case["expected"]["rules"].get("line_outcomes", [])
    }
    notes = []
    answer = given.get("model_answer")
    if isinstance(answer, dict):
        lines = []
        for line in answer["lines"]:
            overrides = {
                cid: value
                for (case_id, line_no, cid), value in OVERRIDES.items()
                if (case_id, line_no) == (case["case_id"], line["line_no"])
            }
            mapped, said = map_line(
                line,
                codes[line["line_no"]],
                "NCCI_BYPASS" in flags.get(line["line_no"], []),
                retired,
                overrides,
            )
            lines.append(mapped)
            notes += [f"line {line['line_no']}: {n}" for n in said]
        given["model_answer"] = {**answer, "lines": lines}
    return {
        "case_id": case["case_id"] + SUFFIX,
        "title": f"{case['title']} (policy set v2)",
        "v1_case": case["case_id"],
        "policy_set": "v2",
        "given": given,
        "mapping": notes,
    }


# --- The engine ----------------------------------------------------------------------------------


class _ConstantEmbedder:
    """The v2 lookup uses no vectors; the collection still needs some."""

    name = "constant-4"
    dim = 4

    def embed_documents(self, texts):  # noqa: ANN001, ANN201
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]


def v2_retriever():  # noqa: ANN201
    from qdrant_client import QdrantClient

    from app.rag.knowledge import build_coverage_collection
    from app.rag.retrieve import ExactCriteriaRetriever

    client = QdrantClient(":memory:")
    build_coverage_collection(client, _ConstantEmbedder(), load_curated("v2"))
    return ExactCriteriaRetriever(client)


def run_engine(case: dict[str, Any]) -> dict[str, Any]:
    """The pipeline's output for a v2 case, in the golden `expected` layout."""
    from alembic import command
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.api.deps import get_decision_model, get_retriever
    from app.api.main import app
    from app.core.settings import Settings, get_settings
    from app.db.models import Accumulator, FeeScheduleEntry
    from app.db.seed import load_reference, load_rule_tables, seed_curated, upsert
    from app.db.session import get_engine
    from app.domain.contracts import DecisionRecord, SourceFormat
    from app.workflow.pipeline import intake_claim_data
    from tests.database import alembic_config, fresh_database
    from tests.e2e.support import StubModel, claim_on_file, e2e_fee_rows
    from tests.rule_tables import fixture_rule_tables

    given = case["given"]
    with fresh_database("claimsense_e2e_v2_build") as url:
        command.upgrade(alembic_config(url), "head")
        engine = create_engine(url)
        with Session(engine) as session:
            seed_curated(session)
            load_rule_tables(session, fixture_rule_tables())
            upsert(session, FeeScheduleEntry, e2e_fee_rows())
            additions = given["reference_additions"]
            load_reference(session, additions)
            session.add_all(claim_on_file(r) for r in additions.get("existing_claims", []))
            session.commit()
        answer = given.get("model_answer")
        settings = Settings(policy_set="v2")
        app.dependency_overrides[get_engine] = lambda: engine
        app.dependency_overrides[get_decision_model] = lambda: StubModel(
            json.dumps(answer) if answer is not None else "unused"
        )
        app.dependency_overrides[get_retriever] = v2_retriever
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            with TestClient(app) as client:
                claim = given["claim"]
                if given["source_format"] == "JSON":
                    assert client.post("/v1/claims/intake", json=claim).status_code == 201
                else:
                    with Session(engine) as session:
                        intake_claim_data(
                            session,
                            claim,
                            given["field_confidences"],
                            SourceFormat(given["source_format"]),
                            0.85,
                        )
                response = client.post(f"/v1/claims/{claim['claim_id']}/process")
                assert response.status_code == 200, response.text
                record = DecisionRecord.model_validate(response.json())
                expected = {
                    "rules": _rules(record),
                    "status_after_processing": record.status.value,
                    "recommendation": _recommendation(record),
                }
                action = given.get("review_action")
                if action is None:
                    expected["final"] = {"status": record.status.value}
                    return expected
                headers = {"X-Role": "reviewer"}
                reviewed = client.post(
                    f"/v1/claims/{claim['claim_id']}/review", json=action, headers=headers
                )
                assert reviewed.status_code == 200, reviewed.text
                final = DecisionRecord.model_validate(reviewed.json())
                events = client.get(f"/v1/claims/{claim['claim_id']}/audit").json()
                accumulators = events[-1]["payload"]["accumulators"]
                key = (
                    claim["member_id"],
                    date.fromisoformat(accumulators["period_start"]),
                    accumulators["network"],
                )
                with Session(engine) as session:
                    row = session.get(Accumulator, key)
                stored = (
                    {
                        "deductible_met_cents": row.deductible_met_cents,
                        "oop_met_cents": row.oop_met_cents,
                    }
                    if row
                    else {"deductible_met_cents": 0, "oop_met_cents": 0}
                )
                if stored != accumulators["after"]:
                    raise SystemExit(f"{case['case_id']}: stored and FINALIZED accumulators differ")
                expected["final"] = {
                    "status": final.status.value,
                    "claim_decision": final.claim_decision.value,
                    "line_decisions": _decisions(final),
                    "amounts": final.amounts.model_dump(mode="json"),
                    "accumulators_after": {"network": accumulators["network"], **stored},
                }
                return expected
        finally:
            app.dependency_overrides.clear()
            engine.dispose()


def _decisions(record: Any) -> list[dict[str, Any]]:
    return [
        d.model_dump(mode="json", include={"line_no", "decision", "source", "reason_codes"})
        for d in record.line_decisions
    ]


def _rules(record: Any) -> dict[str, Any]:
    rules = record.rules_outcome
    return {
        "claim_outcome": rules.claim_outcome.value,
        "line_outcomes": [o.model_dump(mode="json") for o in rules.line_outcomes],
        "flags": list(rules.flags),
        "failures": [
            {
                "rule_id": r.rule_id,
                "outcome": r.outcome.value,
                "reason_code": r.reason_code,
                "line_no": r.line_no,
            }
            for r in rules.rule_results
            if not r.passed
        ],
    }


def _recommendation(record: Any) -> dict[str, Any] | None:
    if not record.line_decisions:
        return None
    return {
        "output_valid": record.output_errors == [],
        "line_decisions": _decisions(record),
        "claim_decision": record.claim_decision.value if record.claim_decision else None,
        "review_tier": record.review_tier.value if record.review_tier else None,
        "amounts": record.amounts.model_dump(mode="json") if record.amounts else None,
    }


def build(day: str) -> dict[str, Any]:
    from app.calculator import CALCULATOR_VERSION
    from app.rules import RULES_VERSION

    note = SOURCE_NOTE.format(rules=RULES_VERSION, calculator=CALCULATOR_VERSION, day=day)
    cases = []
    for v1 in cases_to_version():
        case = version_case(v1)
        case["expected"] = run_engine(case)
        case["expected_source"] = note
        case["worked_steps"] = [
            f"Inputs: {v1['case_id']}'s claim, reference additions and review action; the stub "
            "answer mapped to the v2 criteria as this script's docstring says.",
            *case.pop("mapping"),
            "Expected values: " + note,
        ]
        cases.append(case)
    return {
        "description": (
            "Golden end-to-end cases on policy set v2 (D-GOLD-8, D-GOLD-9): the v2 versions of the "
            "cases in ../e2e/cases.json that cite a retired v1 criterion. Expected values are "
            "engine-derived, not hand-checked (D-GOLD-10)."
        ),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("write", "check"))
    step = parser.parse_args().step
    if step == "write":
        data = build(date.today().isoformat())
        V2_CASES.parent.mkdir(parents=True, exist_ok=True)
        V2_CASES.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {V2_CASES.relative_to(ROOT)}: {len(data['cases'])} cases")
        for case in data["cases"]:
            final = case["expected"]["final"]
            after = case["expected"]["status_after_processing"]
            print(f"  {case['case_id']}: {after} -> {final['status']}")
        return
    committed = json.loads(V2_CASES.read_text(encoding="utf-8"))
    problems = []
    for case in committed["cases"]:
        v1 = next(c for c in cases_to_version() if c["case_id"] == case["v1_case"])
        fresh = version_case(v1)
        if fresh["given"] != case["given"]:
            problems.append(f"{case['case_id']}: inputs differ from a fresh mapping")
        if run_engine(case) != case["expected"]:
            problems.append(f"{case['case_id']}: the engine's output differs")
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"{len(committed['cases'])} v2 cases: inputs and engine output unchanged")


if __name__ == "__main__":
    main()
