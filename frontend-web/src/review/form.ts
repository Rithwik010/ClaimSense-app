// The review form's rules (§8.8, D-REV-2, D-REV-4), apart from the page so they can be tested:
// a line decided by a rule cannot be changed; a changed line needs a reason; the benefit category
// is chosen only for an approved line with several candidate categories; reviewers never enter
// amounts. "Accept all" is for an unchanged form, "Submit changes" for a changed one.

import type { DecisionRecord, LineDecision, LineOverride } from "../api/types";

export interface LineState {
  lineNo: number;
  editable: boolean; // false for a line decided by a rule
  original: { decision: LineDecision; category: string | null };
  candidates: string[]; // benefit categories the plan offers for the line's code
  decision: LineDecision;
  category: string | null;
  reason: string;
}

export interface Checked {
  changed: number[];
  overrides: LineOverride[];
  errors: Record<number, string>;
}

export function initialLines(record: DecisionRecord): LineState[] {
  const context = new Map((record.context_refs?.lines ?? []).map((c) => [c.line_no, c]));
  return [...record.line_decisions]
    .sort((a, b) => a.line_no - b.line_no)
    .map((line) => ({
      lineNo: line.line_no,
      editable: line.source !== "RULE",
      original: { decision: line.decision, category: line.benefit_category },
      candidates: (context.get(line.line_no)?.candidate_benefits ?? []).map(
        (fact) => fact.benefit_category,
      ),
      decision: line.decision,
      category: line.benefit_category,
      reason: "",
    }));
}

/** Does the line need a benefit category choice? An approved line with several candidates. */
export function needsCategory(line: LineState): boolean {
  return line.decision === "APPROVE" && line.candidates.length > 1;
}

export function isChanged(line: LineState): boolean {
  if (!line.editable) return false;
  if (line.decision !== line.original.decision) return true;
  return needsCategory(line) && line.category !== line.original.category;
}

export function check(lines: LineState[]): Checked {
  const result: Checked = { changed: [], overrides: [], errors: {} };
  for (const line of lines) {
    if (!isChanged(line)) continue;
    result.changed.push(line.lineNo);
    if (!line.reason.trim()) {
      result.errors[line.lineNo] = `Give a reason for changing line ${line.lineNo}.`;
    } else if (needsCategory(line) && !line.category) {
      result.errors[line.lineNo] = `Choose a benefit category for line ${line.lineNo}.`;
    }
    const override: LineOverride = {
      line_no: line.lineNo,
      decision: line.decision,
      reason: line.reason.trim(),
    };
    if (needsCategory(line) && line.category) override.benefit_category = line.category;
    result.overrides.push(override);
  }
  return result;
}
