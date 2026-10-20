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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
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
from training.generate.v3.config import config, leaks, phrases
from training.generate.v3.facts import PLACEHOLDER

STOPWORDS = frozenset(
    "a an the and or of to in on at for with without is are was were be been has have had this "
    "that these those it its as by from into over than then there their they he she his her "
    "patient pt no not only but also so if when which who".split()
)
SENTENCE = re.compile(r"[^.;\n]+[.;]?")
TOKEN = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*")
NUMBER_WORDS = dict(  # a whole-number value may be spelled out; "one" is left out ("one on one")
    zip(
        [str(n) for n in range(2, 21)] + ["30", "40", "50", "60", "90"],
        "two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty ninety".split(),
        strict=True,
    )
)
Span = tuple[int, int]


@cache
def _short_forms() -> tuple[tuple[re.Pattern[str], str], ...]:
    """The writers' short forms (phrases/abbreviations.yaml) with their long forms. A short form
    with a capital (PT, R) matches as written and comes first, so "PT" is physical therapy before
    "pt" (any case) is patient; symbols (+, &, ~) are left alone."""
    found = []
    for long, short in phrases("abbreviations")["pairs"]:
        if not re.search(r"[A-Za-z]", short) or (len(short) < 2 and not short.isupper()):
            continue
        flags = 0 if short != short.lower() else re.IGNORECASE
        found.append((re.compile(rf"(?<![\w/]){re.escape(short)}(?![\w/])", flags), long))
    found.sort(key=lambda pair: (bool(pair[0].flags & re.IGNORECASE), -len(pair[0].pattern)))
    return tuple(found)


def expand(text: str) -> str:
    """The text with each short form written out, for comparing words (never for quoting)."""
    for pattern, long in _short_forms():
        text = pattern.sub(long, text)
    return text


def words(text: str) -> set[str]:
    """The words two wordings are compared by: short forms written out, hyphenated and slashed
    words split, no stopwords or bare numbers, and a plural "s" dropped ("blood-sugar mgmt" and
    "blood sugar management" share blood and sugar)."""
    text = re.sub(r"\{[^}]+\}", " ", expand(text).lower())
    found = set()
    for token in re.findall(r"[a-z0-9]+", text):
        if token in STOPWORDS or token.isdigit():
            continue
        found.add(token[:-1] if len(token) > 3 and token[-1] == "s" and token[-2] != "s" else token)
    return found


def has_value(text: str, value: str) -> bool:
    """Whether a passage holds a fact's value: as written, or a whole number spelled out."""
    if value in text:
        return True
    word = NUMBER_WORDS.get(value)
    return word is not None and re.search(rf"\b{word}\b", text, re.IGNORECASE) is not None


def sentences(note: str) -> list[Span]:
    """The note's sentences, as spans without the surrounding whitespace."""
    found = []
    for match in SENTENCE.finditer(note):
        text = match.group(0)
        if text.strip():
            start = match.start() + len(text) - len(text.lstrip())
            found.append((start, match.start() + len(text.rstrip())))
    return found


def sentence_windows(note: str, spans: Sequence[Span], size: int) -> list[Span]:
    """`size` adjacent sentences on the same line, as one span: a fact a writer split in two, or
    cut into pieces with semicolons."""
    return [
        (spans[i][0], spans[i + size - 1][1])
        for i in range(len(spans) - size + 1)
        if all(
            "\n" not in note[a[1] : b[0]]
            for a, b in zip(spans[i : i + size - 1], spans[i + 1 : i + size], strict=True)
        )
    ]


@dataclass
class GateResult:
    sheet_id: str
    writer: str
    failures: list[str] = field(default_factory=list)
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)
    verifier_pending: bool = False
    local_spans: list[str] = field(default_factory=list)  # found by `stated_locally`

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


def closest_sentence(note: str, quote: str) -> Span | None:
    """The note passage the verifier paraphrased: the sentence (or two adjacent sentences on one
    line) whose words, numbers included, overlap the quote's most, when the overlap (Jaccard) is
    `verification.fuzzy_quote_overlap` or more. The evidence is then that passage, copied exactly
    from the note."""
    wanted = set(TOKEN.findall(quote.lower()))
    if not wanted:
        return None
    single = sentences(note)
    best, best_score = None, 0.0
    for span in single + sentence_windows(note, single, 2):
        words = set(TOKEN.findall(note[span[0] : span[1]].lower()))
        score = len(wanted & words) / len(wanted | words) if words else 0.0
        if score > best_score:
            best, best_score = span, score
    if best is None or best_score < config()["verification"]["fuzzy_quote_overlap"]:
        return None
    return best


NEGATIVE = re.compile(r"\b(no|not|without|never|none|negative|absent|neither|nor|cannot)\b|n't\b")


