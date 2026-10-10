"""Decision dataset v2 (generator v2): policy set v2, rules RULES_VERSION, prompt decision_v3.

Chat records (system decision_v3 + user message + the target `SLMOutput`) and a sidecar of the
structured inputs, as in v1, built by `training.generate.scenarios_v2`. Retrieval is the v2 exact
lookup (`ExactCriteriaRetriever`, D-RAG-2) on an in-memory copy of `coverage_policies_v2` built
from the policy files; training and validation never see the test-only policies.

Splits (2,000 / 300 / 300): train and validation use the training policies and note styles A, B
and C; the test split has 100 records on the policies never seen in training and 200 on the
training policies, and half of its records use style D, a style no training record uses. Every
check in `checks_v2.py` must pass before anything is written; the label distributions per split,
policy and scenario go to `summary.json` and the data card.

    uv run python -m training.generate.decision_dataset --policy-set v2
"""

import json
import random
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from app.ml.prompt import PROMPT_V3, PromptLookups, render_user_message, system_prompt
from app.rag.knowledge import (
    COVERAGE_COLLECTIONS,
    build_coverage_collection,
    curated_knowledge_version,
)
from app.rag.retrieve import ExactCriteriaRetriever
from app.rules import RULES_VERSION
from training.generate.checks import distribution
from training.generate.checks_v2 import check_record_v2, duplicate_problems
from training.generate.claims import claim_decision
from training.generate.codebook import load_codebook
from training.generate.common import DEFAULT_SEED, GENERATED_DIR, write_json, write_jsonl
from training.generate.reference import generate_reference
from training.generate.scenarios import ScenarioError
from training.generate.scenarios_v2 import (
    GENERATOR_VERSION as SCENARIO_VERSION,
)
from training.generate.scenarios_v2 import (
    POLICY_SET,
    TEST_ONLY_POLICIES,
    TEST_ONLY_STYLE,
    TRAIN_STYLES,
    ScenarioBuilderV2,
    template_problems,
)

GENERATOR_VERSION = "decision-dataset-v3"
OUT_DIR = GENERATED_DIR / "decision_v2"
DOCS_CARD = Path(__file__).resolve().parents[2] / "docs" / "data-card-v2.md"
DEFAULT_SIZES = {"train": 2000, "validation": 300, "test": 300}
TEST_UNSEEN_POLICY_RECORDS = 100
TEST_STYLES = (TEST_ONLY_STYLE,) * 3 + TRAIN_STYLES  # half of the test notes in style D
SCENARIO_WEIGHTS = {
    "approve_single": 16,
    "deny_criterion": 9,
    "deny_exclusion": 6,
    "pend_missing": 11,
    "office_visit": 4,
    "office_plus_procedure": 5,
    "office_same_day": 7,
    "same_profile_multi": 6,
    "two_policy": 5,
    "ncci_bypass": 7,
    "rule_denied_line": 6,
    "ncs_without_emg": 4,
    "facet_two_regions": 3,
    "extended_testing": 3,
}
CHARS_PER_TOKEN = 3.5


class _ConstantEmbedder:
    """The exact lookup reads no vectors; the in-memory collection still stores some."""

    name = "constant-4"
    dim = 4

    def embed_documents(self, texts):  # noqa: ANN001, ANN201
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]


def exact_retriever() -> ExactCriteriaRetriever:
    from qdrant_client import QdrantClient

    client = QdrantClient(":memory:")
    build_coverage_collection(client, _ConstantEmbedder(), load_curated(POLICY_SET))
    return ExactCriteriaRetriever(client, COVERAGE_COLLECTIONS[POLICY_SET])


def lookups_v2() -> PromptLookups:
    from app.workflow.pipeline import bypass_keys

    codebook = load_codebook()
    return PromptLookups(
        icd10_descriptions=codebook.icd10,
        procedure_descriptions=load_curated(POLICY_SET).descriptions,
        policy_codes={
            p.policy_id: list(p.procedure_codes) for p in load_curated(POLICY_SET).policies.values()
        },
        bypass_keys=bypass_keys(),
    )


