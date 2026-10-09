"""Policies v2 and retrieval planning (report only): what the decided v2 policy changes touch
before any policy file changes.

- the dataset lines (every split) and the golden cases that reference a v1 criterion the plan
  replaces with a new ID (a changed meaning gets a new ID; FOOT-001.c3 keeps its ID, only its
  source changes);
- the v1 labels that D-GEN-3 contradicts: an exclusion criterion labelled MET;
- the nerve-conduction test labels that contradict L34594 cov-037 (D-RULE-6): an R17-flagged line
  (no needle EMG on the claim) without a carpal tunnel diagnosis, labelled APPROVE or PEND;
- for the SURG-002.F3 limitations (D-V2-2): which of their diagnosis codes A56456 covers, so R15
  cannot catch them and the policy needs an exclusion criterion.

Nothing under data/curated/coverage_policies/ is changed (frozen for model v1). Codes only; no
CPT descriptor text is read out (H10).

    uv run python -m scripts.verify.policies_v2_plan
    # prints the report and writes data/generated/verification/policies_v2_plan.md
"""

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.db import raw
from scripts.verify.rules_v2_impact import (
    CARPAL_TUNNEL,
    Line,
    check_r17,
    load_lookups,
    load_records,
    r15_supported,
)
from scripts.verify.rules_v2_impact import lines_of as rule_lines_of

ROOT = Path(__file__).resolve().parents[2]
DECISION_DIR = ROOT / "data" / "generated" / "decision"
SPLITS = ("train", "validation", "test")
E2E_CASES = ROOT / "tests" / "golden" / "e2e" / "cases.json"
RAG_QUERIES = ROOT / "tests" / "golden" / "rag" / "queries.json"
TESTS_DIR = ROOT / "tests"
SKIPPED_DIRS = ("blind_review",)  # never opened
OUT = ROOT / "data" / "generated" / "verification" / "policies_v2_plan.md"
CRITERION = re.compile(r"POL-[A-Z]+-[0-9]{3}\.c[0-9]+")

# v1 criterion -> (decision, proposed v2 IDs). Every row is a changed meaning, so a new ID.
REPLACED: dict[str, tuple[str, str]] = {
    "POL-CAR-001.c1": ("D-V2-1", "c4 requirement + c5 exclusion"),
    "POL-CAR-002.c1": ("D-V2-1, CAR-002.F1 note", "c4"),
    "POL-CAR-002.c2": ("D-V2-2 CAR-002.F1", "c5"),
    "POL-CAR-002.c3": ("D-V2-1", "c6 + c7"),
    "POL-DX-001.c2": ("D-V2-1", "c4"),
    "POL-DX-003.c1": ("D-V2-2 DX-003.F1", "c4 + c5"),
    "POL-PAIN-001.c2": ("D-ESI-2", "c6"),
    "POL-PAIN-001.c4": ("D-ESI-7", "c7"),
    "POL-PAIN-001.c5": ("D-ESI-2, V1a open item", "c8"),
    "POL-PAIN-002.c4": ("D-V2-1", "c5"),
    "POL-REHAB-001.c2": ("D-V2-2 REHAB-001.F1, F2", "c4 + c5"),
    "POL-SURG-002.c1": ("D-V2-2 SURG-002.F1", "c4"),
    "POL-SURG-002.c2": ("D-V2-1", "c5"),
    "POL-SURG-004.c1": ("D-V2-2 SURG-004.F1", "c5"),
    "POL-SURG-004.c2": ("D-V2-2 SURG-004.F1", "c6"),
    "POL-SURG-004.c3": ("D-V2-2 SURG-004.F1", "c7"),
    "POL-SURG-004.c4": ("D-V2-2 SURG-004.F1", "c8"),
    "POL-WOUND-001.c3": ("D-V2-2 WOUND-001.F3", "c4"),
}
# New criteria with no v1 predecessor: their policy's lines gain a criterion.
ADDED = {
    "POL-PAIN-001": "c9 exclusion (D-ESI-4)",
    "POL-SURG-002": "c6 exclusion (D-V2-2 SURG-002.F3)",
    "POL-DX-002": "c4 exclusion (D-RULE-6, L34594 cov-037)",
}
# v1 criteria whose proposed type is exclusion (D-ESI-6, D-GEN-3): never MET.
V1_EXCLUSIONS = (
    "POL-BH-001.c2",
    "POL-BH-001.c3",
    "POL-DX-002.c2",
    "POL-DX-002.c3",
    "POL-FOOT-001.c3",
    "POL-IMG-001.c4",
    "POL-IMG-002.c2",
    "POL-SURG-001.c2",
    "POL-SURG-003.c2",
    "POL-SURG-003.c3",
    "POL-SURG-004.c4",
)
# SURG-002.F3: the L34005 limitations that a diagnosis code can express (ICD-10-CM description
# patterns); the others are situations (routine follow-up, pre-operative, a demonstrated upper
# source, fulminant colitis, possible perforation) and always need the criterion.
LIMITATION_CODES = {
    "cov-037 irritable bowel syndrome": r"irritable bowel",
    "cov-037 chronic abdominal pain": r"\babdominal pain\b|^(?:right|left) (?:upper|lower) "
    r"quadrant pain|^(?:epigastric|periumbilical|generalized abdominal) pain",
    "cov-038 diarrhea (acute is not coded)": r"\bdiarrh",
    "cov-039 hemorrhoids": r"hemorrhoid",
    "cov-040 malignancy of unknown primary": r"secondary malignant neoplasm of unspecified site"
    r"|disseminated malignant neoplasm|malignant \(primary\) neoplasm, unspecified",
    "cov-048 diverticulitis": r"diverticulitis of (?:large|both small and large) intestine",
    "cov-049 diverticulosis": r"diverticulosis of (?:large|both small and large) intestine",
}
SURG_002_CODE = "45378"  # the policy's first code; 45380 and 45385 share the article (A56456)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(row) for row in f]


