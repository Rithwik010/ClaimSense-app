import { describe, expect, it } from "vitest";

import type { DecisionRecord } from "../api/types";
import { check, initialLines, needsCategory, needsReasonCode, withDecision, type LineState } from "./form";

function record(): DecisionRecord {
  return {
    claim_id: "CLM-T-1",
    status: "AWAITING_REVIEW",
    rules_outcome: { claim_outcome: "PASS", rule_results: [] },
    context_refs: {
      plan_id: "PLN-PPO-GOLD",
      plan_type: "PPO",
      network: "IN_NETWORK",
      excluded_codes: [],
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
    expect(check(lines)).toEqual({ changed: [], overrides: [], errors: {}, fields: {} });
  });

  it("needs a reason code for a line changed to deny or pend, then a note", () => {
    const lines = edit(initialLines(record()), 2, { decision: "DENY" });

    expect(check(lines).errors).toEqual({ 2: "Choose a reason for line 2." });
    expect(check(lines).fields).toEqual({ 2: "reasonCode" });
    const coded = edit(lines, 2, { reasonCode: "DN_NOT_MEDICALLY_NECESSARY" });
    expect(check(coded).errors).toEqual({ 2: "Write a note for changing line 2." });
    expect(check(coded).fields).toEqual({ 2: "reason" });
    const fixed = check(edit(coded, 2, { reason: "  No change since last MRI.  " }));
    expect(fixed.errors).toEqual({});
    expect(fixed.overrides).toEqual([
      { line_no: 2, decision: "DENY", reason: "No change since last MRI.", reason_code: "DN_NOT_MEDICALLY_NECESSARY" },
    ]);
  });

  it("asks for a reason code on deny and pend only, and drops one the new decision does not allow", () => {
    const line = initialLines(record())[0] as LineState;

    expect(needsReasonCode({ ...line, decision: "DENY" })).toBe(true);
    expect(needsReasonCode({ ...line, decision: "PEND" })).toBe(true);
    expect(needsReasonCode(line)).toBe(false); // approve
    const denied = { ...withDecision(line, "DENY"), reasonCode: "DN_VISIT_LIMIT" };
    expect(withDecision(denied, "PEND").reasonCode).toBeNull();
    expect(withDecision(denied, "APPROVE").reasonCode).toBeNull();
    const pended = { ...withDecision(line, "PEND"), reasonCode: "PD_MISSING_DOCUMENTATION" };
    expect(withDecision(pended, "PEND").reasonCode).toBe("PD_MISSING_DOCUMENTATION");
  });

  it("treats a blank note as missing", () => {
    const lines = edit(initialLines(record()), 2, { decision: "APPROVE", reason: "   " });

    expect(check(lines).errors[2]).toBe("Write a note for changing line 2.");
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
    const lines = edit(initialLines(record()), 1, {
      decision: "PEND",
      reasonCode: "PD_MISSING_DOCUMENTATION",
      reason: "Need notes.",
    });

    expect(check(lines).overrides).toEqual([
      { line_no: 1, decision: "PEND", reason: "Need notes.", reason_code: "PD_MISSING_DOCUMENTATION" },
    ]);
  });
});

describe("evidence checks", () => {
  it("separates the evidence guard's entries from answer errors", async () => {
    const { answerErrors, evidenceChecks } = await import("../lib/labels");
    const entries = ["EVIDENCE_NOT_IN_NOTES: line 2 POL-IMG-001.c1", "line 1 is missing from the output"];

    expect(evidenceChecks(entries)).toEqual([{ lineNo: 2, criterionId: "POL-IMG-001.c1" }]);
    expect(answerErrors(entries)).toEqual(["line 1 is missing from the output"]);
  });
});