HEDGED = re.compile(
    r"\b(may|might|maybe|possibl[ey]|perhaps|unclear|uncertain|unsure|not sure|cannot say|"
    r"unknown|questionabl[ey]|suspected)\b"
)


def _negative(text: str) -> bool:
    return bool(NEGATIVE.search(expand(text).lower()))


def _hedged(text: str) -> bool:
    return bool(HEDGED.search(text.lower()))


def share(wording: str, passage: str, drop: frozenset[str] = frozenset()) -> float:
    """The share of a wording's content words (short forms written out, `drop` left out) that a
    passage holds; 0 when the wording has none left."""
    wanted = words(wording) - drop
    if not wanted:
        return 0.0
    return len(wanted & words(passage)) / len(wanted)


def stated_locally(note: str, fact: Mapping[str, Any], original: bool = False) -> Span | None:
    """A documented fact (`original`: a contradiction's copied statement) found in the note itself,
    when the verifier missed it or quoted a passage that does not state it: one of its wordings word
    for word; else the sentence, or the fewest adjacent sentences on one line (up to three), with
    `verification.local_fact_overlap` of its content words (short forms read as their long forms),
    every value (a whole number may be spelled out) and the same polarity (a negative in both or in
    neither). A contradicted fact and its copied statement only word for word: the opposite
    statement is in the note as well."""
    texts = list((fact.get("original" if original else "text") or {}).values())
    for text in texts:
        span = locate(note, text)
        if span:
            return span
    if fact["status"] == "contradicted":
        return None
    threshold = config()["verification"]["local_fact_overlap"]
    values = fact.get("values") or []
    single = sentences(note)
    for spans in (single, *(sentence_windows(note, single, n) for n in (2, 3))):
        best, best_share = None, 0.0
        for text in texts:
            if len(words(text)) < 3:
                continue
            negative = _negative(text)
            for span in spans:
                passage = note[span[0] : span[1]]
                if _negative(passage) != negative:
                    continue
                if not all(has_value(passage, v) for v in values):
                    continue
                found = share(text, passage)
                if found > best_share:
                    best, best_share = span, found
        if best is not None and best_share >= threshold:
            return best
    return None


def _about(note: str, span: Span, fact: Mapping[str, Any], original: bool) -> bool:
    """Whether a passage is about a documented fact: it holds `verification.quote_overlap` of one
    wording's content words (a verifier sometimes gives one fact's quote to the next)."""
    passage = note[span[0] : span[1]]
    texts = (fact.get("original" if original else "text") or {}).values()
    threshold = config()["verification"]["quote_overlap"]
    return any(share(text, passage) >= threshold for text in texts)


def _states(note: str, span: Span, fact: Mapping[str, Any], original: bool) -> bool:
    """Whether the passage the verifier quoted for a documented fact states it: about the fact,
    with every value."""
    passage = note[span[0] : span[1]]
    if not original and not all(has_value(passage, v) for v in fact.get("values") or []):
        return False
    return _about(note, span, fact, original)


def _find(note: str, quote: str) -> Span | None:
    return locate(note, quote) or closest_sentence(note, quote)


