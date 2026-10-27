"""A note as segments (generator v3): text pieces tagged with their section and, for a fact's
sentence, the fact ID. Writers build segments; the noise layer changes only unprotected ones; the
rendered note gives every protected fact's exact character span, which becomes the target's quote.

Fact IDs on segments: `F3` is fact F3's own sentence (the evidence); `F3:original` the copied
statement a correction overrides; `F3:hedge` an uncertain mention; `F3:negated` an exclusion stated
in the negative.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Segment:
    text: str
    section: str | None = None
    role: str = "text"  # header | text | sep | marker
    fact_id: str | None = None
    protected: bool = False

    def with_text(self, text: str) -> "Segment":
        return replace(self, text=text)


def render(segments: Sequence[Segment]) -> tuple[str, dict[str, tuple[int, int]]]:
    """The note's text and each fact segment's span (start, end)."""
    parts: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    position = 0
    for segment in segments:
        if segment.fact_id is not None:
            spans[segment.fact_id] = (position, position + len(segment.text))
        parts.append(segment.text)
        position += len(segment.text)
    return "".join(parts), spans


def word_count(segments: Sequence[Segment]) -> int:
    return sum(len(s.text.split()) for s in segments if s.role != "sep")
