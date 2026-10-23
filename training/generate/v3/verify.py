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
from calendar import monthrange
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
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


def _number_contexts(value: str, text: str) -> set[str]:
    """What stands right before and after each whole-number occurrence of `value` in a text: a
    capital letter or . , / before it (C5, 1.5), or . , / and a digit after it (2/5)."""
    found = set()
    for match in re.finditer(rf"(?<!\d){value}(?!\d)", text):
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end() : match.end() + 2]
        per = before == "/" and text[match.start() - 2 : match.start() - 1] in (
            "x",
            "X",
        )  # 1x/5 days
        if before.isupper() or (before and before in ".,/" and not per):
            found.add("before " + before)
        if len(after) == 2 and after[0] in ".,/" and after[1].isdigit():
            found.add("after " + after[0])
    return found


AGO = re.compile(r"\b(\d+) (day|week|month)s? ago\b")
MONTHS = (
    "January February March April May June July August September October November December".split()
)


def date_forms(day: date) -> set[str]:
    """The ways a note writes a date: 07/04/2026, 7/4/2026, 7/4/26, 2026-07-04, July 4, 2026."""
    m, d, y, name = day.month, day.day, day.year, MONTHS[day.month - 1]
    return {
        f"{m:02d}/{d:02d}/{y}",
        f"{m}/{d}/{y}",
        f"{m:02d}/{d:02d}/{y % 100:02d}",
        f"{m}/{d}/{y % 100:02d}",
        day.isoformat(),
        f"{name} {d}, {y}",
        f"{name[:3]} {d}, {y}",
    }


