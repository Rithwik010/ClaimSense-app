// Plain-language labels with short hints for outcomes, statuses, decisions, tiers and reason codes.
// One outcome label set for every dashboard (D-UI-6): the API names each claim's outcome; the
// status labels use the same words, with hints that tell the review and the automatic checks
// apart. The reason labels are the wording the reviewer's explanation uses (render.py).

import type { ClaimStatus, LineDecision, Outcome, ReviewTier } from "../api/types";

export type Tone = "approve" | "pend" | "deny" | "reject" | "neutral";

export interface Label {
  label: string;
  hint: string;
  tone: Tone;
}

/** The outcome labels every dashboard shows (the API's `outcome`). */
export const OUTCOME: Record<Outcome, Label> = {
  NOT_PROCESSED: { label: "Not processed", hint: "Received, not processed yet", tone: "neutral" },
  IN_REVIEW: { label: "In review", hint: "A reviewer decides", tone: "neutral" },
  APPROVED: { label: "Approved", hint: "Every line approved", tone: "approve" },
  PARTLY_APPROVED: { label: "Partly approved", hint: "Some lines paid, some not", tone: "approve" },
  PENDED: { label: "Pended", hint: "On hold: more information needed", tone: "pend" },
  DENIED: { label: "Denied", hint: "The plan does not pay", tone: "deny" },
  REJECTED: { label: "Rejected", hint: "Returned: the claim data could not be used", tone: "reject" },
};

/** The status filter's options: the provider's, the reviewer's and admin's, and the returned page's. */
export const PROVIDER_FILTERS: Outcome[] = [
  "NOT_PROCESSED",
  "IN_REVIEW",
  "APPROVED",
  "PARTLY_APPROVED",
  "PENDED",
  "DENIED",
  "REJECTED",
];
export const STAFF_FILTERS: Outcome[] = PROVIDER_FILTERS;
export const RETURNED_FILTERS: Outcome[] = ["REJECTED", "DENIED", "PENDED"];

/** Status labels in the same words, for counts kept by status (the admin overview). */
export const STATUS: Record<ClaimStatus, Label> = {
  RECEIVED: { label: "Not processed", hint: "Received, not processed yet", tone: "neutral" },
  AWAITING_REVIEW: { label: "In review", hint: "A reviewer decides", tone: "neutral" },
  FINAL_APPROVED: { label: "Approved", hint: "Every line approved after review", tone: "approve" },
  FINAL_PARTIAL: { label: "Partly approved", hint: "Some lines approved after review", tone: "approve" },
  FINAL_DENIED: { label: "Denied", hint: "No line approved after review", tone: "deny" },
  FINAL_PENDED: { label: "Pended", hint: "More information needed after review", tone: "pend" },
  REJECTED: { label: "Rejected", hint: "Returned by the automatic checks", tone: "reject" },
  DENIED_BY_RULE: { label: "Denied", hint: "Denied by the automatic checks", tone: "deny" },
  PENDED_BY_RULE: { label: "Pended", hint: "Put on hold by the automatic checks", tone: "pend" },
};

export const DECISION: Record<LineDecision, Label> = {
  APPROVE: { label: "Approve", hint: "The plan pays its share", tone: "approve" },
  DENY: { label: "Deny", hint: "The plan does not pay", tone: "deny" },
  PEND: { label: "Pend", hint: "Needs more information", tone: "pend" },
};

export const TIER: Record<ReviewTier, Label> = {
  QUICK: { label: "Quick", hint: "Every line recommended for approval, nothing to check closely", tone: "neutral" },
  STANDARD: {
    label: "Standard",
    hint: "A line to pend, a medium-complexity case, a high amount or a field read with low confidence",
    tone: "neutral",
  },
  FULL: {
    label: "Full",
    hint: "A line recommended for denial, a high-complexity case, or a model answer that could not be used",
    tone: "neutral",
  },
};

export const SOURCE: Record<string, string> = {
  RULE: "A rule",
  MODEL: "Model recommendation",
  REVIEWER: "Reviewer",
  VALIDATION: "Output check",
};