def _overlaps(a: Span, b: Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def claim_words(sheet: Mapping[str, Any]) -> frozenset[str]:
    """The content words of the claim's own procedure and diagnosis descriptions, which a note
    names anyway: they never make a sentence state a missing fact."""
    text = " ".join(
        [
            *(sheet.get("procedures") or []),
            *(d["description"] for d in sheet.get("diagnoses") or []),
        ]
    )
    return frozenset(words(text))


def missing_matches(
    note: str,
    forbidden: Sequence[str],
    claim: frozenset[str] = frozenset(),
    own: Iterable[Span] = (),
) -> list[str]:
    """Note sentences that state a missing fact: they hold `verification.missing_overlap` of one of
    its wordings' content words, and as much of the words that are not the claim's own procedure
    or diagnosis wording. A wording made only of those words is skipped; sentences in `own` (the
    fact's own hedged or negative mention) are left out."""
    threshold = config()["verification"]["missing_overlap"]
    own = list(own)
    found = []
    spans = [s for s in sentences(note) if not any(_overlaps(s, o) for o in own)]
    for template in forbidden:
        if len(words(template)) < 3 or not words(template) - claim:
            continue
        for start, end in spans:
            sentence = note[start:end]
            if share(template, sentence) >= threshold and share(template, sentence, claim) >= (
                threshold
            ):
                found.append(sentence)
    return found


def own_mentions(note: str, fact: Mapping[str, Any]) -> list[Span]:
    """A missing or absent fact's own hedged or negative mention in the note: its wording, else
    the sentence with `verification.local_fact_overlap` of its content words and the same
    polarity."""
    threshold = config()["verification"]["local_fact_overlap"]
    found = []
    for key in ("hedge", "negated"):
        for text in (fact.get(key) or {}).values():
            span = locate(note, text)
            if span is None and len(words(text)) >= 3:
                scored = [
                    (share(text, note[s[0] : s[1]]), s)
                    for s in sentences(note)
                    if _negative(note[s[0] : s[1]]) == _negative(text)
                ]
                best = max(scored, default=(0.0, None))
                span = best[1] if best[0] >= threshold else None
            if span is not None:
                found.append(span)
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
            original = fid.endswith(":original")
            span = None
            if known_spans is not None:
                span = known_spans.get(fid)
            elif verifier is not None:
                quoted = verifier.get(fid)
                span = _find(note, quoted) if quoted else None
                if span is None or not _states(note, span, fact, original):
                    # missed, a quote too far from any sentence, or one that states another fact
                    local = stated_locally(note, fact, original)
                    if local is not None:
                        span = local
                        result.local_spans.append(fid)
                    elif quoted and span is None:
                        result.failures.append(f"{fid}: the verifier's quote is not in the note")
                        continue
            if span is None:
                if known_spans is not None or verifier is not None:
                    result.failures.append(f"{fid}: documented fact not found")
                continue
            quote = note[span[0] : span[1]]
            if not original:
                missing = [v for v in fact.get("values") or [] if not has_value(quote, v)]
                if missing:
                    result.failures.append(f"{fid}: quote lacks the values {missing}")
                if len(quote.split()) < cfg["min_quote_words"]:
                    result.failures.append(
                        f"{fid}: quote shorter than {cfg['min_quote_words']} words"
                    )
            if known_spans is None and not _about(note, span, fact, original):
                result.failures.append(f"{fid}: the quote does not state the fact")
            result.spans[fid] = span
        if fact["status"] == "contradicted":
            first = result.spans.get(f"{fact['fact_id']}:original")
            last = result.spans.get(fact["fact_id"])
            if first and last and first[0] >= last[0]:
                result.failures.append(
                    f"{fact['fact_id']}: the correction comes before the copied statement"
                )
    claim = claim_words(sheet)
    for fact in sheet["facts"]:
        checked = fact["status"] == "missing" or (
            fact["status"] == "absent" and fact.get("role") == "exclusion"
        )
        if not checked:
            continue
        own = [note[s[0] : s[1]] for s in result.spans.values()]
        mentions = own_mentions(note, fact)
        hits = [
            h
            for h in missing_matches(note, fact.get("forbidden") or [], claim, mentions)
            if not any(h in o or o in h for o in own)
        ]
        if hits:
            result.failures.append(
                f"{fact['fact_id']}: {fact['status']} fact appears: {hits[0][:80]!r}"
            )
        quote = verifier.get(fact["fact_id"]) if verifier is not None else None
        if quote and _a_finding(note, quote, fact, result.spans, claim, mentions):
            result.failures.append(
                f"{fact['fact_id']}: the verifier found the {fact['status']} fact: {quote[:80]!r}"
            )
    leaked = leaks(note)
    if leaked:
        result.failures.append(f"leakage: {sorted(set(leaked))}")
    if not result.verifier_pending and not result.failures:
        result.failures += label_problems(sheet, result.spans, facts)
    return result


def _a_finding(
    note: str,
    quote: str,
    fact: Mapping[str, Any],
    spans: Mapping[str, Span],
    claim: frozenset[str] = frozenset(),
    mentions: Sequence[Span] = (),
) -> bool:
    """Whether the verifier's quote for a missing or absent fact counts. Not when it cites nothing
    in the note, a passage that states another, documented fact, or the fact's own hedged or
    negative mention (the verifier is told these say it is uncertain or absent, and still cites
    them). Otherwise it counts when the passage is about the fact: it holds
    `verification.finding_overlap` of one wording's content words, both of all of them and of
    those that are not the claim's own procedure or diagnosis wording, with the wording's polarity
    and, when hedged, a hedged wording (the topic of a missing fact, "the note documents ...",
    takes either polarity). The local word-overlap check runs on every note anyway."""
    span = _find(note, quote)
    if span is None:
        return False
    if any(_overlaps(span, other) for other in [*spans.values(), *mentions]):
        return False
    cited = note[span[0] : span[1]]
    threshold = config()["verification"]["finding_overlap"]
    wordings = [(text, True) for text in fact.get("forbidden") or []]
    if fact.get("missing_text"):
        wordings.append((fact["missing_text"], False))
    for text, polar in wordings:
        if polar and _negative(cited) != _negative(text):
            continue
        if _hedged(cited) and not _hedged(text):
            continue
        if not words(text) - claim:
            continue
        if share(text, cited) >= threshold and share(text, cited, claim) >= threshold:
            return True
    return False


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
