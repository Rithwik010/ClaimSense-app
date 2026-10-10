"""Task V1a: verify the decision-dataset labels against their sources (report only).

Reads every record of the train, validation and test splits and reports problems. It never changes
a record, a policy, a generator or anything frozen for model v1. Output goes to
`data/generated/verification/` (git-ignored):

- `A_labels_full.csv`: every flag
- `A_labels_check5_cues.csv`: how each NOT_APPLICABLE criterion was cleared or flagged (audit)
- `A_labels_review.md`: a short random sample for one human reviewer

    uv run python -m scripts.verify.label_checks

Checks, on every line the record's answer decides (lines denied by the rules have no label):

1. MCD: the line's diagnoses against the billing article's covered ICD-10-CM groups.
2. Decision rule: the decision follows from the criterion statuses.
3. Evidence: MET evidence appears word for word in the notes.
4. Criterion IDs: every labelled criterion was retrieved for the line.
5. NOT_APPLICABLE cue (triage only): some sentence is related to the criterion.
"""

import argparse
import copy
import csv
import io
import json
import math
import random
import re
import sys
import zipfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import Any, Protocol

from app.ml.prompt import format_icd10

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "data" / "generated" / "decision"
OUT_DIR = ROOT / "data" / "generated" / "verification"
SPLITS = ("train", "validation", "test")

CHECK_NAMES = {
    1: "1 MCD",
    2: "2 decision rule",
    3: "3 evidence",
    4: "4 criterion IDs",
    5: "5 NOT_APPLICABLE cue",
}
TRIAGE_NOTE = (
    "triage only: a cue means a related sentence exists, not that the label is proven right"
)
INSTRUCTION = "For each row write REAL ERROR, FALSE ALARM or UNSURE."
MINUTES_PER_ROW = 2
RANDOM_ROWS = 3
LOWEST_ROWS = 2  # check 5 also shows its lowest-similarity flags
SEED = 42

DX_SCENARIO = "deny_dx"  # the record says the denial rests on the diagnosis
NOT_NECESSARY = "DN_NOT_MEDICALLY_NECESSARY"
NCCI_BYPASS = "NCCI_BYPASS"
DESCRIPTOR_OMITTED = "[AMA CPT descriptor omitted]"
HCPC_DESCRIPTOR_COLUMNS = (5, 6)  # long_description, short_description

WORD = re.compile(r"[a-z]+")
# A 5-digit CPT code, or an in-scope code named in the text.
CODE = re.compile(r"\b(?:\d{5}|[A-Z]\d{4})\b")
# What a criterion is about: the words before its first verb of obligation or coverage.
SUBJECT_END = re.compile(
    r"\b(?:is|are|was|were|must|requires?|needs?|can|should|may)\b", re.IGNORECASE
)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# A subject headed by the patient describes who qualifies, so it names no procedure (the audit
# found "Patients identified as high risk for colon cancer" matching a colonoscopy code's "colon").
PATIENT_SUBJECT = re.compile(r"(?:the\s+)?patients?\b", re.IGNORECASE)
FUNCTION_WORDS = frozenset(
    "the and for with that this than then more one two each per first any all not but are was "
    "were has have had its their from into only also when other such both before after under "
    "over out off can may must should will been being".split()
)


@dataclass(frozen=True)
class Support:
    """A procedure's billing article and ICD-10 group combinations (`1|2+3` = ((1,), (2, 3)))."""

    article: str
    alternatives: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class Lookups:
    support: Mapping[str, Support]  # procedure code -> billing article and group rule
    covered: Mapping[str, Mapping[int, frozenset[str]]]  # article -> group -> ICD-10 (no dots)
    versions: Mapping[str, str]  # article -> current version
    descriptions: Mapping[str, str]  # procedure code -> the project's plain-English description
    icd10: Mapping[str, str]  # ICD-10-CM code -> description
    policy_codes: Mapping[str, tuple[str, ...]]  # policy ID -> procedure codes it covers
    criterion_text: Mapping[str, str] = field(default_factory=dict)
    criterion_policy: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Record:
    split: str
    record_id: str
    scenario_type: str
    claim: dict[str, Any]
    rules: dict[str, Any]
    context: dict[str, Any]
    target: dict[str, Any]

    @classmethod
    def from_dataset(cls, split: str, record: dict[str, Any], inputs: dict[str, Any]) -> "Record":
        metadata = record["metadata"]
        return cls(
            split=split,
            record_id=metadata["record_id"],
            scenario_type=metadata.get("scenario_type", ""),
            claim=inputs["claim"],
            rules=inputs["rules_outcome"],
            context=inputs["context"],
            target=json.loads(record["messages"][-1]["content"]),
        )

    @property
    def lines(self) -> list[dict[str, Any]]:
        return self.target["lines"]

    @property
    def notes(self) -> str:
        return self.claim["clinical_notes"]

    def service_line(self, line_no: int) -> dict[str, Any]:
        return next(s for s in self.claim["service_lines"] if s["line_no"] == line_no)

    def procedure(self, line_no: int) -> str:
        return self.service_line(line_no)["procedure_code"]

    def diagnoses(self, line_no: int) -> list[str]:
        pointers = self.service_line(line_no)["diagnosis_pointers"]
        return [self.claim["diagnoses"][ord(p) - ord("A")] for p in pointers]

    def rule_flags(self, line_no: int) -> list[str]:
        outcomes = self.rules["line_outcomes"]
        return next((o.get("flags", []) for o in outcomes if o["line_no"] == line_no), [])

    def retrieved(self, line_no: int) -> list[dict[str, Any]]:
        lines = self.context["lines"]
        return next((line["criteria"] for line in lines if line["line_no"] == line_no), [])


