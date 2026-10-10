// Plain-language labels with short hints for statuses, decisions, tiers and reason codes. The
// reason labels are the same wording the explanation uses (app/explain/render.py).

import type { ClaimStatus, LineDecision, ReviewTier } from "../api/types";

export type Tone = "approve" | "pend" | "deny" | "reject" | "neutral";

export interface Label {
  label: string;
  hint: string;
  tone: Tone;
}

export const STATUS: Record<ClaimStatus, Label> = {
  RECEIVED: { label: "Received", hint: "Not processed yet", tone: "neutral" },
  AWAITING_REVIEW: { label: "Awaiting review", hint: "A reviewer decides", tone: "neutral" },
  FINAL_APPROVED: { label: "Approved", hint: "Every line approved", tone: "approve" },
  FINAL_PARTIAL: { label: "Partly approved", hint: "Some lines approved", tone: "approve" },
  FINAL_DENIED: { label: "Denied", hint: "No line approved", tone: "deny" },
  FINAL_PENDED: { label: "Needs information", hint: "Pended: needs more information", tone: "pend" },
  REJECTED: { label: "Rejected", hint: "The claim data cannot be used", tone: "reject" },
  DENIED_BY_RULE: { label: "Denied by a rule", hint: "A coverage rule failed", tone: "deny" },
  PENDED_BY_RULE: { label: "Pended by a rule", hint: "Needs more information", tone: "pend" },
};

export const DECISION: Record<LineDecision, Label> = {
  APPROVE: { label: "Approve", hint: "The plan pays its share", tone: "approve" },
  DENY: { label: "Deny", hint: "The plan does not pay", tone: "deny" },
  PEND: { label: "Pend", hint: "Needs more information", tone: "pend" },
};

export const TIER: Record<ReviewTier, Label> = {
  QUICK: { label: "Quick", hint: "A quick check", tone: "neutral" },
  STANDARD: { label: "Standard", hint: "A standard review", tone: "neutral" },
  FULL: { label: "Full", hint: "A full review", tone: "neutral" },
};

export const SOURCE: Record<string, string> = {
  RULE: "A rule",
  MODEL: "Model recommendation",
  REVIEWER: "Reviewer",
  VALIDATION: "Output check",
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

export const LOW_CONFIDENCE = 0.85; // EXTRACTION_CONFIDENCE_MIN

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
