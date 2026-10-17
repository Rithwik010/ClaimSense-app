"""Is the v3 training set big enough? Two measurements for the v3 size decision (D-V3-6).

1. **v2's evidence:** for each policy, how many model-decided lines v2's training set had, against
   model v2's test error rate on that policy (the evaluation's error file).
2. **v3's coverage:** builds v3 training fact sheets on the CPU (no notes, no model), as the
   generator would for a training split of each size given, and counts what the model can learn
   from: model-decided lines per policy and per policy and decision, each criterion's label
   statuses, and the tricky facts (borderline values on each side, contradictions, negated
   exclusions, hedged mentions) per policy and per borderline criterion. The first N sheets of a
   bigger build are exactly the N-sheet build (the generator is seeded), so one build gives every
   size. Report only.

    uv run python -m scripts.verify.v3_coverage \\
        --v2 ../ClaimSense/data/generated/decision_v2 \\
        --v2-errors ../ClaimSense/data/generated/eval/v2/v2-errors.json \\
        --sizes 3000 4500 6000 9000 12000 [--out data/generated/v3/coverage.json]
"""

import argparse
import json
import statistics
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from training.generate.v3.config import config
from training.generate.v3.dataset import build_sheets, read_jsonl

STATUSES = ("MET", "NOT_MET", "NOT_DOCUMENTED", "NOT_APPLICABLE")
DECISIONS = ("APPROVE", "DENY", "PEND")
NO_CRITERIA = "(no criteria)"


def policy_of(criterion_id: str) -> str:
    return criterion_id.split(".")[0]


def line_policies(context: Mapping[str, Any]) -> dict[int, str]:
    """Each line's policy: the policy of its first retrieved criterion, else no criteria."""
    return {
        line["line_no"]: policy_of(line["criteria"][0]["criterion_id"])
        if line["criteria"]
        else NO_CRITERIA
        for line in context["lines"]
    }


# --- 1. v2: training lines against test errors ----------------------------------------------------


def v2_evidence(v2_dir: Path, errors_file: Path) -> list[dict[str, Any]]:
    train: Counter[str] = Counter()
    for row in read_jsonl(v2_dir / "train_inputs.jsonl"):
        policies = line_policies(row["context"])
        for line in row["target"]["lines"]:
            train[policies.get(line["line_no"], NO_CRITERIA)] += 1
    errors = json.loads(errors_file.read_text(encoding="utf-8"))["by_policy"]
    rows = []
    for policy in sorted(set(train) | set(errors)):
        tested = errors.get(policy, {})
        lines, wrong = tested.get("lines", 0), tested.get("wrong", 0)
        rows.append(
            {
                "policy": policy,
                "train_lines": train.get(policy, 0),
                "test_lines": lines,
                "test_wrong": wrong,
                "test_error_rate": round(wrong / lines, 3) if lines else None,
            }
        )
    return sorted(rows, key=lambda r: r["train_lines"])


# --- 2. v3: what a training split of each size holds ----------------------------------------------