/** What a provider sees of a claim still being reviewed (D-AUTH-1): no recommendation. */
export const IN_REVIEW: Label = {
  label: "In review",
  hint: "A reviewer checks it; the decision shows once it is final",
  tone: "neutral",
};

/** What a member sees of their claim until it is final (D-MEM-2): nothing of its outcome. */
export const PROCESSING: Label = {
  label: "Being processed",
  hint: "Your plan is working on it; the outcome shows once it is decided",
  tone: "neutral",
};

/** A member's claim the checks closed as a copy of one the plan already has (D-MEM-2). */
export const DUPLICATE: Label = {
  label: "Already sent",
  hint: "A copy of a claim your plan already has: nothing to do",
  tone: "neutral",
};

/** A member's label for their claim (the API's outcome; PROCESSING until final). */
export function memberOutcome(outcome: Outcome | "PROCESSING" | "DUPLICATE"): Label {
  if (outcome === "DUPLICATE") return DUPLICATE;
  return outcome === "PROCESSING" || outcome === "IN_REVIEW" || outcome === "NOT_PROCESSED"
    ? PROCESSING
    : OUTCOME[outcome];
}

/** A benefit category in words: "REHAB_THERAPY" -> "Rehab therapy". */
export function benefitCategory(code: string): string {
  const text = code.replaceAll("_", " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** What a provider sees of a claim they filed and have not processed (fix 1, D-UI-6 as amended):
 * nobody reviews it until they process it, so it is not "In review". */
export const NOT_PROCESSED: Label = {
  label: "Not processed",
  hint: "Filed, not processed yet: open it to check and process it",
  tone: "neutral",
};

/** A provider's label for their claim's outcome: "Not processed" until they process it (its
 * status RECEIVED), then "In review" until final. */
export function providerOutcome(outcome: Outcome, status?: string): Label {
  if (status === "RECEIVED" || outcome === "NOT_PROCESSED") return NOT_PROCESSED;
  return outcome === "IN_REVIEW" ? IN_REVIEW : OUTCOME[outcome];
}

/** A provider's claim as its list filters it: "Not processed" until they process it. */
export function providerListOutcome(claim: { outcome: Outcome; status: string }): Outcome {
  return claim.status === "RECEIVED" ? "NOT_PROCESSED" : claim.outcome;
}

/** An appeal's outcome (D-APL-1). */
export const APPEAL_OUTCOME: Record<string, string> = {
  UPHELD: "The decision stood",
  CHANGED: "The decision changed",
};

export const CLAIM_DECISION: Record<string, Label> = {
  APPROVE: { label: "Approve", hint: "Every line approved", tone: "approve" },
  PARTIAL: { label: "Partly approve", hint: "Some lines approved", tone: "approve" },
  PEND: { label: "Pend", hint: "Needs more information", tone: "pend" },
  DENY: { label: "Deny", hint: "No line approved", tone: "deny" },
};

export const CRITERION_STATUS: Record<string, string> = {
  MET: "Met",
  NOT_MET: "Not met",
  NOT_DOCUMENTED: "Not documented",
  NOT_APPLICABLE: "Does not apply",
};

export const REASONS: Record<string, string> = {
  RJ_MISSING_FIELD: "a required field is missing",
  RJ_INVALID_CODE: "a code is not valid",
  RJ_INVALID_NPI: "the provider NPI is not valid",
  RJ_MEMBER_NOT_FOUND: "the member was not found",
  RJ_PROVIDER_NOT_FOUND: "the provider was not found",
  RJ_DUPLICATE: "the claim duplicates one already filed",
  RJ_LOW_CONFIDENCE_FIELD: "a rule failed on a field read with low confidence",
  DN_NOT_ELIGIBLE: "the member was not covered on the date of service",
  DN_LATE_FILING: "the claim was filed after the plan's filing window",
  DN_OUT_OF_NETWORK: "out-of-network care that the plan does not cover",
  DN_MISSING_REFERRAL: "a required referral is missing",
  DN_NO_AUTH: "a required prior authorization is missing",
  DN_NCCI_BUNDLED: "the service is bundled into another service on the claim (NCCI)",
  DN_MUE_EXCEEDED: "more units than the medically unlikely edit allows",
  DN_EXCLUDED: "the plan excludes this service",
  DN_MULTIPLE_BLOCKS: "another block on the same day (epidural steroid injection policy)",
  DN_DX_NOT_SUPPORTED: "the diagnoses do not support the service (billing article)",
  DN_HOME_TEST_PARASOMNIA: "a home sleep test billed for a parasomnia",
  DN_ESI_LEVELS: "more epidural injection levels than the policy allows",
  DN_FACET_LEVELS: "more facet levels than the policy allows",
  DN_VISIT_LIMIT: "the plan's yearly visit limit for this service is used up",
  DN_NOT_MEDICALLY_NECESSARY: "not medically necessary under the coverage criteria",
  DN_CONDITIONAL_EXCLUSION: "a coverage policy excludes the service in this situation",
  PD_PROVIDER_ENROLLMENT: "the provider's enrollment needs checking",
  PD_MISSING_DOCUMENTATION: "documentation is missing",
  MODEL_OUTPUT_INVALID: "the recommendation could not be used and needs a full review",
};

export function reason(code: string | null | undefined): string {
  if (!code) return "";
  return REASONS[code] ? `${REASONS[code]} (${code})` : code;
}

/** The reason codes a reviewer gives a Deny or Pend override (D-REV-9; the API's list,
 *  app/review/actions.py OVERRIDE_REASONS). The provider sees the reason and its codes. */
export const OVERRIDE_REASONS: Record<"DENY" | "PEND", string[]> = {
  DENY: [
    "DN_NOT_MEDICALLY_NECESSARY",
    "DN_CONDITIONAL_EXCLUSION",
    "DN_NCCI_BUNDLED",
    "DN_MUE_EXCEEDED",
    "DN_EXCLUDED",
    "DN_MULTIPLE_BLOCKS",
    "DN_DX_NOT_SUPPORTED",
    "DN_HOME_TEST_PARASOMNIA",
    "DN_ESI_LEVELS",
    "DN_FACET_LEVELS",
    "DN_VISIT_LIMIT",
  ],
  PEND: ["PD_MISSING_DOCUMENTATION"],
};

/** A reason code's label for a choice list: "Documentation is missing (PD_MISSING_DOCUMENTATION)". */
export function reasonOption(code: string): string {
  const text = REASONS[code] ?? code;
  return `${text.charAt(0).toUpperCase()}${text.slice(1)} (${code})`;
}

export const LOW_CONFIDENCE = 0.85; // EXTRACTION_CONFIDENCE_MIN

/** The review queue's flags (app/workflow/review.py queue_flags): facts the record holds. */
export const FLAGS: Record<string, string> = {
  MODEL_ANSWER_UNUSABLE: "Model answer unusable",
  QUOTE_NOT_IN_NOTE: "Quote not in the note",
  CALCULATION_FAILED: "No amounts",
  LOW_CONFIDENCE_FIELDS: "Low-confidence fields",
  HIGH_DOLLAR: "High amount",
  LINE_DECIDED_BY_RULE: "Line decided by a rule",
  APPEAL: "Appeal: decide again",
};

const DECIDED: Record<LineDecision, string> = {
  APPROVE: "Covered under the plan's benefits",
  PEND: "More information is needed",
  DENY: "Not covered",
};

/** A line's outcome in plain words: its reasons, or what its decision means when it has none. */
export function lineReason(decision: LineDecision, reasonCodes: string[]): string {
  const known = reasonCodes.map((code) => REASONS[code]).filter((text): text is string => Boolean(text));
  if (known.length === 0) return DECIDED[decision];
  const text = known.join("; ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// The evidence guard's entries in a record's output_errors (D-EVID-1): check results, not errors.
const GUARD_NOTE = /^EVIDENCE_NOT_IN_NOTES: line (\d+) (\S+)$/;

export function evidenceChecks(outputErrors: string[]): { lineNo: number; criterionId: string }[] {
  return outputErrors.flatMap((entry) => {
    const found = GUARD_NOTE.exec(entry);
    return found ? [{ lineNo: Number(found[1]), criterionId: found[2] ?? "" }] : [];
  });
}

export function answerErrors(outputErrors: string[]): string[] {
  return outputErrors.filter((entry) => !GUARD_NOTE.test(entry));
}