@dataclass(frozen=True)
class Flag:
    check: int
    split: str
    record_id: str
    line_no: int
    what: str
    left: str
    right: str
    look_up: str
    criterion_id: str = ""
    score: float | None = None
    kind: str = ""
    mcd: tuple[str, str, str, tuple[str, ...]] | None = None  # article, version, code, diagnoses
    source_rows: str = ""


class Similarity(Protocol):
    def scores(self, criterion: str, candidates: Sequence[str]) -> list[float]: ...


def _in_split(record: Record) -> str:
    return f"data/generated/decision/{record.split}.jsonl → {record.record_id}"


# --- check 1: MCD ---------------------------------------------------------------------------


def supported(
    diagnoses: Sequence[str],
    rule: Support,
    covered: Mapping[str, Mapping[int, frozenset[str]]],
) -> bool:
    """True when, for at least one group combination, every group has one of the diagnoses."""
    groups = covered.get(rule.article, {})
    return any(
        all(any(dx in groups.get(group, frozenset()) for dx in diagnoses) for group in alternative)
        for alternative in rule.alternatives
    )


def _rule_text(rule: Support) -> str:
    return " | ".join("+".join(f"group {g}" for g in alt) for alt in rule.alternatives)


def _diagnosis_text(record: Record, line_no: int, lookups: Lookups) -> str:
    pointers = record.service_line(line_no)["diagnosis_pointers"]
    parts = [
        f"{p}: {format_icd10(dx)} {lookups.icd10.get(dx, '(not in ICD-10-CM FY2027)')}"
        for p, dx in zip(pointers, record.diagnoses(line_no), strict=True)
    ]
    return "Diagnoses: " + "; ".join(parts)


def _mcd_text(diagnoses: Sequence[str], rule: Support, lookups: Lookups) -> str:
    groups = lookups.covered.get(rule.article, {})
    version = lookups.versions.get(rule.article, "?")
    wanted = sorted({g for alt in rule.alternatives for g in alt})
    parts = [f"MCD {rule.article} v{version}, rule: {_rule_text(rule)}"]
    for group in wanted:
        codes = sorted(groups.get(group, frozenset()))
        near = [c for c in codes if any(c[:3] == dx[:3] for dx in diagnoses)][:5]
        sample = ", ".join(format_icd10(c) for c in (near or codes[:5]))
        label = "same category" if near else "first codes"
        parts.append(f"group {group}: {len(codes)} codes ({label}: {sample or 'none'})")
    for dx in diagnoses:
        found = [g for g in wanted if dx in groups.get(g, frozenset())]
        where = ", ".join(f"group {g}" for g in found) if found else "no required group"
        parts.append(f"{format_icd10(dx)} is in {where}")
    return "; ".join(parts)


def check_mcd(record: Record, lookups: Lookups) -> tuple[list[Flag], int]:
    """(flags, lines not checkable because the procedure has no billing article)."""
    flags, not_checkable = [], 0
    for line in record.lines:
        line_no = line["line_no"]
        code = record.procedure(line_no)
        rule = lookups.support.get(code)
        if rule is None:
            not_checkable += 1
            continue
        diagnoses = record.diagnoses(line_no)
        ok = supported(diagnoses, rule, lookups.covered)
        decision = line["decision"]
        if decision in ("APPROVE", "PEND") and not ok:
            kind = f"{decision} not covered"
            what = f"{decision} line, but its diagnoses do not satisfy the article's covered rule"
            if decision == "PEND":
                what += " (by the decision rule's precedence it should be DENY)"
        elif (
            decision == "DENY"
            and record.scenario_type == DX_SCENARIO
            and NOT_NECESSARY in line.get("reasons", [])
            and ok
        ):
            kind = "diagnosis-based DENY covered"
            what = "diagnosis-based DENY, but the article covers the diagnosis"
        else:
            continue
        version = lookups.versions.get(rule.article, "?")
        flags.append(
            Flag(
                check=1,
                split=record.split,
                record_id=record.record_id,
                line_no=line_no,
                what=f"{what} (procedure {code})",
                left=_diagnosis_text(record, line_no, lookups),
                right=_mcd_text(diagnoses, rule, lookups),
                look_up=(
                    f"{_in_split(record)}, line {line_no}; MCD article {rule.article} v{version}: "
                    "data/raw/mcd/2026-09-21/current_article.zip → current_article_csv.zip"
                ),
                kind=kind,
                mcd=(rule.article, version, code, tuple(diagnoses)),
            )
        )
    return flags, not_checkable


# --- check 2: decision rule -----------------------------------------------------------------


def implied_decision(statuses: Iterable[str]) -> str:
    statuses = list(statuses)
    if "NOT_MET" in statuses:
        return "DENY"
    if "NOT_DOCUMENTED" in statuses:
        return "PEND"
    return "APPROVE"