def dataset_rows() -> Iterable[tuple[str, str, dict[str, Any], dict[str, Any] | None]]:
    """(split, record ID, context line, target line or None) for every line shown criteria."""
    for split in SPLITS:
        for row in read_jsonl(DECISION_DIR / f"{split}_inputs.jsonl"):
            targets = {x["line_no"]: x for x in (row.get("target") or {}).get("lines", [])}
            for line in row["context"]["lines"]:
                yield split, row["record_id"], line, targets.get(line["line_no"])


def statuses(target: dict[str, Any] | None) -> dict[str, str]:
    return {c["criterion_id"]: c["status"] for c in (target or {}).get("criteria", [])}


def dataset_section() -> list[str]:
    shown: Counter[tuple[str, str]] = Counter()
    used: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    records: dict[str, set[str]] = defaultdict(set)
    policy_lines: Counter[tuple[str, str]] = Counter()
    exclusion_met: Counter[tuple[str, str]] = Counter()
    exclusion_records: dict[str, set[str]] = defaultdict(set)
    for split, record_id, line, target in dataset_rows():
        found = statuses(target)
        ids = [c["criterion_id"] for c in line["criteria"]]
        for policy in {c["policy_id"] for c in line["criteria"]}:
            policy_lines[(policy, split)] += 1
        for cid in ids:
            if cid in REPLACED:
                shown[(cid, split)] += 1
                records[cid].add(record_id)
                status = found.get(cid)
                if status and status != "NOT_APPLICABLE":
                    used[(cid, split)][status] += 1
            if cid in V1_EXCLUSIONS and found.get(cid) == "MET":
                exclusion_met[(cid, split)] += 1
                exclusion_records[cid].add(record_id)

    out = [
        "## Dataset lines that reference a replaced v1 criterion",
        "",
        "Shown: the line's prompt lists the criterion. Used: its gold status is not "
        "NOT_APPLICABLE (status counts). Lines decided by a rule have no gold criteria.",
        "",
        "| v1 criterion | Decision | v2 IDs | Shown (train / validation / test) | Used, train | "
        "Used, validation | Used, test | Records |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cid, (decision, v2) in REPLACED.items():
        counts = " / ".join(str(shown[(cid, s)]) for s in SPLITS)
        cells = [
            ", ".join(f"{k} {n}" for k, n in sorted(used[(cid, s)].items())) or "-" for s in SPLITS
        ]
        out.append(
            f"| {cid} | {decision} | {v2} | {counts} | {' | '.join(cells)} | {len(records[cid])} |"
        )
    total_shown = sum(shown.values())
    total_used = sum(sum(c.values()) for c in used.values())
    out += [
        "",
        f"- Total: shown {total_shown}, used {total_used}; records with any replaced criterion: "
        f"{len(set().union(*records.values()))}.",
        "",
        "Lines of the policies that gain a new criterion (all of the policy's lines change):",
        "",
    ]
    out += [
        f"- {policy} {what}: "
        + " / ".join(f"{s} {policy_lines[(policy, s)]}" for s in SPLITS)
        + " lines"
        for policy, what in ADDED.items()
    ]
    out += [
        "",
        "## v1 labels that D-GEN-3 contradicts (an exclusion criterion labelled MET)",
        "",
        "| v1 criterion (proposed type exclusion) | MET (train / validation / test) | Records |",
        "|---|---|---|",
    ]
    for cid in V1_EXCLUSIONS:
        counts = " / ".join(str(exclusion_met[(cid, s)]) for s in SPLITS)
        out.append(f"| {cid} | {counts} | {len(exclusion_records[cid])} |")
    out.append(f"\n- Total MET on exclusion criteria: {sum(exclusion_met.values())}.")
    return out


def golden_section() -> list[str]:
    out = ["", "## Golden cases and tests that reference a replaced v1 criterion", ""]
    e2e = json.loads(E2E_CASES.read_text(encoding="utf-8"))["cases"]
    hits = [
        (c["case_id"], sorted(set(CRITERION.findall(json.dumps(c))) & set(REPLACED))) for c in e2e
    ]
    hits = [(k, v) for k, v in hits if v]
    out.append(
        f"- tests/golden/e2e/cases.json ({len(e2e)} cases): "
        + ("; ".join(f"{k} {' '.join(v)}" for k, v in hits) or "none")
    )
    rag = json.loads(RAG_QUERIES.read_text(encoding="utf-8"))["queries"]
    rag_hits = [
        (q["query_id"], sorted(set(q["expected_criterion_ids"]) & set(REPLACED))) for q in rag
    ]
    rag_hits = [(k, v) for k, v in rag_hits if v]
    expected = sum(len(q["expected_criterion_ids"]) for q in rag)
    out.append(
        f"- tests/golden/rag/queries.json ({len(rag)} queries, {expected} expected IDs): "
        + ("; ".join(f"{k} {' '.join(v)}" for k, v in rag_hits) or "none")
    )
    policies_added = set(ADDED)
    rag_added = [
        q["query_id"]
        for q in rag
        if {cid.split(".")[0] for cid in q["expected_criterion_ids"]} & policies_added
    ]
    out.append(
        "- RAG queries on a policy that gains a criterion: " + (", ".join(rag_added) or "none")
    )
    files: list[str] = []
    for path in sorted(TESTS_DIR.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".json", ".csv", ".md"}:
            continue
        if any(part in SKIPPED_DIRS for part in path.parts):
            continue
        if path in (E2E_CASES, RAG_QUERIES):
            continue
        found = set(CRITERION.findall(path.read_text(encoding="utf-8"))) & set(REPLACED)
        if found:
            files.append(f"{path.relative_to(ROOT)} ({' '.join(sorted(found))})")
    out.append(
        "- Other test files naming a replaced criterion (tests/golden/blind_review not opened): "
        + ("; ".join(files) or "none")
    )
    return out


def ncs_section() -> list[str]:
    targets = {
        (row["record_id"], x["line_no"]): statuses(x)
        for split in SPLITS
        for row in read_jsonl(DECISION_DIR / f"{split}_inputs.jsonl")
        for x in (row.get("target") or {}).get("lines", [])
    }
    rows: list[str] = []
    for r in load_records():
        lines = rule_lines_of(r.claim)
        by_no = {x.line_no: x for x in lines}
        for h in check_r17(lines):
            label = r.labels.get(h.line_no, "")
            line = by_no[h.line_no]
            if label not in ("MODEL APPROVE", "MODEL PEND") or CARPAL_TUNNEL & set(line.diagnoses):
                continue
            found = targets.get((r.record_id, h.line_no), {})
            criteria = ", ".join(f"{k.split('.')[1]} {v}" for k, v in sorted(found.items()))
            rows.append(
                f"| {r.record_id} | {r.split} | {h.line_no} | {line.code} | "
                f"{' '.join(line.diagnoses)} | {label.split()[1]} | {r.scenario} | {criteria} |"
            )
    return [
        "",
        "## Nerve-conduction labels that contradict L34594 cov-037 (D-RULE-6)",
        "",
        "R17-flagged lines (a nerve conduction code, no needle EMG code on the claim) without a "
        "carpal tunnel diagnosis (G56.00-G56.03), labelled APPROVE or PEND. For the generator v2 "
        "task; the v1 dataset is not changed.",
        "",
        "| Record | Split | Line | Code | Diagnoses | Label | Scenario | DX-002 statuses |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        f"- Total: {len(rows)}.",
    ]


def limitations_section() -> list[str]:
    lookups = load_lookups()
    icd = raw.read_icd10_codes()
    support = lookups.curated.diagnosis_support[SURG_002_CODE]
    groups = lookups.covered[support.billing_article]
    out = [
        "",
        "## SURG-002.F3: which L34005 limitations R15 already catches",
        "",
        f"R15 for {SURG_002_CODE} ({support.billing_article}): {support.source}. A limitation is "
        "caught when a line whose diagnoses are only its codes fails R15; codes A56456 covers in "
        "group 1 pass R15 alone, so the policy needs the criterion.",
        "",
        "| Limitation | ICD-10-CM codes matched | In group 1 (R15 passes alone) | "
        "In groups 2 or 3 | Not covered |",
        "|---|---|---|---|---|",
    ]
    for name, pattern in LIMITATION_CODES.items():
        regex = re.compile(pattern, re.IGNORECASE)
        codes = sorted(c for c, d in icd.items() if regex.search(d))
        passes = [
            c
            for c in codes
            if r15_supported(Line(0, 1, SURG_002_CODE, "", 1, (), (c,), (0,)), lookups, True)
        ]
        later = groups.get(2, frozenset()) | groups.get(3, frozenset())
        other = [c for c in codes if c not in passes and c in later]
        neither = [c for c in codes if c not in passes and c not in other]
        out.append(
            f"| {name} | {len(codes)} | {' '.join(passes) or '-'} | {' '.join(other) or '-'} | "
            f"{len(neither)} |"
        )
    return out


def main() -> None:
    out = ["# Policies v2 and retrieval: impact before any policy change", ""]
    out += dataset_section()
    out += golden_section()
    out += ncs_section()
    out += limitations_section()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