def _records(
    builder: ScenarioBuilderV2,
    split: str,
    count: int,
    start: int,
    seed: int,
    lookups: PromptLookups,
    skip: tuple[str, ...] = (),
    forbidden_notes: frozenset[str] = frozenset(),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """`forbidden_notes`: the training notes, which a test record must not repeat."""
    rng = random.Random(f"{seed}-v2-{split}-{start}")
    system = system_prompt(PROMPT_V3)
    knowledge = curated_knowledge_version(POLICY_SET, "")
    weighted = {t: w for t, w in SCENARIO_WEIGHTS.items() if t not in skip}
    types, weights = list(weighted), list(weighted.values())
    records, inputs = [], []
    number = start
    failures: Counter[str] = Counter()
    while len(records) < count:
        scenario_type = rng.choices(types, weights=weights)[0]
        claim_id = f"CLM-V2{split[:2].upper()}-{number:05d}"
        try:
            scenario = builder.build(scenario_type, claim_id)
        except ScenarioError:
            failures[scenario_type] += 1
            if failures[scenario_type] > 200:
                weighted.pop(scenario_type, None)
                types, weights = list(weighted), list(weighted.values())
            continue
        if scenario.claim.clinical_notes in forbidden_notes:
            continue
        number += 1
        record_id = f"DV2-{split[:2].upper()}-{number:05d}"
        user = render_user_message(
            scenario.claim, scenario.rules, scenario.context, lookups, PROMPT_V3
        )
        assert scenario.target is not None
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": scenario.target.model_dump_json()},
        ]
        metadata = {
            **scenario.metadata(),
            "record_id": record_id,
            "split": split,
            "claim_id": claim_id,
            "seed": seed,
            "dataset_version": GENERATOR_VERSION,
            "scenario_version": SCENARIO_VERSION,
            "policy_set": POLICY_SET,
            "prompt_version": PROMPT_V3,
            "rules_version": RULES_VERSION,
            "retrieval": f"{ExactCriteriaRetriever.settings_label}; knowledge {knowledge}",
            "note_style": scenario.template_set,
            "policy_id": scenario.policy_ids[0] if scenario.policy_ids else None,
            "claim_decision": claim_decision(scenario.line_labels),
        }
        records.append({"messages": messages, "metadata": metadata})
        inputs.append(
            {
                "record_id": record_id,
                "claim": scenario.claim.model_dump(mode="json"),
                "rules_outcome": scenario.rules.model_dump(mode="json"),
                "context": scenario.context.model_dump(mode="json"),
                "target": scenario.target.model_dump(mode="json"),
                "authorizations": [
                    {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in a.items()}
                    for a in scenario.authorizations
                ],
            }
        )
    return records, inputs


