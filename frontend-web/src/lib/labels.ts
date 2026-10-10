// Plain-language labels with short hints for statuses, decisions, tiers and reason codes. The
// reason labels are the same wording the explanation uses (app/explain/render.py).

import type { ClaimStatus, LineDecision, ReviewTier } from "../api/types";

export type Tone = "green" | "amber" | "red" | "grey" | "blue";

export interface Label {
  label: string;
  hint: string;
  tone: Tone;
}

export const STATUS: Record<ClaimStatus, Label> = {
  RECEIVED: { label: "Received", hint: "not processed yet", tone: "blue" },
  AWAITING_REVIEW: { label: "Awaiting review", hint: "a reviewer decides", tone: "blue" },
  FINAL_APPROVED: { label: "Approved", hint: "every line approved", tone: "green" },
  FINAL_PARTIAL: { label: "Partly approved", hint: "some lines approved", tone: "green" },
  FINAL_DENIED: { label: "Denied", hint: "no line approved", tone: "red" },
  FINAL_PENDED: { label: "Needs information", hint: "PEND: needs more information", tone: "amber" },
  REJECTED: { label: "Rejected", hint: "REJECT: the claim data cannot be used", tone: "grey" },
  DENIED_BY_RULE: { label: "Denied by a rule", hint: "a coverage rule failed", tone: "red" },
  PENDED_BY_RULE: {
    label: "Pended by a rule",
    hint: "PEND: needs more information",
    tone: "amber",
  },
};

export const DECISION: Record<LineDecision, Label> = {
  APPROVE: { label: "Approved", hint: "APPROVE: the plan pays its share", tone: "green" },
  DENY: { label: "Denied", hint: "DENY: the plan does not pay", tone: "red" },
  PEND: { label: "Needs information", hint: "PEND: needs more information", tone: "amber" },
};

export const TIER: Record<ReviewTier, Label> = {
  QUICK: { label: "Quick", hint: "a quick check", tone: "grey" },
  STANDARD: { label: "Standard", hint: "a standard review", tone: "blue" },
  FULL: { label: "Full", hint: "a full review", tone: "amber" },
};

export const SOURCE: Record<string, string> = {
  RULE: "a rule",
  MODEL: "the model's recommendation",
  REVIEWER: "the reviewer",
  VALIDATION: "output validation",
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