def _before(day: date, count: int, unit: str) -> date:
    if unit == "day":
        return day - timedelta(days=count)
    if unit == "week":
        return day - timedelta(weeks=count)
    months = day.year * 12 + day.month - 1 - count
    year, month = divmod(months, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def ago_dates(sheet: Mapping[str, Any], fact: Mapping[str, Any]) -> dict[str, set[str]]:
    """Each value a fact's wordings give as a time before the visit ("4 months ago"), with the
    dates that state it too: the fact's own timeline date (the date its writer was given), or the
    visit date less that time."""
    visit = sheet.get("visit_date")
    own = {
        date.fromisoformat(t["date"])
        for t in sheet.get("timeline") or []
        if t.get("fact_id") == fact["fact_id"]
    }
    found: dict[str, set[str]] = {}
    for text in (fact.get("text") or {}).values():
        for match in AGO.finditer(text):
            days = set(own)
            if visit:
                days.add(_before(date.fromisoformat(visit), int(match.group(1)), match.group(2)))
            found.setdefault(match.group(1), set()).update(f for d in days for f in date_forms(d))
    return found


def has_value(
    text: str,
    value: str,
    wordings: Iterable[str] = (),
    dates: Mapping[str, set[str]] | None = None,
) -> bool:
    """Whether a passage holds a fact's value. A whole number must stand as a number of its own:
    not inside a longer number, a score, a date or a decimal (4 in 44% or 4/10), or a spinal level
    (5 in C5), unless the fact's own wordings write it that way (C5-C6, 2/5 sites); it may be
    spelled out, and a time before the visit ("4 months ago") may be written as its date (`dates`,
    from `ago_dates`). Any other value (7/10, a date) as written."""
    if dates and any(form in text for form in dates.get(value, ())):
        return True
    if not value.isdigit():
        return value in text
    allowed = set().union(*(_number_contexts(value, w) for w in wordings))
    for match in re.finditer(rf"(?<!\d){value}(?!\d)", text):
        if _number_contexts(value, text[max(0, match.start() - 2) : match.end() + 2]) <= allowed:
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
    looks: list[str] = field(default_factory=list)  # leak findings awaiting the second look

    @property
    def pending(self) -> bool:
        """Waiting for the verifier, or for its second look at a leak finding."""
        return not self.failures and (self.verifier_pending or bool(self.looks))

    @property
    def passed(self) -> bool:
        return not self.failures and not self.verifier_pending and not self.looks


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


def stated_locally(
    note: str,
    fact: Mapping[str, Any],
    original: bool = False,
    dates: Mapping[str, set[str]] | None = None,
) -> Span | None:
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
                if not all(has_value(passage, v, texts, dates) for v in values):
                    continue
                found = share(text, passage)
                if found > best_share:
                    best, best_share = span, found
        if best is not None and best_share >= threshold:
            return best
    return None


def _about(
    note: str,
    span: Span,
    fact: Mapping[str, Any],
    original: bool,
    rivals: Sequence[str] = (),
    dates: Mapping[str, set[str]] | None = None,
) -> bool:
    """Whether a passage is about a documented fact: it holds `verification.quote_overlap` of one
    wording's content words, and it is not another fact's statement (a verifier sometimes gives
    one fact's quote to the next): no wording of the note's other stated facts (`rivals`) has
    `verification.rival_overlap` of its words in it and fits it by `verification.rival_margin`
    more. A passage with all of a fact's values, two or more, is about it as well ("Pain 8/10, NDI
    57%")."""
    passage = note[span[0] : span[1]]
    texts = (fact.get("original" if original else "text") or {}).values()
    cfg = config()["verification"]
    own = max((share(text, passage) for text in texts), default=0.0)
    values = [] if original else fact.get("values") or []
    valued = len(values) >= 2 and all(has_value(passage, v, texts, dates) for v in values)
    if own < cfg["quote_overlap"] and not valued:
        return False
    rival = max((share(text, passage) for text in rivals), default=0.0)
    return not (rival >= cfg["rival_overlap"] and rival >= own + cfg["rival_margin"])


def _states(
    note: str,
    span: Span,
    fact: Mapping[str, Any],
    original: bool,
    rivals: Sequence[str] = (),
    dates: Mapping[str, set[str]] | None = None,
) -> bool:
    """Whether the passage the verifier quoted for a documented fact states it: about the fact,
    with every value."""
    passage = note[span[0] : span[1]]
    texts = list((fact.get("text") or {}).values())
    if not original and not all(
        has_value(passage, v, texts, dates) for v in fact.get("values") or []
    ):
        return False
    return _about(note, span, fact, original, rivals, dates)


def _find(note: str, quote: str) -> Span | None:
    return locate(note, quote) or closest_sentence(note, quote)


def _overlaps(a: Span, b: Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def claim_words(sheet: Mapping[str, Any]) -> frozenset[str]:
    """The content words of the claim's own procedure descriptions, which a note names anyway (the
    plan): naming what is requested never documents why. Diagnoses are not left out: a diagnosis
    can document a condition a criterion asks for."""
    return frozenset(words(" ".join(sheet.get("procedures") or [])))


def missing_matches(
    note: str,
    forbidden: Sequence[str],
    claim: frozenset[str] = frozenset(),
    own: Iterable[Span] = (),
) -> list[str]:
    """Note sentences that state a missing fact: they hold `verification.missing_overlap` of one of
    its wordings' content words, and as much of the words that are not the claim's own procedure
    wording. A wording made only of those words is skipped; sentences in `own` (the fact's own
    hedged or negative mention) are left out."""
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
    second_look: Mapping[str, str | None] | None = None,
) -> GateResult:
    """Checks 1 to 5 for one note. `known_spans`: writer A's fact spans (None for a model note,
    whose spans come from the verifier's quotes); `verifier`: {fact_id: quote or None} for the
    verifier's statements (llm.statements), None while it has not run; `second_look`:
    {fact_id: quote or None}, the second look at a missing or absent fact the verifier found
    (`result.looks` lists the findings still waiting for it): the finding stands unless the
    second look finds nothing (None); a second look citing another passage still confirms it."""
    cfg = config()["verification"]
    result = GateResult(sheet_id=sheet["sheet_id"], writer=sheet["writer"])
    result.verifier_pending = verifier is None
    facts = {f["fact_id"]: f for f in sheet["facts"]}
    statements: dict[str, list[str]] = {}  # every stated fact's wordings, by id
    for fact in sheet["facts"]:
        if _stated(fact):
            statements[fact["fact_id"]] = list(fact["text"].values())
            if fact["status"] == "contradicted":
                statements[f"{fact['fact_id']}:original"] = list(fact["original"].values())

    def rivals(fid: str) -> list[str]:
        return [text for other, texts in statements.items() if other != fid for text in texts]

    for fact in sheet["facts"]:
        if not _stated(fact):
            continue
        dates = ago_dates(sheet, fact)
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
                if span is None or not _states(note, span, fact, original, rivals(fid), dates):
                    # missed, a quote too far from any sentence, or one that states another fact
                    local = stated_locally(note, fact, original, dates)
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
                texts = list(fact["text"].values())
                missing = [
                    v for v in fact.get("values") or [] if not has_value(quote, v, texts, dates)
                ]
                if missing:
                    result.failures.append(f"{fid}: quote lacks the values {missing}")
                if len(quote.split()) < cfg["min_quote_words"]:
                    result.failures.append(
                        f"{fid}: quote shorter than {cfg['min_quote_words']} words"
                    )
            if known_spans is None and not _about(note, span, fact, original, rivals(fid), dates):
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
        fid = fact["fact_id"]
        quote = verifier.get(fid) if verifier is not None else None
        if not (quote and _a_finding(note, quote, fact, result.spans, claim, mentions)):
            continue
        if second_look is None or fid not in second_look:
            result.looks.append(fid)  # asked again, about this fact alone, before it counts
            continue
        if second_look[fid]:  # the finding stands unless the second look finds nothing
            result.failures.append(
                f"{fid}: the verifier found the {fact['status']} fact twice: {quote[:80]!r}"
            )
    leaked = leaks(note)
    if leaked:
        result.failures.append(f"leakage: {sorted(set(leaked))}")
    if not result.verifier_pending and not result.failures:
        result.failures += label_problems(sheet, result.spans, facts)
    if result.failures:
        result.looks = []  # the note is rewritten anyway
    return result


def _a_finding(
    note: str,
    quote: str,
    fact: Mapping[str, Any],
    spans: Mapping[str, Span],
    claim: frozenset[str] = frozenset(),
    mentions: Sequence[Span] = (),
) -> bool:
    """Whether the verifier's quote for a missing or absent fact counts. It does unless the passage
    it cites is not in the note; states another, documented fact; is the fact's own hedged or
    negative mention (the verifier is told these say it is uncertain or absent, and still cites
    them); is hedged while no wording of the fact is; for an exclusion, has the opposite polarity
    to every wording of it; is mostly the claim's own procedure wording (`verification.
    procedure_share` of its words: naming the requested procedure documents nothing); or shares
    less than `verification.finding_overlap` of the words of every wording and of the missing
    fact's topic (a passage about something else). The local word-overlap check runs anyway."""
    span = _find(note, quote)
    if span is None:
        return False
    if any(_overlaps(span, other) for other in [*spans.values(), *mentions]):
        return False
    cited = note[span[0] : span[1]]
    cfg = config()["verification"]
    forbidden = list(fact.get("forbidden") or [])
    texts = forbidden + ([fact["missing_text"]] if fact.get("missing_text") else [])
    if _hedged(cited) and not any(_hedged(text) for text in texts):
        return False
    if fact["status"] == "absent" and forbidden:
        if all(_negative(cited) != _negative(text) for text in forbidden):
            return False
    found = words(cited)
    if found and len(found & claim) / len(found) >= cfg["procedure_share"]:
        return False
    return any(share(text, cited) >= cfg["finding_overlap"] for text in texts)


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
