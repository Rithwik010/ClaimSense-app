"""The verification gate (generator v3, Phase 4; SPEC.md). Every note must pass all of it.

1. Every documented fact is present: its quote (the writer A span, or the verifier's quote found
   exactly in the note) holds the fact's values and has at least `verification.min_quote_words`
   words; a contradiction's copied statement comes before its correction.
2. No missing fact is present: no note sentence holds `verification.missing_overlap` of a missing
   fact's (or an exclusion's) content words, and the verifier found nothing for it.
3. Contradictions and borderline values appear as specified (the values are part of check 1).
4. The label recomputed from the verified facts (v2's `implied_decision`) equals the sheet's.
5. Leakage: no outcome word and no criterion or policy ID (config.yaml `leakage`).
6. The targets' quotes are exact substrings of the note; the target passes the output schema
   and the evidence guard changes nothing.
7. Near-duplicates across splits are checked over the whole dataset (`near_duplicates`).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.contracts import (
    ContextPackage,
    CriterionStatus,
    LineDecision,
    RulesOutcome,
    SLMOutput,
)
from app.ml.derive import implied_decision
from app.ml.evidence import evidence_guard
from app.ml.validate import validate_output
from training.generate.v3.config import config, leaks
from training.generate.v3.facts import PLACEHOLDER

STOPWORDS = frozenset(
    "a an the and or of to in on at for with without is are was were be been has have had this "
    "that these those it its as by from into over than then there their they he she his her "
    "patient pt no not only but also so if when which who".split()
)
SENTENCE = re.compile(r"[^.;\n]+[.;]?")
TOKEN = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*")


@dataclass
class GateResult:
    sheet_id: str
    writer: str
    failures: list[str] = field(default_factory=list)
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)
    verifier_pending: bool = False

    @property
    def passed(self) -> bool:
        return not self.failures and not self.verifier_pending


def content_words(text: str) -> set[str]:
    text = re.sub(r"\{[^}]+\}", " ", text.lower())
    return {t for t in TOKEN.findall(text) if t not in STOPWORDS and not t.isdigit()}


def locate(note: str, quote: str) -> tuple[int, int] | None:
    """The span of `quote` in the note: exact, else the same words with any whitespace between
    them (case-insensitive); None when it is not there."""
    quote = quote.strip()
    if not quote:
        return None
    start = note.find(quote)
    if start >= 0:
        return start, start + len(quote)
    words = quote.split()
    pattern = r"\s+".join(re.escape(w) for w in words)
    found = re.search(pattern, note, re.IGNORECASE)
    return (found.start(), found.end()) if found else None


def missing_matches(note: str, forbidden: Sequence[str]) -> list[str]:
    """Note sentences that hold most of a missing fact's content words."""
    threshold = config()["verification"]["missing_overlap"]
    found = []
    sentences = [m.group(0) for m in SENTENCE.finditer(note)]
    for template in forbidden:
        wanted = content_words(template)
        if len(wanted) < 3:
            continue
        for sentence in sentences:
            if len(wanted & content_words(sentence)) / len(wanted) >= threshold:
                found.append(sentence.strip())
    return found


def _stated(fact: Mapping[str, Any]) -> bool:
    return bool(fact.get("text")) and fact["status"] not in ("missing", "absent")


def check_note(
    sheet: Mapping[str, Any],
    note: str,
    known_spans: Mapping[str, tuple[int, int]] | None,
    verifier: Mapping[str, str | None] | None,
) -> GateResult:
    """Checks 1 to 5 for one note. `known_spans`: writer A's fact spans (None for a model note,
    whose spans come from the verifier's quotes); `verifier`: {fact_id: quote or None} for the
    verifier's statements (llm.statements), None while it has not run."""
    cfg = config()["verification"]
    result = GateResult(sheet_id=sheet["sheet_id"], writer=sheet["writer"])
    result.verifier_pending = verifier is None
    facts = {f["fact_id"]: f for f in sheet["facts"]}
    for fact in sheet["facts"]:
        if not _stated(fact):
            continue
        ids = [fact["fact_id"]] + (
            [f"{fact['fact_id']}:original"] if fact["status"] == "contradicted" else []
        )
        for fid in ids:
            span = None
            if known_spans is not None:
                span = known_spans.get(fid)
            elif verifier is not None and verifier.get(fid):
                span = locate(note, verifier[fid] or "")
                if span is None:
                    result.failures.append(f"{fid}: the verifier's quote is not in the note")
                    continue
            if span is None:
                if known_spans is not None or verifier is not None:
                    result.failures.append(f"{fid}: documented fact not found")
                continue
            quote = note[span[0] : span[1]]
            if not fid.endswith(":original"):
                missing = [v for v in fact.get("values") or [] if v not in quote]
                if missing:
                    result.failures.append(f"{fid}: quote lacks the values {missing}")
                if len(quote.split()) < cfg["min_quote_words"]:
                    result.failures.append(
                        f"{fid}: quote shorter than {cfg['min_quote_words']} words"
                    )
            result.spans[fid] = span
        if fact["status"] == "contradicted":
            first = result.spans.get(f"{fact['fact_id']}:original")
            last = result.spans.get(fact["fact_id"])
            if first and last and first[0] >= last[0]:
                result.failures.append(
                    f"{fact['fact_id']}: the correction comes before the copied statement"
                )
    for fact in sheet["facts"]:
        checked = fact["status"] == "missing" or (
            fact["status"] == "absent" and fact.get("role") == "exclusion"
        )
        if not checked:
            continue
        own = [note[s[0] : s[1]] for s in result.spans.values()]
        hits = [
            h
            for h in missing_matches(note, fact.get("forbidden") or [])
            if not any(h in o or o in h for o in own)
        ]
        if hits:
            result.failures.append(
                f"{fact['fact_id']}: {fact['status']} fact appears: {hits[0][:80]!r}"
            )
        if verifier is not None and verifier.get(fact["fact_id"]):
            result.failures.append(
                f"{fact['fact_id']}: the verifier found the {fact['status']} fact: "
                f"{(verifier[fact['fact_id']] or '')[:80]!r}"
            )
    leaked = leaks(note)
    if leaked:
        result.failures.append(f"leakage: {sorted(set(leaked))}")
    if not result.verifier_pending and not result.failures:
        result.failures += label_problems(sheet, result.spans, facts)
    return result