def build_dataset_v2(
    seed: int = DEFAULT_SEED, sizes: Mapping[str, int] | None = None
) -> dict[str, Any]:
    sizes = dict(sizes or DEFAULT_SIZES)
    curated = load_curated(POLICY_SET)
    problems = template_problems(curated.policies, set(load_codebook().icd10))
    if problems:
        raise SystemExit("templates incomplete:\n  " + "\n  ".join(problems))
    reference = generate_reference(DEFAULT_SEED)[0]
    lookups = lookups_v2()
    retriever = exact_retriever()
    everything = set(curated.policies)
    train_policies = everything - TEST_ONLY_POLICIES

    def builder(offset: int, styles, policies: set[str], excluded: set[str]) -> ScenarioBuilderV2:  # noqa: ANN001
        return ScenarioBuilderV2(
            seed + offset, styles, policies, excluded, retriever, reference, lookups
        )

    splits: dict[str, tuple[list, list]] = {}
    splits["train"] = _records(
        builder(10, TRAIN_STYLES, train_policies, set(TEST_ONLY_POLICIES)),
        "train",
        sizes["train"],
        0,
        seed,
        lookups,
    )
    splits["validation"] = _records(
        builder(11, TRAIN_STYLES, train_policies, set(TEST_ONLY_POLICIES)),
        "validation",
        sizes["validation"],
        0,
        seed,
        lookups,
    )
    training_notes = frozenset(
        i["claim"]["clinical_notes"] for split in ("train", "validation") for i in splits[split][1]
    )
    unseen = min(TEST_UNSEEN_POLICY_RECORDS, sizes["test"] // 3)
    test_unseen = _records(
        builder(12, TEST_STYLES, set(TEST_ONLY_POLICIES), set()),
        "test",
        unseen,
        0,
        seed,
        lookups,
        skip=("office_visit", "ncs_without_emg", "facet_two_regions", "extended_testing"),
        forbidden_notes=training_notes,
    )
    test_seen = _records(
        builder(13, TEST_STYLES, train_policies, set()),
        "test",
        sizes["test"] - unseen,
        unseen,
        seed,
        lookups,
        forbidden_notes=training_notes,
    )
    splits["test"] = (test_unseen[0] + test_seen[0], test_unseen[1] + test_seen[1])
    return {
        "splits": splits,
        "curated": curated,
        "retriever": retriever,
        "reference": reference,
        "lookups": lookups,
    }


def run_checks_v2(built: Mapping[str, Any]) -> dict[str, Any]:
    from app.rules.lcd_edits import supported as r15_supported

    curated = built["curated"]
    retriever = built["retriever"]
    lookups = built["lookups"]
    probe = ScenarioBuilderV2(0, TRAIN_STYLES, set(), set(), retriever, built["reference"], lookups)

    def render(claim, rules, context):  # noqa: ANN001, ANN202
        return render_user_message(claim, rules, context, lookups, PROMPT_V3)

    def supported(claim, index: int) -> bool:  # noqa: ANN001
        line = claim.service_lines[index]
        support = probe.rules_reference.diagnosis_support.get(line.procedure_code)
        return support is None or r15_supported(claim, line, support, probe.rules_reference)

    problems: list[str] = []
    for split, (records, inputs) in built["splits"].items():
        excluded = set() if split == "test" else set(TEST_ONLY_POLICIES)

        def lookup(plan_id: str, code: str, day, excluded: set[str] = excluded):  # noqa: ANN001, ANN202
            return retriever.retrieve("", plan_id, day, code, excluded)

        for record, record_inputs in zip(records, inputs, strict=True):
            found = check_record_v2(
                record_inputs,
                record["messages"],
                curated,
                lookup=lookup,
                engine=probe.engine,
                supported=supported,
                render=render,
            )
            problems += [f"{record['metadata']['record_id']}: {p}" for p in found]
            meta = record["metadata"]
            if split != "test" and meta["note_style"] == TEST_ONLY_STYLE:
                problems.append(f"{meta['record_id']}: test-only style in {split}")
            if split != "test" and set(meta["policy_ids"]) & TEST_ONLY_POLICIES:
                problems.append(f"{meta['record_id']}: test-only policy in {split}")
    problems += duplicate_problems({s: r for s, (r, _) in built["splits"].items()})
    unseen = sum(
        1
        for r in built["splits"]["test"][0]
        if set(r["metadata"]["policy_ids"]) & TEST_ONLY_POLICIES
    )
    styles = Counter(r["metadata"]["note_style"] for r in built["splits"]["test"][0])
    return {
        "problems": problems,
        "test_records_with_unseen_policies": unseen,
        "test_styles": dict(styles),
    }


def label_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Line labels per policy and per scenario, and the flags and modifiers shown."""
    by_policy: dict[str, Counter[str]] = {}
    by_scenario: dict[str, Counter[str]] = {}
    flags: Counter[str] = Counter()
    for record in records:
        meta = record["metadata"]
        user = record["messages"][1]["content"]
        for flag in ("NCCI_BYPASS", "NCS_WITHOUT_EMG", "FACET_TWO_REGIONS", "EXTENDED_TESTING"):
            flags[flag] += user.count(f"flag {flag}")
        for label in meta["line_labels"]:
            key = f"{label['source']} {label['decision']}"
            policy = meta["policy_id"] or "office visit"
            by_policy.setdefault(policy, Counter())[key] += 1
            by_scenario.setdefault(meta["scenario_type"], Counter())[key] += 1
    return {
        "by_policy": {k: dict(v) for k, v in sorted(by_policy.items())},
        "by_scenario": {k: dict(v) for k, v in sorted(by_scenario.items())},
        "flags_shown": dict(flags),
        "note_styles": dict(Counter(r["metadata"]["note_style"] for r in records)),
    }


def record_lengths(records: list[dict[str, Any]]) -> dict[str, Any]:
    sizes = sorted(
        (sum(len(m["content"]) for m in r["messages"]), r["metadata"]["record_id"]) for r in records
    )

    def at(share: float) -> int:
        return sizes[int(share * (len(sizes) - 1))][0]

    return {
        "p50": at(0.5),
        "p95": at(0.95),
        "max": sizes[-1][0],
        "longest_record": sizes[-1][1],
        "tokens_max_estimate": round(sizes[-1][0] / CHARS_PER_TOKEN),
    }


def data_card_v2(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Decision dataset v2: data card",
        "",
        f"Generator {GENERATOR_VERSION} (scenarios {SCENARIO_VERSION}), policy set {POLICY_SET}, "
        f"rules {RULES_VERSION}, prompt {PROMPT_V3}, seed {summary['seed']}. Synthetic data only.",
        "",
        f"- Sizes: {summary['sizes']}.",
        f"- Retrieval: {summary['retrieval']}.",
        f"- Test-only policies (never in train or validation): {sorted(TEST_ONLY_POLICIES)}; "
        f"test records using them: {summary['checks']['test_records_with_unseen_policies']}.",
        f"- Note styles: train and validation {list(TRAIN_STYLES)}; style {TEST_ONLY_STYLE} "
        f"(a numbered list mixing wordings A and B) only in the test split: "
        f"{summary['checks']['test_styles']}.",
        "- Labels: the line decision is derived from the statuses by `app.ml.derive` (D-DEC-1), "
        "the pipeline's own code; rule outcomes come from the rules engine with every claim's "
        "authorizations in the reference data (D-GEN-5).",
        "- Add-on level codes (64480, 64484, 64491, 64492, 64494, 64495) stay out of scope: "
        "rule-only.",
        f"- Checks: {summary['checks']['problems']} problems (checks_v2.py).",
        "",
        "## Lengths (characters; tokens estimated at 3.5 characters each)",
        "",
        "| Split | p50 | p95 | max | longest record |",
        "|---|---|---|---|---|",
    ]
    for split, length in summary["lengths"].items():
        lines.append(
            f"| {split} | {length['p50']} | {length['p95']} | {length['max']} | "
            f"{length['longest_record']} |"
        )
    for split, report in summary["labels"].items():
        lines += ["", f"## {split}: line labels per policy", "", "| Policy | Labels |", "|---|---|"]
        lines += [
            f"| {policy} | {', '.join(f'{k} {v}' for k, v in sorted(counts.items()))} |"
            for policy, counts in report["by_policy"].items()
        ]
        lines += [
            "",
            f"## {split}: line labels per scenario",
            "",
            "| Scenario | Labels |",
            "|---|---|",
        ]
        lines += [
            f"| {scenario} | {', '.join(f'{k} {v}' for k, v in sorted(counts.items()))} |"
            for scenario, counts in report["by_scenario"].items()
        ]
        lines += [
            "",
            f"Flags shown in {split}: {report['flags_shown']}; "
            f"note styles: {report['note_styles']}.",
        ]
    return "\n".join(lines) + "\n"


def write_dataset_v2(
    out_dir: Path = OUT_DIR, seed: int = DEFAULT_SEED, sizes: Mapping[str, int] | None = None
) -> dict[str, Any]:
    built = build_dataset_v2(seed, sizes)
    checks = run_checks_v2(built)
    if checks["problems"]:
        raise SystemExit("v2 dataset checks failed:\n" + "\n".join(checks["problems"][:60]))
    out_dir.mkdir(parents=True, exist_ok=True)
    authorizations = []
    for split, (records, inputs) in built["splits"].items():
        write_jsonl(out_dir / f"{split}.jsonl", records)
        write_jsonl(out_dir / f"{split}_inputs.jsonl", inputs)
        authorizations += [a for i in inputs for a in i["authorizations"]]
    write_jsonl(out_dir / "authorizations.jsonl", authorizations)
    summary = {
        "generator_version": GENERATOR_VERSION,
        "scenario_version": SCENARIO_VERSION,
        "policy_set": POLICY_SET,
        "prompt_version": PROMPT_V3,
        "rules_version": RULES_VERSION,
        "retrieval": built["splits"]["train"][0][0]["metadata"]["retrieval"],
        "seed": seed,
        "sizes": {split: len(records) for split, (records, _) in built["splits"].items()},
        "distribution": {s: distribution(r) for s, (r, _) in built["splits"].items()},
        "labels": {s: label_report(r) for s, (r, _) in built["splits"].items()},
        "lengths": {s: record_lengths(r) for s, (r, _) in built["splits"].items()},
        "checks": {"problems": 0, **{k: v for k, v in checks.items() if k != "problems"}},
    }
    write_json(out_dir / "summary.json", summary)
    card = data_card_v2(summary)
    (out_dir / "data-card.md").write_text(card, encoding="utf-8")
    if out_dir == OUT_DIR:  # the committed copy (aggregates only, no claim data)
        DOCS_CARD.write_text(card, encoding="utf-8")
    return summary


def main(seed: int, sizes: Mapping[str, int], out: Path) -> None:
    summary = write_dataset_v2(out, seed, sizes)
    print(json.dumps(summary["sizes"]), "checks passed;", json.dumps(summary["lengths"]))