def check_decision_rule(record: Record) -> tuple[list[Flag], int]:
    """(flags, NCCI-bypass PEND lines exempted by the prompt's rule)."""
    flags, exempt = [], 0
    for line in record.lines:
        line_no = line["line_no"]
        statuses = [c["status"] for c in line["criteria"]]
        implied = implied_decision(statuses)
        decision = line["decision"]
        if implied == decision:
            continue
        rule_flags = record.rule_flags(line_no)
        if (
            NCCI_BYPASS in rule_flags
            and decision == "PEND"
            and not {"NOT_MET", "NOT_DOCUMENTED"} & set(statuses)
        ):
            exempt += 1
            continue
        listed = ", ".join(f"{c['criterion_id']} {c['status']}" for c in line["criteria"])
        flags.append(
            Flag(
                check=2,
                split=record.split,
                record_id=record.record_id,
                line_no=line_no,
                what=f"labelled {decision}, but the statuses imply {implied}",
                left=f"Statuses: {listed or 'no criteria'}",
                right=(
                    f"Decision: {decision}; reasons: {', '.join(line.get('reasons', [])) or 'none'}"
                    f"; rule flags: {', '.join(rule_flags) or 'none'}"
                ),
                look_up=f"{_in_split(record)}, line {line_no} (last message); flags in "
                f"{record.split}_inputs.jsonl → rules_outcome",
                kind=f"{decision} but implies {implied}",
            )
        )
    return flags, exempt


# --- check 3: evidence ----------------------------------------------------------------------


def check_evidence(record: Record) -> tuple[list[Flag], int]:
    """(flags, MET criteria checked)."""
    flags, checked = [], 0
    for line in record.lines:
        for criterion in line["criteria"]:
            if criterion["status"] != "MET":
                continue
            checked += 1
            if criterion["evidence"] in record.notes:
                continue
            flags.append(
                Flag(
                    check=3,
                    split=record.split,
                    record_id=record.record_id,
                    line_no=line["line_no"],
                    criterion_id=criterion["criterion_id"],
                    what=f"MET evidence for {criterion['criterion_id']} is not in the notes "
                    "word for word",
                    left=f"Evidence: {criterion['evidence']}",
                    right=f"Notes: {record.notes}",
                    look_up=f"{_in_split(record)}, line {line['line_no']}; notes in "
                    f"{record.split}_inputs.jsonl → claim.clinical_notes",
                    kind="evidence not verbatim",
                )
            )
    return flags, checked


# --- check 4: criterion IDs -----------------------------------------------------------------


def check_criterion_ids(record: Record) -> list[Flag]:
    flags = []
    for line in record.lines:
        retrieved = [c["criterion_id"] for c in record.retrieved(line["line_no"])]
        for criterion in line["criteria"]:
            if criterion["criterion_id"] in retrieved:
                continue
            flags.append(
                Flag(
                    check=4,
                    split=record.split,
                    record_id=record.record_id,
                    line_no=line["line_no"],
                    criterion_id=criterion["criterion_id"],
                    what=f"{criterion['criterion_id']} was not retrieved for this line",
                    left=f"Labelled: {criterion['criterion_id']} {criterion['status']}",
                    right=f"Retrieved for line {line['line_no']}: {', '.join(retrieved) or 'none'}",
                    look_up=f"{_in_split(record)}, line {line['line_no']}; retrieved set in "
                    f"{record.split}_inputs.jsonl → context.lines[].criteria",
                    kind="not retrieved",
                )
            )
    return flags


# --- check 5: NOT_APPLICABLE cue ------------------------------------------------------------


def content_words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if len(w) > 2 and w not in FUNCTION_WORDS}


def subject(text: str) -> str:
    match = SUBJECT_END.search(text)
    return (text[: match.start()] if match else text).strip()


def structural_cue(
    text: str, line_code: str, policy_codes: Sequence[str], descriptions: Mapping[str, str]
) -> str | None:
    """A deterministic reason the criterion is about another procedure, or None.

    Either the text names a procedure code that is not the line's, or the criterion's subject
    names a word found in another code's description and in no other description of the policy,
    while naming none of the line's own such words."""
    for code in CODE.findall(text):
        if code != line_code and (code.isdigit() or code in descriptions):
            return f"names procedure code {code}, not the line's {line_code}"
    words = {c: content_words(descriptions.get(c, "")) for c in policy_codes}
    unique = {
        c: words[c] - set().union(*(words[o] for o in policy_codes if o != c)) for c in policy_codes
    }
    head = subject(text)
    if PATIENT_SUBJECT.match(head):  # the criterion is about the patient, not a procedure
        return None
    about = content_words(head)
    if about & unique.get(line_code, set()):
        return None
    hits = {c: sorted(about & terms) for c, terms in unique.items() if c != line_code}
    named = "; ".join(f"{c} ({', '.join(terms)})" for c, terms in sorted(hits.items()) if terms)
    return f"subject names {named}, not the line's {line_code}" if named else None


def note_sentences(notes: str) -> list[str]:
    return [s for s in SENTENCE_END.split(notes.strip()) if s]


