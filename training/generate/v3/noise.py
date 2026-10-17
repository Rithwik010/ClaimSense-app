"""The noise layer (generator v3, Phase 3; SPEC.md "Noise").

Typos, abbreviation swaps, section shuffling and formatting noise, at the rates in config.yaml
`noise`. Noise works on segments (training.generate.v3.segments) and never changes a protected one:
a fact's sentence, a contradiction's copied statement, a hedged or negated mention. Inside the other
segments it never touches a number, a date or a negation word (`noise.negation_words`), so no noise
can change what a note says. Section shuffling swaps two adjacent sections other than the chief
complaint and the history, so a contradiction's correction (in the assessment) still comes after
its copied statement (in the history).

Every change is counted in the returned report, for the noise statistics (Phase 5).
"""

import random
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from functools import lru_cache

from training.generate.v3.config import config, phrases
from training.generate.v3.segments import Segment

WORD = re.compile(r"[A-Za-z][A-Za-z'-]*|\S")
HAS_DIGIT = re.compile(r"\d")
FIXED_SECTIONS = ("chief_complaint", "hpi")


@lru_cache
def _negations() -> frozenset[str]:
    return frozenset(w.lower() for w in config()["noise"]["negation_words"])


@lru_cache
def _abbreviations() -> list[tuple[re.Pattern[str], str, str]]:
    """(pattern, long form, short form), longest first; pairs whose long form holds a negation
    word are left out (negation words are protected)."""
    pairs = []
    for long, short in phrases("abbreviations")["pairs"]:
        words = long.lower().split()
        if any(w in _negations() for w in words):
            continue
        pairs.append((re.compile(rf"\b{re.escape(long)}\b", re.IGNORECASE), long, short))
    return sorted(pairs, key=lambda p: -len(p[1]))


def _protected_word(word: str) -> bool:
    lowered = word.lower().strip(".,;:()")
    return bool(HAS_DIGIT.search(word)) or lowered in _negations() or lowered.endswith("n't")


def _typo(rng: random.Random, word: str) -> str:
    letters = list(word)
    i = rng.randrange(1, len(letters) - 1)
    kind = rng.choice(("swap", "drop", "double"))
    if kind == "swap":
        letters[i], letters[i + 1] = letters[i + 1], letters[i]
    elif kind == "drop":
        del letters[i]
    else:
        letters.insert(i, letters[i])
    return "".join(letters)


def _text_noise(rng: random.Random, text: str, report: Counter[str]) -> str:
    cfg = config()["noise"]
    for pattern, _long, short in _abbreviations():

        def swap(match: re.Match[str], short: str = short) -> str:
            if rng.random() >= cfg["abbreviation_swap_rate"]:
                return match.group(0)
            report["abbreviation_swaps"] += 1
            if match.group(0)[0].isupper() and short[0].islower():
                return short[0].upper() + short[1:]
            return short

        text = pattern.sub(swap, text)
    out = []
    for token in re.split(r"(\s+)", text):
        if (
            token.isalpha()
            and len(token) >= 4
            and not _protected_word(token)
            and rng.random() < cfg["typo_rate"]
        ):
            token = _typo(rng, token)
            report["typos"] += 1
        out.append(token)
    return "".join(out)


def _shuffle(rng: random.Random, segments: list[Segment], report: Counter[str]) -> list[Segment]:
    order: list[str] = []
    for s in segments:
        if s.section and s.section not in order:
            order.append(s.section)
    pairs = [
        i
        for i in range(len(order) - 1)
        if order[i] not in FIXED_SECTIONS and order[i + 1] not in FIXED_SECTIONS
    ]
    if not pairs:
        return segments
    i = rng.choice(pairs)
    order[i], order[i + 1] = order[i + 1], order[i]
    report["section_shuffles"] += 1
    return [s for name in order for s in segments if s.section == name]


def apply(
    segments: Sequence[Segment], rng: random.Random, sections: bool = True
) -> tuple[list[Segment], Counter[str]]:
    """The segments with noise. `sections`: whether the note's sections are known (writer A);
    a model-written note gets the word and whitespace noise only."""
    cfg = config()["noise"]
    fmt = cfg["formatting"]
    report: Counter[str] = Counter()
    out = list(segments)
    if sections and rng.random() < cfg["section_shuffle"]:
        out = _shuffle(rng, out, report)
    upper = sections and rng.random() < fmt["upper_case_headers"]
    together = sections and rng.random() < fmt["run_together_sections"]
    bullets = sections and rng.random() < fmt["bullets"]
    doubles = rng.random() < fmt["double_spaces"]
    trailing = rng.random() < fmt["trailing_whitespace"]
    for name, used in (
        ("upper_case_headers", upper),
        ("run_together_sections", together),
        ("bullets", bullets),
        ("double_spaces", doubles),
        ("trailing_whitespace", trailing),
    ):
        if used:
            report[name] += 1
    result = []
    for i, segment in enumerate(out):
        if segment.protected:
            result.append(segment)
            continue
        text = segment.text
        if segment.role == "header":
            text = text.upper() if upper else text
        elif segment.role == "sep":
            if together and "\n" in text:
                text = " "
            elif bullets and text == "\n" and i + 1 < len(out) and out[i + 1].role != "header":
                text = "\n- "
            if doubles and text == " " and rng.random() < 0.5:
                text = "  "
            if trailing and text.startswith("\n") and rng.random() < 0.5:
                text = " " + text
        else:
            text = _text_noise(rng, text, report)
        result.append(replace(segment, text=text))
    return result, report


def free_text_segments(text: str, spans: dict[str, tuple[int, int]]) -> list[Segment]:
    """A model-written note as segments: each found quote protected, the rest free text."""
    cuts = sorted(spans.items(), key=lambda kv: kv[1][0])
    segments, position = [], 0
    for fact_id, (start, end) in cuts:
        if start < position:
            raise ValueError(f"overlapping quotes at {fact_id}")
        if start > position:
            segments.append(Segment(text=text[position:start]))
        segments.append(Segment(text=text[start:end], fact_id=fact_id, protected=True))
        position = end
    if position < len(text):
        segments.append(Segment(text=text[position:]))
    return segments
