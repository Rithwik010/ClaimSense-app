// The claim's clinical note with every evidence quote highlighted (DESIGN.md). Selecting a
// criterion scrolls the note to its quote and pulses the highlight once (motion moment 3); with
// reduced motion the quote is underlined without the pulse.

import { useAnimate, useReducedMotion } from "motion/react";
import { useEffect } from "react";

export interface Quote {
  key: string; // `${lineNo}:${criterionId}`
  text: string;
}

interface Segment {
  start: number;
  end: number;
  keys: string[];
}

/** Where each quote is in the note: overlapping quotes share one highlight. */
export function segments(notes: string, quotes: Quote[]): Segment[] {
  const found = quotes
    .map((q) => ({ start: q.text ? notes.indexOf(q.text) : -1, length: q.text.length, key: q.key }))
    .filter((q) => q.start >= 0)
    .sort((a, b) => a.start - b.start);
  const merged: Segment[] = [];
  for (const q of found) {
    const last = merged[merged.length - 1];
    if (last && q.start < last.end) {
      last.end = Math.max(last.end, q.start + q.length);
      last.keys.push(q.key);
    } else {
      merged.push({ start: q.start, end: q.start + q.length, keys: [q.key] });
    }
  }
  return merged;
}

export function ClinicalNote({
  notes,
  quotes,
  active,
}: {
  notes: string;
  quotes: Quote[];
  active: { key: string; n: number } | null;
}) {
  const [scope, animate] = useAnimate();
  const reduce = useReducedMotion();
  const parts = segments(notes, quotes);

  useEffect(() => {
    if (!active || !scope.current) return;
    const mark = (scope.current as HTMLElement).querySelector<HTMLElement>(
      `mark[data-keys~="${CSS.escape(active.key)}"]`,
    );
    if (!mark) return;
    mark.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    if (!reduce) {
      void animate(mark, { backgroundColor: ["#FFF2CC", "#FFD966", "#FFF2CC"] }, { duration: 0.6, delay: 0.25 });
    }
  }, [active, animate, reduce, scope]);

  if (!notes.trim()) {
    return <p className="text-ink-muted">This claim has no clinical note.</p>;
  }
  const pieces = [];
  let at = 0;
  for (const part of parts) {
    if (part.start > at) pieces.push(notes.slice(at, part.start));
    const selected = active !== null && part.keys.includes(active.key);
    pieces.push(
      <mark
        key={part.start}
        data-keys={part.keys.join(" ")}
        className={`evidence ${selected ? "underline decoration-[#2b2f38] decoration-2 underline-offset-4 ring-2 ring-primary/70" : ""}`}
      >
        {notes.slice(part.start, part.end)}
      </mark>,
    );
    at = part.end;
  }
  pieces.push(notes.slice(at));
  return (
    <div ref={scope} className="max-w-[72ch] text-[15px] leading-7 whitespace-pre-wrap" data-testid="clinical-note">
      {pieces}
    </div>
  );
}