def check_not_applicable(
    record: Record, lookups: Lookups, similarity: Similarity, threshold: float
) -> tuple[list[Flag], list[dict[str, Any]]]:
    """(flags for "no cue found", one audit row per NOT_APPLICABLE criterion)."""
    flags, cues = [], []
    for line in record.lines:
        line_no = line["line_no"]
        code = record.procedure(line_no)
        retrieved = {c["criterion_id"]: c for c in record.retrieved(line_no)}
        for criterion in line["criteria"]:
            if criterion["status"] != "NOT_APPLICABLE":
                continue
            criterion_id = criterion["criterion_id"]
            info = retrieved.get(criterion_id, {})
            text = info.get("text") or lookups.criterion_text.get(criterion_id, "")
            policy = info.get("policy_id") or lookups.criterion_policy.get(criterion_id, "")
            audit = {
                "split": record.split,
                "record_id": record.record_id,
                "line_no": line_no,
                "procedure_code": code,
                "criterion_id": criterion_id,
            }
            cue = structural_cue(
                text, code, lookups.policy_codes.get(policy, (code,)), lookups.descriptions
            )
            if cue:
                cues.append(
                    {
                        **audit,
                        "result": "structural",
                        "source": "structural",
                        "matched": cue,
                        "score": "",
                    }
                )
                continue
            candidates = [(s, "notes") for s in note_sentences(record.notes)]
            if code in lookups.descriptions:
                candidates.append((lookups.descriptions[code], "procedure description"))
            candidates += [
                (lookups.icd10[dx], "diagnosis description")
                for dx in record.diagnoses(line_no)
                if dx in lookups.icd10
            ]
            scores = similarity.scores(text, [c for c, _ in candidates]) if candidates else []
            best = max(range(len(scores)), key=scores.__getitem__) if scores else None
            score = round(scores[best], 4) if best is not None else 0.0
            closest, source = candidates[best] if best is not None else ("", "")
            found = score >= threshold
            cues.append(
                {
                    **audit,
                    "result": "cue found" if found else "no cue found",
                    "source": source,
                    "matched": closest,
                    "score": score,
                }
            )
            if found:
                continue
            flags.append(
                Flag(
                    check=5,
                    split=record.split,
                    record_id=record.record_id,
                    line_no=line_no,
                    criterion_id=criterion_id,
                    what=f"{criterion_id} NOT_APPLICABLE, no related sentence ({TRIAGE_NOTE})",
                    left=f"Criterion {criterion_id}: {text}",
                    right=(
                        f"Notes: {record.notes} Closest ({source}, similarity {score:.3f}, "
                        f"threshold {threshold:.3f}): {closest}"
                    ),
                    look_up=f"{_in_split(record)}, line {line_no}; criterion in "
                    f"data/curated/coverage_policies/v1/{policy}.md",
                    score=score,
                    kind="no cue found",
                )
            )
    return flags, cues


class WordOverlap:
    """Share of the criterion's content words found in a candidate (self-test and unit tests)."""

    def scores(self, criterion: str, candidates: Sequence[str]) -> list[float]:
        words = content_words(criterion)
        if not words:
            return [0.0 for _ in candidates]
        return [len(words & content_words(c)) / len(words) for c in candidates]


class EmbeddingSimilarity:
    """Cosine similarity with the project's embedding model, both texts embedded as passages."""

    def __init__(self, embedder: Any) -> None:
        self._embedder = embedder
        self._vectors: dict[str, tuple[list[float], float]] = {}

    def prepare(self, texts: Iterable[str]) -> None:
        todo = sorted({t for t in texts if t and t not in self._vectors})
        for text, vector in zip(todo, self._embedder.embed_documents(todo), strict=True):
            self._vectors[text] = (vector, math.sqrt(sum(x * x for x in vector)) or 1.0)

    def scores(self, criterion: str, candidates: Sequence[str]) -> list[float]:
        self.prepare([criterion, *candidates])
        a, norm_a = self._vectors[criterion]
        results = []
        for candidate in candidates:
            b, norm_b = self._vectors[candidate]
            results.append(sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b))
        return results


def calibrate(pairs: Sequence[tuple[str, str]], similarity: Similarity) -> float:
    """5th percentile (nearest rank) of criterion-to-own-evidence similarity over MET labels."""
    values = sorted(similarity.scores(criterion, [evidence])[0] for criterion, evidence in pairs)
    return values[max(1, math.ceil(0.05 * len(values))) - 1]


# --- planted cases: the unit tests and the runtime self-test --------------------------------

PLANTED_THRESHOLD = 0.34
NOTES = (
    "Low back pain radiating down the left leg for eight weeks. MRI shows a disc herniation. "
    "Pain has lasted eight weeks despite physical therapy. Plan: epidural steroid injection."
)
CRITERIA = {
    "POL-PLANT-001.c1": "History and imaging must support nerve-root pain from a disc herniation.",
    "POL-PLANT-001.c2": "Pain must have lasted at least four weeks despite conservative care.",
    "POL-PLANT-001.c3": "Sleep studies must be read by a certified sleep physician.",
    "POL-PLANT-001.c4": "Nerve root injections are covered at one level per session.",
    "POL-PLANT-001.c5": "Radiating leg pain must be documented before treatment.",
}


@dataclass(frozen=True)
class PlantedCase:
    name: str
    check: int
    record: Record
    expect_flag: bool