def counts(sheets: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    lines: Counter[str] = Counter()
    decisions: Counter[tuple[str, str]] = Counter()
    statuses: Counter[tuple[str, str]] = Counter()
    tricky_by_policy: dict[str, Counter[str]] = defaultdict(Counter)
    borderline: Counter[tuple[str, str]] = Counter()
    rule_denied = 0
    for sheet in sheets:
        target = sheet["label"]["target"]
        policies = line_policies(sheet["inputs"]["context"])
        rule_denied += sum(
            o["outcome"] == "DENY" for o in sheet["inputs"]["rules_outcome"]["line_outcomes"]
        )
        for line in target["lines"]:
            policy = policies.get(line["line_no"], NO_CRITERIA)
            lines[policy] += 1
            decisions[(policy, line["decision"])] += 1
            for criterion in line["criteria"]:
                statuses[(criterion["criterion_id"], criterion["status"])] += 1
        for fact in sheet["facts"]:
            if fact["kind"] != "criterion":
                continue
            policy = policy_of(fact["criterion_id"])
            status = fact["status"]
            if status.startswith("borderline"):
                tricky_by_policy[policy]["borderline"] += 1
                borderline[(fact["criterion_id"], status.removeprefix("borderline_"))] += 1
            elif status in ("contradicted", "missing"):
                tricky_by_policy[policy][status] += 1
            if fact.get("negated"):
                tricky_by_policy[policy]["negated"] += 1
            if fact.get("hedge"):
                tricky_by_policy[policy]["hedged"] += 1
    return {
        "model_lines": sum(lines.values()),
        "rule_denied_lines": rule_denied,
        "lines_per_policy": dict(sorted(lines.items())),
        "lines_per_policy_and_decision": {f"{p} {d}": n for (p, d), n in sorted(decisions.items())},
        "criterion_statuses": {f"{c} {s}": n for (c, s), n in sorted(statuses.items())},
        "tricky_per_policy": {p: dict(c) for p, c in sorted(tricky_by_policy.items())},
        "borderline_per_criterion_side": {
            f"{c} {s}": n for (c, s), n in sorted(borderline.items())
        },
    }


def smallest(found: Mapping[str, int], k: int = 5) -> list[tuple[str, int]]:
    return sorted(found.items(), key=lambda item: item[1])[:k]


def summary(found: Mapping[str, Any], minimum: Mapping[str, int]) -> dict[str, Any]:
    """The thinnest cells, and how many cells are under each minimum."""
    statuses = found["criterion_statuses"]
    decisions = found["lines_per_policy_and_decision"]
    tricky = {
        f"{p} {kind}": n
        for p, kinds in found["tricky_per_policy"].items()
        for kind, n in kinds.items()
    }
    borderline = found["borderline_per_criterion_side"]
    return {
        "model_lines": found["model_lines"],
        "rule_denied_lines": found["rule_denied_lines"],
        "policy_lines_min": smallest(found["lines_per_policy"], 3),
        "policies_under_minimum": sum(
            n < minimum["policy_lines"] for n in found["lines_per_policy"].values()
        ),
        "policy_decision_cells": len(decisions),
        "policy_decision_cells_under_minimum": sum(
            n < minimum["policy_decision"] for n in decisions.values()
        ),
        "policy_decision_min": smallest(decisions),
        "criterion_status_cells": len(statuses),
        "criterion_status_cells_under_minimum": sum(
            n < minimum["criterion_status"] for n in statuses.values()
        ),
        "criterion_status_median": statistics.median(statuses.values()) if statuses else 0,
        "criterion_status_min": smallest(statuses),
        "tricky_cells": len(tricky),
        "tricky_cells_under_minimum": sum(n < minimum["tricky"] for n in tricky.values()),
        "tricky_min": smallest(tricky),
        "borderline_cells": len(borderline),
        "borderline_cells_under_minimum": sum(n < minimum["tricky"] for n in borderline.values()),
        "borderline_min": smallest(borderline),
    }


def v3_coverage(
    sizes: Sequence[int], minimum: Mapping[str, int], keep: Path | None
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        folder = keep or Path(tmp)
        folder.mkdir(parents=True, exist_ok=True)
        build_sheets(config()["seed"], folder, sizes={"train": max(sizes)})
        sheets = read_jsonl(folder / "sheets.jsonl")
    found = {}
    for size in sorted(sizes):
        part = counts(sheets[:size])
        found[str(size)] = {"summary": summary(part, minimum), "counts": part}
    return found


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--v2", type=Path, required=True, help="the decision_v2 folder")
    parser.add_argument("--v2-errors", type=Path, required=True, help="v2-errors.json")
    parser.add_argument("--sizes", type=int, nargs="+", default=[3000, 4500, 6000, 9000, 12000])
    parser.add_argument("--min-policy-lines", type=int, default=150)
    parser.add_argument("--min-policy-decision", type=int, default=30)
    parser.add_argument("--min-criterion-status", type=int, default=20)
    parser.add_argument("--min-tricky", type=int, default=30)
    parser.add_argument("--keep", type=Path, help="keep the built sheets in this folder")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    minimum = {
        "policy_lines": args.min_policy_lines,
        "policy_decision": args.min_policy_decision,
        "criterion_status": args.min_criterion_status,
        "tricky": args.min_tricky,
    }
    report = {
        "minimum": minimum,
        "v2_train_lines_vs_test_errors": v2_evidence(args.v2, args.v2_errors),
        "v3_train_coverage": v3_coverage(args.sizes, minimum, args.keep),
    }
    for row in report["v2_train_lines_vs_test_errors"]:
        print(
            f"v2 {row['policy']:<16} train lines {row['train_lines']:>4}  test "
            f"{row['test_wrong']}/{row['test_lines']} wrong ({row['test_error_rate']})"
        )
    for size, part in report["v3_train_coverage"].items():
        print(f"v3 train {size}: " + json.dumps(part["summary"]))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
