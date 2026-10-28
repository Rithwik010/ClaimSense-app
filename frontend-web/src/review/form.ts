// The review form's rules (§8.8, D-REV-2, D-REV-4, D-REV-9), apart from the page so they can be
// tested: a line decided by a rule cannot be changed; a line changed to Deny or Pend needs a reason
// code from the allowed list, which the provider sees; every changed line needs a note for the
// audit trail, which the provider never sees; the benefit category is chosen only for an approved
// line with several candidate categories; reviewers never enter amounts. "Accept all" is for an
// unchanged form, "Submit changes" for a changed one.

import type { DecisionRecord, LineDecision, LineOverride } from "../api/types";
import { OVERRIDE_REASONS } from "../lib/labels";

export interface LineState {
  lineNo: number;
  editable: boolean; // false for a line decided by a rule
  original: { decision: LineDecision; category: string | null };
  candidates: string[]; // benefit categories the plan offers for the line's code
  decision: LineDecision;
  category: string | null;
  reasonCode: string | null; // a Deny or Pend override's reason code
  reason: string; // the reviewer's note (the API's free-text reason)
}

/** The input an error belongs to, so the form marks that one. */
export type FormField = "reasonCode" | "reason" | "category";

export interface Checked {
  changed: number[];
  overrides: LineOverride[];
  errors: Record<number, string>;
  fields: Record<number, FormField>;
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
      reasonCode: null,
      reason: "",
    }));
}

/** The reason codes a decision allows: Deny and Pend have a list, Approve none. */
export function reasonCodes(decision: LineDecision): string[] {
  return decision === "APPROVE" ? [] : OVERRIDE_REASONS[decision];
}

/** Does the line need a reason code? A line changed to Deny or Pend. */
export function needsReasonCode(line: LineState): boolean {
  return reasonCodes(line.decision).length > 0;
}

/** The line with a new decision; a reason code the new decision does not allow is cleared. */
export function withDecision(line: LineState, decision: LineDecision): LineState {
  const keep = line.reasonCode !== null && reasonCodes(decision).includes(line.reasonCode);
  return { ...line, decision, reasonCode: keep ? line.reasonCode : null };
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
  const result: Checked = { changed: [], overrides: [], errors: {}, fields: {} };
  for (const line of lines) {
    if (!isChanged(line)) continue;
    const n = line.lineNo;
    result.changed.push(n);
    const fail = (field: FormField, message: string) => {
      result.errors[n] = message;
      result.fields[n] = field;
    };
    if (needsReasonCode(line) && !line.reasonCode) {
      fail("reasonCode", `Choose a reason for line ${n}.`);
    } else if (!line.reason.trim()) {
      fail("reason", `Write a note for changing line ${n}.`);
    } else if (needsCategory(line) && !line.category) {
      fail("category", `Choose a benefit category for line ${n}.`);
    }
    const override: LineOverride = {
      line_no: n,
      decision: line.decision,
      reason: line.reason.trim(),
    };
    if (needsCategory(line) && line.category) override.benefit_category = line.category;
    if (needsReasonCode(line) && line.reasonCode) override.reason_code = line.reasonCode;
    result.overrides.push(override);
  }
  return result;
}