def planted_lookups() -> Lookups:
    return Lookups(
        support={"62323": Support(article="A0001", alternatives=((1,),))},
        covered={"A0001": {1: frozenset({"M5416"})}},
        versions={"A0001": "1"},
        descriptions={
            "62323": "Epidural steroid injection between the vertebrae, lower back",
            "64483": "Epidural steroid injection beside the nerve root, lower back, first level",
        },
        icd10={
            "M5416": "Radiculopathy, lumbar region",
            "J069": "Acute upper respiratory infection",
        },
        policy_codes={"POL-PLANT-001": ("62323", "64483")},
        criterion_text=dict(CRITERIA),
        criterion_policy={c: "POL-PLANT-001" for c in CRITERIA},
    )


def _base_record() -> Record:
    retrieved = [
        {"criterion_id": c, "policy_id": "POL-PLANT-001", "text": t} for c, t in CRITERIA.items()
    ]
    return Record(
        split="planted",
        record_id="PLANTED",
        scenario_type="approve_single",
        claim={
            "diagnoses": ["M5416"],
            "service_lines": [
                {"line_no": 1, "procedure_code": "62323", "diagnosis_pointers": ["A"]}
            ],
            "clinical_notes": NOTES,
        },
        rules={"line_outcomes": [{"line_no": 1, "outcome": "PASS", "flags": []}]},
        context={"lines": [{"line_no": 1, "criteria": retrieved}]},
        target={
            "lines": [
                {
                    "line_no": 1,
                    "decision": "APPROVE",
                    "criteria": [
                        {
                            "criterion_id": "POL-PLANT-001.c1",
                            "status": "MET",
                            "evidence": "MRI shows a disc herniation.",
                        },
                        {
                            "criterion_id": "POL-PLANT-001.c2",
                            "status": "MET",
                            "evidence": "Pain has lasted eight weeks despite physical therapy.",
                        },
                    ],
                    "reasons": [],
                    "missing_information": [],
                }
            ]
        },
    )


def _variant(
    *,
    decision: str | None = None,
    statuses: Sequence[str] | None = None,
    diagnoses: Sequence[str] | None = None,
    scenario_type: str | None = None,
    reasons: Sequence[str] | None = None,
    rule_flags: Sequence[str] | None = None,
    evidence: str | None = None,
    extra: Sequence[dict[str, str]] = (),
) -> Record:
    record = _base_record()
    claim, rules, target = (copy.deepcopy(x) for x in (record.claim, record.rules, record.target))
    line = target["lines"][0]
    if decision is not None:
        line["decision"] = decision
    for criterion, status in zip(line["criteria"], statuses or (), strict=False):
        criterion["status"] = status
        if status == "NOT_DOCUMENTED":
            criterion["evidence"] = "Not documented in the clinical notes."
    if evidence is not None:
        line["criteria"][0]["evidence"] = evidence
    if diagnoses is not None:
        claim["diagnoses"] = list(diagnoses)
    if reasons is not None:
        line["reasons"] = list(reasons)
    if rule_flags is not None:
        rules["line_outcomes"][0]["flags"] = list(rule_flags)
    line["criteria"] += [dict(c) for c in extra]
    return replace(
        record,
        claim=claim,
        rules=rules,
        target=target,
        scenario_type=scenario_type or record.scenario_type,
    )


def _not_applicable(criterion_id: str) -> dict[str, str]:
    return {
        "criterion_id": criterion_id,
        "status": "NOT_APPLICABLE",
        "evidence": "Does not apply to this service.",
    }


def planted_cases() -> list[PlantedCase]:
    """One wrong record per check (and the correct records each check must leave alone)."""
    return [
        PlantedCase("1: APPROVE line, diagnosis covered", 1, _variant(), False),
        PlantedCase(
            "1: APPROVE line, diagnosis not covered", 1, _variant(diagnoses=["J069"]), True
        ),
        PlantedCase(
            "1: PEND line, diagnosis not covered",
            1,
            _variant(decision="PEND", statuses=["MET", "NOT_DOCUMENTED"], diagnoses=["J069"]),
            True,
        ),
        PlantedCase(
            "1: diagnosis-based DENY, diagnosis covered",
            1,
            _variant(
                decision="DENY",
                statuses=["NOT_MET"],
                scenario_type=DX_SCENARIO,
                reasons=[NOT_NECESSARY],
            ),
            True,
        ),
        PlantedCase(
            "2: APPROVE line with a NOT_MET criterion",
            2,
            _variant(statuses=["MET", "NOT_MET"]),
            True,
        ),
        PlantedCase("2: PEND line, all criteria MET, no flag", 2, _variant(decision="PEND"), True),
        PlantedCase(
            "2: NCCI_BYPASS PEND line, all criteria MET",
            2,
            _variant(decision="PEND", rule_flags=[NCCI_BYPASS]),
            False,
        ),
        PlantedCase(
            "3: MET evidence not in the notes",
            3,
            _variant(evidence="MRI shows a large disc herniation."),
            True,
        ),
        PlantedCase(
            "4: criterion that was not retrieved",
            4,
            _variant(extra=[_not_applicable("POL-OTHER-009.c1")]),
            True,
        ),
        PlantedCase(
            "5: NOT_APPLICABLE with no related sentence",
            5,
            _variant(extra=[_not_applicable("POL-PLANT-001.c3")]),
            True,
        ),
        PlantedCase(
            "5: NOT_APPLICABLE cleared by a structural cue",
            5,
            _variant(extra=[_not_applicable("POL-PLANT-001.c4")]),
            False,
        ),
        PlantedCase(
            "5: NOT_APPLICABLE with a related note sentence",
            5,
            _variant(extra=[_not_applicable("POL-PLANT-001.c5")]),
            False,
        ),
    ]