def label_problems(
    sheet: Mapping[str, Any],
    spans: Mapping[str, tuple[int, int]],
    facts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Check 4: each line's decision recomputed from the verified facts with v2's derivation."""
    target = SLMOutput.model_validate(sheet["label"]["target"])
    context = ContextPackage.model_validate(sheet["inputs"]["context"])
    groups = {
        (c.line_no, r.criterion_id): r.group is not None for c in context.lines for r in c.criteria
    }
    by_line: dict[tuple[int, str], Mapping[str, Any]] = {}
    for fact in facts.values():
        if fact.get("kind") == "criterion":
            for n in fact.get("lines") or []:
                by_line[(n, fact["criterion_id"])] = fact
    flags = {o["line_no"]: o["flags"] for o in sheet["inputs"]["rules_outcome"]["line_outcomes"]}
    bypass_missing = {
        n
        for f in facts.values()
        if f.get("kind") == "bypass" and f["status"] == "missing"
        for n in f.get("lines") or []
    }
    problems = []
    for line in target.lines:
        pairs = []
        for result in line.criteria:
            fact = by_line.get((line.line_no, result.criterion_id))
            if fact is None:
                problems.append(f"line {line.line_no}: no fact for {result.criterion_id}")
                continue
            if fact["status"] == "missing":
                status = CriterionStatus.NOT_DOCUMENTED
            elif fact["status"] == "absent":
                status = CriterionStatus.NOT_APPLICABLE
            else:
                anchor = fact.get("shares_evidence_with") or fact["fact_id"]
                if anchor not in spans:
                    problems.append(f"line {line.line_no}: {result.criterion_id} not verified")
                    continue
                status = CriterionStatus(fact["label_status"])
            pairs.append((status, groups.get((line.line_no, result.criterion_id), False)))
        decision, _ = implied_decision(pairs)
        if (
            decision is LineDecision.APPROVE
            and line.line_no in bypass_missing
            and "NCCI_BYPASS" in flags.get(line.line_no, [])
        ):
            decision = LineDecision.PEND
        if decision is not line.decision:
            problems.append(
                f"line {line.line_no}: recomputed {decision.value} != label {line.decision.value}"
            )
    return problems


def filled_target(
    sheet: Mapping[str, Any], note: str, spans: Mapping[str, tuple[int, int]]
) -> tuple[SLMOutput | None, list[str]]:
    """Check 6: the target with each placeholder replaced by its exact quote."""
    text = _json(sheet["label"]["target"])
    for fid, (start, end) in spans.items():
        if ":" in fid:
            continue
        quote = note[start:end]
        text = text.replace(_json_string(PLACEHOLDER.format(fid)), _json_string(quote))
    if "⟦" in text:
        return None, ["a placeholder has no quote"]
    rules = RulesOutcome.model_validate(sheet["inputs"]["rules_outcome"])
    context = ContextPackage.model_validate(sheet["inputs"]["context"])
    result = validate_output(text, rules, context)
    if not result.valid or result.output is None:
        return None, [f"target invalid: {e}" for e in result.errors]
    guarded, notes = evidence_guard(result, note)
    if notes:
        return None, [f"evidence guard: {n}" for n in notes]
    for line in guarded.output.lines:  # type: ignore[union-attr]
        for criterion in line.criteria:
            if criterion.status in (CriterionStatus.MET, CriterionStatus.NOT_MET):
                if criterion.evidence not in note:
                    return None, [f"{criterion.criterion_id}: quote not in the note"]
    return guarded.output, []


def _json(value: Any) -> str:  # noqa: ANN401
    import json

    return json.dumps(value, ensure_ascii=False)


def _json_string(text: str) -> str:
    return _json(text)


def shingles(text: str, size: int = 5) -> set[str]:
    words = TOKEN.findall(text.lower())
    return {" ".join(words[i : i + size]) for i in range(max(0, len(words) - size + 1))}


def near_duplicates(notes: Mapping[str, Mapping[str, str]]) -> list[tuple[str, str, float]]:
    """Check 7: (note id, note id, Jaccard) for notes in different splits whose 5-word shingles
    overlap at `verification.near_duplicate_jaccard` or more. `notes`: split -> id -> text."""
    threshold = config()["verification"]["near_duplicate_jaccard"]
    sets = [
        (split, nid, shingles(text))
        for split, items in notes.items()
        for nid, text in items.items()
    ]
    index: dict[str, list[int]] = {}
    for i, (_, _, grams) in enumerate(sets):
        for gram in grams:
            index.setdefault(gram, []).append(i)
    found = []
    for i, (split, nid, grams) in enumerate(sets):
        counts: dict[int, int] = {}
        for gram in grams:
            for j in index[gram]:
                if j > i and sets[j][0] != split:
                    counts[j] = counts.get(j, 0) + 1
        for j, shared in counts.items():
            union = len(grams) + len(sets[j][2]) - shared
            if union and shared / union >= threshold:
                found.append((nid, sets[j][1], round(shared / union, 3)))
    return found
