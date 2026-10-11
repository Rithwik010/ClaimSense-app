// The API's JSON shapes the pages use (app/api/*.py, app/domain/contracts.py). Amounts are integer
// cents; the web app never computes an amount, it only formats the calculator's.

export type ClaimStatus =
  | "RECEIVED"
  | "AWAITING_REVIEW"
  | "FINAL_APPROVED"
  | "FINAL_DENIED"
  | "FINAL_PENDED"
  | "FINAL_PARTIAL"
  | "REJECTED"
  | "DENIED_BY_RULE"
  | "PENDED_BY_RULE";
export type LineDecision = "APPROVE" | "DENY" | "PEND";
export type ReviewTier = "QUICK" | "STANDARD" | "FULL";
export type SourceFormat = "JSON" | "DIGITAL_PDF" | "SCANNED";
export type Role = "provider" | "reviewer" | "admin";

/** The logged-in user (GET /v1/auth/me, D-AUTH-1). */
export interface User {
  username: string;
  display_name: string;
  role: Role;
  provider_id: string | null;
}
export type Claim = Record<string, unknown>;

export interface IntakeResult {
  claim: Claim;
  field_confidences: Record<string, number>;
  source_format: SourceFormat;
}

export interface FiledWithErrors {
  claim_id: string;
  status: ClaimStatus;
  source_format: SourceFormat;
  contract_errors: string[];
  received?: Claim;
  field_confidences?: Record<string, number>;
}

export interface RuleResult {
  rule_id: string;
  passed: boolean;
  outcome: string;
  reason_code: string | null;
  detail: string;
  line_no: number | null;
}

export interface BenefitFact {
  benefit_category: string;
}

export interface RetrievedCriterion {
  criterion_id: string;
  policy_id: string;
  policy_title: string;
  text: string;
}

export interface LineContext {
  line_no: number;
  procedure_code: string;
  candidate_benefits: BenefitFact[];
  criteria: RetrievedCriterion[];
}

export interface CriterionResult {
  criterion_id: string;
  status: "MET" | "NOT_MET" | "NOT_DOCUMENTED" | "NOT_APPLICABLE";
  evidence: string;
}

export interface SLMLine {
  line_no: number;
  decision: LineDecision;
  benefit_category: string;
  criteria: CriterionResult[];
  missing_information: string[];
}

export interface FinalLineDecision {
  line_no: number;
  decision: LineDecision;
  benefit_category: string | null;
  source: "RULE" | "MODEL" | "REVIEWER" | "VALIDATION";
  reason_codes: string[];
}

export interface Amounts {
  billed_cents: number;
  allowed_cents: number;
  contractual_adjustment_cents: number;
  deductible_cents: number;
  copay_cents: number;
  coinsurance_cents: number;
  cob_primary_paid_cents: number;
  plan_pays_cents: number;
  member_pays_cents: number;
  balance_bill_exposure_cents: number;
}

export interface LineAmounts extends Amounts {
  line_no: number;
}

export interface DecisionRecord {
  claim_id: string;
  status: ClaimStatus;
  rules_outcome: { claim_outcome: string; rule_results: RuleResult[] };
  context_refs: { lines: LineContext[] } | null;
  slm_output: { lines: SLMLine[] } | null;
  output_errors: string[];
  line_decisions: FinalLineDecision[];
  claim_decision: string | null;
  amounts: { lines: LineAmounts[]; totals: Amounts } | null;
  review_tier: ReviewTier | null;
  review: { reviewer_id: string; action: string } | null;
  versions: { rules_version: string; model_name: string | null; prompt_version: string | null };
  timestamps: { received: string; processed: string | null; finalized: string | null };
}

export interface Adjustment {
  line_no: number | null;
  reason_code: string;
  group_code: string;
  codes: { kind: "CARC" | "RARC"; code: string; description: string | null }[];
  billing_article: string | null;
  lcds: string[];
}

export interface ClaimView {
  claim_id: string;
  status: ClaimStatus;
  source_format: SourceFormat;
  intake: IntakeResult | null;
  received: Claim;
  field_confidences: Record<string, number>;
  record: DecisionRecord | null;
  adjustments?: Adjustment[];
}

export interface QueueItem {
  claim_id: string;
  review_tier: ReviewTier;
  claim_decision: string | null;
  total_allowed_cents: number | null;
  received_date: string;
  processed: string | null;
}

export interface ClaimSummary {
  claim_id: string;
  status: ClaimStatus;
  source_format: SourceFormat;
  received_date: string;
  updated: string;
  claim_decision: string | null;
  review_tier: ReviewTier | null;
  total_billed_cents: number | null;
  total_allowed_cents: number | null;
  plan_pays_cents: number | null;
  failed_rules: Omit<RuleResult, "passed">[];
}

export interface AuditEvent {
  id: number;
  event_type: string;
  actor: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface LineOverride {
  line_no: number;
  decision: LineDecision;
  reason: string;
  benefit_category?: string;
}

export interface ModelRow {
  model: string;
  prompt: string;
  records: number;
  valid_output: number;
  line_accuracy: number;
  macro_f1: number;
  criterion_accuracy: number;
  deny_precision: number;
  median_ms_per_claim: number;
}

export interface V2Errors {
  lines: number;
  wrong_lines: number;
  directions: { gold: LineDecision; predicted: LineDecision; lines: number }[];
  policies: { policy_id: string; lines: number; wrong: number }[];
  quick_claims: number;
  quick_claims_with_wrong_line: number;
}

export interface Evaluation {
  models: ModelRow[];
  macro_f1_target: number;
  ocr: { claims: number; fields: number; field_accuracy: number; blank_read_as_blank: number } | null;
  ocr_target: number;
  v2_errors: V2Errors | null;
}

/** A provider's own claim (D-AUTH-1): the decision only once final; until then IN_REVIEW. */
export interface ProviderClaimView {
  claim_id: string;
  status: ClaimStatus | "IN_REVIEW";
  final: boolean;
  source_format: SourceFormat;
  received: Claim;
  field_confidences: Record<string, number>;
  filed_by: string | null;
  record: DecisionRecord | null;
}

/** A provider's own claim in their list: the decision and amounts only once final. */
export interface ProviderClaimSummary {
  claim_id: string;
  status: ClaimStatus | "IN_REVIEW";
  final: boolean;
  source_format: SourceFormat;
  received_date: string;
  updated: string;
  claim_decision: string | null;
  total_billed_cents: number | null;
  total_allowed_cents: number | null;
  plan_pays_cents: number | null;
  failed_rules: { rule_id: string; outcome: string; reason_code: string | null; detail: string; line_no: number | null }[];
}