def run_planted(case: PlantedCase) -> bool:
    """True when the case's check flags its record."""
    lookups = planted_lookups()
    record = case.record
    if case.check == 1:
        flags = check_mcd(record, lookups)[0]
    elif case.check == 2:
        flags = check_decision_rule(record)[0]
    elif case.check == 3:
        flags = check_evidence(record)[0]
    elif case.check == 4:
        flags = check_criterion_ids(record)
    else:
        flags = check_not_applicable(record, lookups, WordOverlap(), PLANTED_THRESHOLD)[0]
    return bool(flags)


def self_test_line(real_results: Sequence[tuple[str, bool]] = ()) -> tuple[str, bool]:
    """The review file's "Checker self-test" line, and whether every case behaved."""
    results = [(case, run_planted(case) == case.expect_flag) for case in planted_cases()]
    caught = [c.name for c, ok in results if ok and c.expect_flag]
    left_alone = [c.name for c, ok in results if ok and not c.expect_flag]
    failed = [c.name for c, ok in results if not ok] + [n for n, ok in real_results if not ok]
    total = len(results) + len(real_results)
    passed = total - len(failed)
    text = (
        f"Checker self-test: {passed}/{total} planted cases behaved as expected. "
        f"Caught ({len(caught)}): {'; '.join(caught)}. "
        f"Correctly not flagged ({len(left_alone)}): {'; '.join(left_alone)}."
    )
    if real_results:
        text += (
            " On the real MCD lookups: "
            + "; ".join(f"{name} ({'ok' if ok else 'FAILED'})" for name, ok in real_results)
            + "."
        )
    if failed:
        text += f" FAILED: {'; '.join(failed)}."
    return text, not failed


# --- review file ----------------------------------------------------------------------------


def _order(flag: Flag) -> tuple[Any, ...]:
    split = SPLITS.index(flag.split) if flag.split in SPLITS else len(SPLITS)
    return split, flag.record_id, flag.line_no, flag.criterion_id


def review_sample(flags: Sequence[Flag], seed: int = SEED) -> list[Flag]:
    """At most 3 random flags per check; check 5 also gets its 2 lowest-similarity flags."""
    rng = random.Random(seed)
    rows: list[Flag] = []
    for check in CHECK_NAMES:
        pool = sorted((f for f in flags if f.check == check), key=_order)
        picked = rng.sample(pool, min(RANDOM_ROWS, len(pool)))
        if check == 5:
            rest = sorted(
                (f for f in pool if f not in picked),
                key=lambda f: (f.score if f.score is not None else math.inf, _order(f)),
            )
            picked += rest[:LOWEST_ROWS]
        rows += picked
    return rows


def redact_hcpc_row(row: str) -> str:
    """A raw article_x_hcpc_code.csv row with the AMA CPT descriptor columns replaced."""
    fields = next(csv.reader(io.StringIO(row)))
    for column in HCPC_DESCRIPTOR_COLUMNS:
        if column < len(fields):
            fields[column] = DESCRIPTOR_OMITTED
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(fields)
    return out.getvalue()


@cache
def _mcd_file_lines(name: str) -> tuple[str, ...]:
    from app.db.raw import MCD_ARTICLES_ZIP

    with zipfile.ZipFile(MCD_ARTICLES_ZIP) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read("current_article_csv.zip")))
    return tuple(inner.read(name).decode("latin-1").splitlines())


