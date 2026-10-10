import { describe, expect, it } from "vitest";

import type { DecisionRecord } from "../api/types";
import { check, initialLines, needsCategory, type LineState } from "./form";

function record(): DecisionRecord {
  return {
    claim_id: "CLM-T-1",
    status: "AWAITING_REVIEW",
    rules_outcome: { claim_outcome: "PASS", rule_results: [] },
    context_refs: {
      lines: [
        { line_no: 1, procedure_code: "97110", candidate_benefits: [{ benefit_category: "PHYSICAL_THERAPY" }, { benefit_category: "CHIROPRACTIC" }], criteria: [] },
        { line_no: 2, procedure_code: "70551", candidate_benefits: [{ benefit_category: "ADVANCED_IMAGING" }], criteria: [] },
        { line_no: 3, procedure_code: "99213", candidate_benefits: [{ benefit_category: "OFFICE_VISIT" }], criteria: [] },
      ],
    },
    slm_output: null,
    output_errors: [],
    line_decisions: [
      { line_no: 2, decision: "PEND", benefit_category: "ADVANCED_IMAGING", source: "MODEL", reason_codes: ["PD_MISSING_DOCUMENTATION"] },
      { line_no: 1, decision: "APPROVE", benefit_category: "PHYSICAL_THERAPY", source: "MODEL", reason_codes: [] },
      { line_no: 3, decision: "DENY", benefit_category: null, source: "RULE", reason_codes: ["DN_NCCI_BUNDLED"] },
    ],
    claim_decision: "APPROVE",
    amounts: null,
    review_tier: "STANDARD",
    review: null,
    versions: { rules_version: "2.1.0", model_name: null, prompt_version: null },
    timestamps: { received: "2026-10-01", processed: null, finalized: null },
  };
}

function edit(lines: LineState[], lineNo: number, change: Partial<LineState>): LineState[] {
  return lines.map((line) => (line.lineNo === lineNo ? { ...line, ...change } : line));
}

describe("review form", () => {
  it("starts unchanged, in line order, with rule lines read-only", () => {
    const lines = initialLines(record());

    expect(lines.map((l) => [l.lineNo, l.editable])).toEqual([[1, true], [2, true], [3, false]]);
    expect(check(lines)).toEqual({ changed: [], overrides: [], errors: {} });
  });

  it("needs a reason for every changed line", () => {
    const lines = edit(initialLines(record()), 2, { decision: "DENY" });

    expect(check(lines).errors).toEqual({ 2: "Give a reason for changing line 2." });
    const fixed = check(edit(lines, 2, { reason: "  No change since last MRI.  " }));
    expect(fixed.errors).toEqual({});
    expect(fixed.overrides).toEqual([{ line_no: 2, decision: "DENY", reason: "No change since last MRI." }]);
  });

  it("treats a blank reason as missing", () => {
    const lines = edit(initialLines(record()), 2, { decision: "APPROVE", reason: "   " });

    expect(check(lines).errors[2]).toBe("Give a reason for changing line 2.");
  });

  it("asks for a category only on an approved line with several candidates", () => {
    const lines = initialLines(record());

    expect(lines.map(needsCategory)).toEqual([true, false, false]);
    const recategorized = edit(lines, 1, { category: "CHIROPRACTIC", reason: "Chiropractor billed it." });
    expect(check(recategorized).overrides).toEqual([
      { line_no: 1, decision: "APPROVE", reason: "Chiropractor billed it.", benefit_category: "CHIROPRACTIC" },
    ]);
    const missing = edit(lines, 1, { category: null, reason: "Not sure." });
    expect(check(missing).errors[1]).toBe("Choose a benefit category for line 1.");
  });

  it("never changes a line decided by a rule", () => {
    const lines = edit(initialLines(record()), 3, { decision: "APPROVE", reason: "Try" });

    expect(check(lines).changed).toEqual([]);
  });

  it("sends no category for a line moved away from approve", () => {
    const lines = edit(initialLines(record()), 1, { decision: "PEND", reason: "Need notes." });

    expect(check(lines).overrides).toEqual([{ line_no: 1, decision: "PEND", reason: "Need notes." }]);
  });
});