def mcd_source_rows(article: str, version: str, code: str, diagnoses: Sequence[str]) -> str:
    """The raw MCD rows for the procedure and the diagnoses, as they appear in the source file
    (procedure descriptor columns omitted)."""
    prefix = f"{article.removeprefix('A')},{version},"
    wanted_dx = {format_icd10(dx) for dx in diagnoses}
    parts = []
    for name, wanted, redact in (
        ("article_x_hcpc_code.csv", {code}, True),
        ("article_x_icd10_covered.csv", wanted_dx, False),
        ("article_x_icd10_noncovered.csv", wanted_dx, False),
    ):
        lines = _mcd_file_lines(name)
        rows = [
            redact_hcpc_row(line) if redact else line
            for line in lines[1:]
            if line.startswith(prefix) and next(csv.reader([line]))[2] in wanted
        ]
        shown = " / ".join(f"`{row}`" for row in rows) or (
            f"no row for {', '.join(sorted(wanted))} in {article} v{version}"
        )
        parts.append(f"{name} (`{lines[0]}`): {shown}")
    return "Raw MCD rows: " + " || ".join(parts)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def review_markdown(summary: Mapping[str, Any], rows: Sequence[Flag]) -> str:
    minutes = MINUTES_PER_ROW * len(rows)
    lines = [
        "# Label verification (Task V1a): review sheet",
        "",
        INSTRUCTION,
        "",
        f"- Records checked: {summary['records']}; {summary['lines']} decided lines",
        "- Flags per check:",
        *[f"  - {count}" for count in summary["counts"]],
        *[f"- {method}" for method in summary["methods"]],
        f"- {summary['self_test']}",
        f"- Estimated review time: {minutes} minutes ({MINUTES_PER_ROW} minutes per row)",
        "",
        "| # | Check | Record ID | What was flagged | Evidence (side by side) "
        "| Where to look it up | Your verdict | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for number, row in enumerate(rows, start=1):
        evidence = f"{row.left}<br>⟷<br>{row.right}"
        if row.source_rows:
            evidence += f"<br>{row.source_rows}"
        lines.append(
            f"| {number} | {CHECK_NAMES[row.check]} | {row.record_id} (line {row.line_no}) | "
            f"{_cell(row.what)} | {_cell(evidence)} | {_cell(row.look_up)} |  |  |"
        )
    return "\n".join(lines) + "\n"


# --- the run --------------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_records(split: str, dataset_dir: Path = DATASET_DIR) -> list[Record]:
    inputs = {i["record_id"]: i for i in _read_jsonl(dataset_dir / f"{split}_inputs.jsonl")}
    return [
        Record.from_dataset(split, r, inputs[r["metadata"]["record_id"]])
        for r in _read_jsonl(dataset_dir / f"{split}.jsonl")
    ]


def load_lookups() -> Lookups:
    from app.db import raw
    from app.db.curated import load_curated

    curated = load_curated()
    support = {
        code: Support(article=s.billing_article, alternatives=s.alternatives)
        for code, s in curated.diagnosis_support.items()
    }
    articles = raw.read_article_diagnoses({s.article for s in support.values()})
    policies = list(curated.policies.values())
    return Lookups(
        support=support,
        covered={a: dict(d.covered) for a, d in articles.items()},
        versions={a: d.version for a, d in articles.items()},
        descriptions=dict(curated.descriptions),
        icd10=raw.read_icd10_codes(),
        policy_codes={p.policy_id: tuple(p.procedure_codes) for p in policies},
        criterion_text={c.criterion_id: c.text for p in policies for c in p.criteria},
        criterion_policy={c.criterion_id: p.policy_id for p in policies for c in p.criteria},
    )


def real_mcd_self_test(records: Sequence[Record], lookups: Lookups) -> list[tuple[str, bool]]:
    """Plant into a copy of a real record: a code in no covered group must be flagged through the
    real reader, and a code from the required group must not (guards against a reader that
    silently covers everything, which would make check 1 report nothing)."""
    for record in records:
        for line in record.lines:
            rule = lookups.support.get(record.procedure(line["line_no"]))
            if line["decision"] != "APPROVE" or rule is None or len(rule.alternatives[0]) != 1:
                continue
            group = lookups.covered.get(rule.article, {}).get(rule.alternatives[0][0])
            if not group:
                continue
            pointers = record.service_line(line["line_no"])["diagnosis_pointers"]
            results = []
            for name, code, expect in (
                ("a code in no covered group is flagged", "XX999", True),  # not an ICD-10 code
                ("a code from the required group is not flagged", sorted(group)[0], False),
            ):
                claim = copy.deepcopy(record.claim)
                for pointer in pointers:  # every pointed diagnosis, so none can rescue the line
                    claim["diagnoses"][ord(pointer) - ord("A")] = code
                planted = replace(record, claim=claim, target={"lines": [line]})
                flagged = bool(check_mcd(planted, lookups)[0])
                results.append((f"{name} ({record.record_id}, {rule.article})", flagged == expect))
            return results
    return [("no APPROVE line with a single-group rule to plant into", False)]


def _met_pairs(records: Sequence[Record], lookups: Lookups) -> list[tuple[str, str]]:
    pairs = []
    for record in records:
        for line in record.lines:
            retrieved = {c["criterion_id"]: c for c in record.retrieved(line["line_no"])}
            for criterion in line["criteria"]:
                if criterion["status"] != "MET":
                    continue
                text = retrieved.get(criterion["criterion_id"], {}).get("text") or (
                    lookups.criterion_text.get(criterion["criterion_id"], "")
                )
                pairs.append((text, criterion["evidence"]))
    return pairs


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    from app.core.settings import get_settings
    from app.rag.embedding import FastEmbedder

    lookups = load_lookups()
    by_split = {split: load_records(split) for split in SPLITS}
    records = [r for split in SPLITS for r in by_split[split]]
    lines_total = sum(len(r.lines) for r in records)
    print(f"{len(records)} records, {lines_total} decided lines", flush=True)

    flags: list[Flag] = []
    stats: Counter[str] = Counter()
    for record in records:
        mcd_flags, not_checkable = check_mcd(record, lookups)
        rule_flags, exempt = check_decision_rule(record)
        evidence_flags, met = check_evidence(record)
        id_flags = check_criterion_ids(record)
        flags += mcd_flags + rule_flags + evidence_flags + id_flags
        stats["not_checkable"] += not_checkable
        stats["exempt"] += exempt
        stats["met"] += met
        stats["criteria"] += sum(len(line["criteria"]) for line in record.lines)
    print("checks 1-4 done; embedding for check 5", flush=True)

    settings = get_settings()
    similarity = EmbeddingSimilarity(
        FastEmbedder(settings.embedding_model, settings.embedding_cache_dir)
    )
    pairs = _met_pairs(records, lookups)
    similarity.prepare(
        [text for pair in pairs for text in pair]
        + [s for r in records for s in note_sentences(r.notes)]
        + [c["text"] for r in records for line in r.context["lines"] for c in line["criteria"]]
        + list(lookups.descriptions.values())
        + [lookups.icd10[dx] for r in records for dx in r.claim["diagnoses"] if dx in lookups.icd10]
    )
    threshold = calibrate(pairs, similarity)
    cues: list[dict[str, Any]] = []
    for record in records:
        na_flags, na_cues = check_not_applicable(record, lookups, similarity, threshold)
        flags += na_flags
        cues += na_cues
    print(f"check 5 done: threshold {threshold:.4f}", flush=True)

    self_test, self_test_ok = self_test_line(real_mcd_self_test(records, lookups))
    per_check = Counter(f.check for f in flags)
    kinds = Counter((f.check, f.kind) for f in flags)
    sources = Counter(c["source"] for c in cues if c["result"] != "no cue found")
    split_sizes = ", ".join(f"{s} {len(by_split[s]):,}" for s in SPLITS)
    summary = {
        "records": f"{len(records):,} ({split_sizes})",
        "lines": f"{lines_total:,}",
        "counts": [
            f"{CHECK_NAMES[1]}: {per_check[1]} (APPROVE not covered "
            f"{kinds[(1, 'APPROVE not covered')]}, PEND not covered "
            f"{kinds[(1, 'PEND not covered')]}, diagnosis-based DENY covered "
            f"{kinds[(1, 'diagnosis-based DENY covered')]}) on "
            f"{lines_total - stats['not_checkable']:,} checkable lines; not checkable: "
            f"{stats['not_checkable']:,} lines (procedure has no billing article: office visits)",
            f"{CHECK_NAMES[2]}: {per_check[2]}; exempt: {stats['exempt']} NCCI-bypass PEND lines "
            "(flag NCCI_BYPASS, labelled PEND, no NOT_MET or NOT_DOCUMENTED criterion)",
            f"{CHECK_NAMES[3]}: {per_check[3]} of {stats['met']:,} MET criteria",
            f"{CHECK_NAMES[4]}: {per_check[4]} of {stats['criteria']:,} labelled criteria",
            f'{CHECK_NAMES[5]} ({TRIAGE_NOTE}): {per_check[5]} "no cue found" of {len(cues):,} '
            f"NOT_APPLICABLE criteria; cleared by a structural cue {sources['structural']}, "
            f"by a note sentence {sources['notes']}, by the procedure description "
            f"{sources['procedure description']}, by a diagnosis description "
            f"{sources['diagnosis description']}",
        ],
        "methods": [
            "Check 1 diagnoses: all of the line's pointed diagnoses (every pointer, not only the "
            "first). A line is covered when, for at least one of the procedure's group "
            "combinations, each group in it contains at least one of those diagnoses (for "
            "example colonoscopy: group 1, or group 2 and group 3). Combinations come from "
            "data/curated diagnosis support, which cites the article and groups; covered codes "
            "come from the current article version in data/raw/mcd.",
            "Check 1 uses app/db/raw.read_article_diagnoses, the same reader the generator uses "
            "(training/generate/codebook.py), so it is not an independent check of that reader.",
            "Check 1 DENY side: only lines the record marks as diagnosis-based (scenario_type "
            "deny_dx, reason DN_NOT_MEDICALLY_NECESSARY) are checked; criterion-based denials "
            "use the same reason code and are check 2's territory. A diagnosis-based denial in "
            "another scenario type would be missed.",
            f"Check 5 threshold: {threshold:.4f}, the 5th percentile (nearest rank) of the "
            f"similarity between each MET criterion and its own evidence sentence (n = "
            f"{len(pairs):,}); {settings.embedding_model} cosine, both texts embedded as "
            "passages. A structural cue is tried first: the criterion names a procedure code "
            "that is not the line's, or its subject names a word unique to another code's "
            "description in the same policy and none unique to the line's own; a subject that "
            "begins with the patient names no procedure. Every cue decision is in "
            "A_labels_check5_cues.csv.",
            f"Raw MCD procedure rows show {DESCRIPTOR_OMITTED} in the two descriptor columns "
            "(CLAUDE.md: never copy AMA CPT descriptor text).",
        ],
        "self_test": self_test,
    }

    rows = [
        replace(row, source_rows=mcd_source_rows(*row.mcd)) if row.mcd else row
        for row in review_sample(flags)
    ]
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "A_labels_full.csv",
        [
            {
                "check": CHECK_NAMES[f.check],
                "kind": f.kind,
                "split": f.split,
                "record_id": f.record_id,
                "line_no": f.line_no,
                "criterion_id": f.criterion_id,
                "what": f.what,
                "evidence_left": f.left,
                "evidence_right": f.right,
                "look_up": f.look_up,
                "score": "" if f.score is None else f.score,
            }
            for f in sorted(flags, key=lambda f: (f.check, *_order(f)))
        ],
        [
            "check",
            "kind",
            "split",
            "record_id",
            "line_no",
            "criterion_id",
            "what",
            "evidence_left",
            "evidence_right",
            "look_up",
            "score",
        ],
    )
    _write_csv(
        out / "A_labels_check5_cues.csv",
        cues,
        [
            "split",
            "record_id",
            "line_no",
            "procedure_code",
            "criterion_id",
            "result",
            "source",
            "matched",
            "score",
        ],
    )
    (out / "A_labels_review.md").write_text(review_markdown(summary, rows), encoding="utf-8")
    print(json.dumps({CHECK_NAMES[c]: per_check[c] for c in CHECK_NAMES}, indent=2))
    print(self_test)
    print(f"wrote {out}")
    if not self_test_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
