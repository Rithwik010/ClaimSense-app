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
export type Role = "provider" | "reviewer" | "admin" | "member";

/** The logged-in user (GET /v1/auth/me, D-AUTH-1). A member (a patient, D-MEM-1) also has their
 * member ID; the API leaves it out for the other roles. */
export interface User {
  username: string;
  display_name: string;
  role: Role;
  provider_id: string | null;
  member_id?: string | null;
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
  context_refs: { plan_id: string; plan_type: string; network: string; excluded_codes: string[]; lines: LineContext[] } | null;
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

/** The label key every dashboard shows (D-UI-6): one per claim, from its status and lines. */
export type Outcome =
  | "NOT_PROCESSED"
  | "IN_REVIEW"
  | "APPROVED"
  | "PARTLY_APPROVED"
  | "PENDED"
  | "DENIED"
  | "REJECTED";

/** An original file kept with a claim (D-DOC-1), numbered in page order (D-DOC-2). */
export interface DocumentInfo {
  file_no: number;
  file_name: string;
  content_type: "application/json" | "application/pdf" | "image/png" | "image/jpeg";
  size_bytes: number;
}

/** One reason a claim or line was not paid as billed (reviewers and admins). */
export interface Reason {
  code: string;
  rule_id: string | null;
  line_no: number | null;
  short: string;
}

/** The claim summary (reviewers and admins), built from the record by the API. */
export interface ClaimSummaryLines {
  outcome: Outcome;
  outcome_label: string;
  items: { kind: "glance" | "checks" | "line" | "amounts" | "flags" | "outcome"; text: string; line_no: number | null }[];
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
  outcome: Outcome;
  summary: ClaimSummaryLines;
  documents: DocumentInfo[];
  /** GET /v1/claims/{id}/eob has the patient's explanation of benefits (D-EOB-1). */
  eob?: boolean;
  /** Plain names of the claim's codes, for the review header (D-REV-10). */
  names?: CodeNames;
  appeals?: Appeal[];
  follow_ups?: FollowUps;
}

/** Plain names of a claim's procedure and diagnosis codes (code tables in data/raw). */
export interface CodeNames {
  procedures: Record<string, string>;
  diagnoses: Record<string, string>;
  /** The billing provider's name, when on file. */
  provider?: string | null;
}

/** What can be done with a claim now (D-FUP-1, D-APL-1). */
export interface FollowUps {
  correct: boolean;
  documentation: boolean;
  appeal: boolean;
  reopened: boolean;
}

/** An appeal of a denied claim (D-APL-1). Who decided and the reason are for staff and the filer. */
export interface Appeal {
  appeal_id: number;
  status: "OPEN" | "DECIDED";
  outcome: "UPHELD" | "CHANGED" | null;
  filed_by: string;
  filed_role: "provider" | "member";
  filed_at: string;
  previous_status: string;
  previous_reviewer: string | null;
  decided_by: string | null;
  decided_at: string | null;
  reason: string | null;
}

export interface QueueItem {
  claim_id: string;
  review_tier: ReviewTier;
  claim_decision: string | null;
  total_allowed_cents: number | null;
  received_date: string;
  processed: string | null;
  provider_npi: string | null;
  provider_name: string | null;
  service_date: string | null;
  total_billed_cents: number | null;
  lines: number;
  flags: string[];
  member_id: string;
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
  adjustments: Adjustment[];
  member_id: string;
  provider_npi: string | null;
  provider_name: string | null;
  outcome: Outcome;
  reasons: Reason[];
  patient_name?: string | null;
  service_date?: string | null;
  appeal_open?: boolean;
}

export interface AuditEvent {
  id: number;
  claim_id?: string;
  event_type: string;
  actor: string;
  payload: Record<string, unknown>;
  rules_version?: string | null;
  model_name?: string | null;
  prompt_version?: string | null;
  policy_versions?: Record<string, string> | null;
  /** The API request that wrote it (D-OBS-1). */
  request_id?: string | null;
  created_at: string;
}

export interface LineOverride {
  line_no: number;
  decision: LineDecision;
  reason: string;
  benefit_category?: string;
  reason_code?: string; // a Deny or Pend override's reason code (D-REV-9)
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
  p95_ms_per_claim: number;
  per_class: Record<string, { precision: number | null; recall: number | null; f1: number | null; support: number | null }>;
}

export interface V2Errors {
  lines: number;
  wrong_lines: number;
  directions: { gold: LineDecision; predicted: LineDecision; lines: number }[];
  policies: { policy_id: string; lines: number; wrong: number }[];
  quick_claims: number;
  quick_claims_with_wrong_line: number;
}

export interface V3Scores {
  macro_f1: number;
  valid_output: number;
  line_accuracy: number;
  deny_precision: number;
  wrong_approvals: number;
}

/** Model v3 against v2 on one set, both measured on the same machine (D-V3-34). */
export interface V3Set {
  title: string;
  notes: string;
  claims: number;
  machine: string;
  v2: V3Scores;
  v3: V3Scores;
  macro_f1_difference_ci95: [number, number] | null;
}

export interface Evaluation {
  models: ModelRow[];
  macro_f1_target: number;
  ocr: { claims: number; fields: number; field_accuracy: number; blank_read_as_blank: number } | null;
  ocr_target: number;
  v2_errors: V2Errors | null;
  v3_sets: V3Set[];
  /** Reports not written on this machine, under data/generated/eval/. */
  missing?: string[];
}

/** A line of the provider's explanation: the whole claim (line_no null) or one line. */
export interface ExplanationItem {
  line_no: number | null;
  text: string;
}

export interface CodeGroup {
  line_no: number | null;
  codes: { kind: "CARC" | "RARC"; code: string; description: string | null }[];
  billing_article: string | null;
  lcds: string[];
}

export interface Reduction {
  kind: "allowed_amount" | "out_of_network" | "not_paid" | "deductible" | "copay" | "coinsurance" | "other_plan" | "note";
  amount_cents: number | null;
  text: string;
}

export interface BillingAmounts {
  billed_cents: number;
  allowed_cents: number;
  deductible_cents: number;
  copay_cents: number;
  coinsurance_cents: number;
  plan_pays_cents: number;
  patient_pays_cents: number;
  other_plan_paid_cents: number;
}

export interface BillingLine extends BillingAmounts {
  line_no: number;
  procedure_code: string;
  paid: boolean;
  reductions: Reduction[];
}

/** The provider's view of a final claim (D-UI-6), built by the API from the record. */
export interface ProviderExplanation {
  outcome: Outcome;
  heading: string;
  why: ExplanationItem[];
  review: ExplanationItem[];
  codes: CodeGroup[];
  billing: { lines: BillingLine[]; totals: BillingAmounts } | null;
}

/** A provider's own claim (D-AUTH-1): the decision only once final; until then IN_REVIEW. */
export interface ProviderClaimView {
  claim_id: string;
  status: ClaimStatus | "IN_REVIEW";
  outcome: Outcome;
  final: boolean;
  source_format: SourceFormat;
  received: Claim;
  filed_by: string | null;
  explanation: ProviderExplanation | null;
  /** The audit event types the claim went through, in order (no payloads): the stage strip. */
  stages: string[];
  documents: DocumentInfo[];
  eob?: boolean;
  follow_ups?: FollowUps;
  appeals?: Appeal[];
  names?: CodeNames;
}

/** A provider's own claim in their list: the decision and amounts only once final. */
export interface ProviderClaimSummary {
  claim_id: string;
  status: ClaimStatus | "IN_REVIEW";
  outcome: Outcome;
  final: boolean;
  source_format: SourceFormat;
  received_date: string;
  updated: string;
  claim_decision: string | null;
  total_billed_cents: number | null;
  total_allowed_cents: number | null;
  plan_pays_cents: number | null;
  /** As filed (D-UI-12): the patient, the first date of service and the charges billed. */
  patient_name?: string | null;
  service_date?: string | null;
  billed_cents?: number | null;
  appeal_open?: boolean;
}

/** GET /health (public). */
export interface Health {
  status: "ok" | "degraded";
  database: { ok: boolean; detail: string };
  qdrant: { ok: boolean; detail: string };
  ollama: { ok: boolean; detail: string };
}

/** GET /v1/metrics/overview (admin): counts over the claims on file, demo data. */
export interface Overview {
  claims: number;
  by_status: Record<string, number>;
  final_outcomes: Record<string, number>;
  queue_by_tier: Record<ReviewTier, number>;
  decided_by_rules: number;
  reviewed_accepted: number;
  reviewed_overridden: number;
  /** RECEIVED: read or filed, not processed yet. */
  not_processed?: number;
  extras?: OverviewExtras;
}

/** The Overview's money, times, reasons and trend (D-QLT-1). Rates in basis points. */
export interface OverviewExtras {
  billed_cents: number;
  plan_paid_cents: number;
  member_owes_cents: number;
  decided_claims: number;
  review_wait_seconds: number | null;
  review_seconds: number | null;
  override_rate_bp: number | null;
  top_reasons: { reason: string; claims: number }[];
  daily: { date: string; received: number; decided: number }[];
}

export interface QualityTally {
  reviews: number;
  lines: number;
  overridden: number;
  override_rate_bp: number | null;
  review_seconds: { count: number; median: number | null; p90: number | null };
}

/** GET /v1/metrics/quality (admin): how reviewers use the model's recommendations (D-QLT-1). */
export interface ReviewQuality {
  overall: QualityTally;
  acceptance_rate_bp: number | null;
  /** The model's line decision -> the final decision -> lines. */
  matrix: Record<string, Record<string, number>>;
  by_tier: Record<string, QualityTally>;
  by_reviewer: (QualityTally & { reviewer: string })[];
  by_policy: (QualityTally & { policy_id: string; title: string | null })[];
  feedback: { lines: number; criteria: number };
  appeals: { open: number; upheld: number; changed: number };
}

/** A login as the admin's Users page shows it (D-AUTH-2); never a password. */
export interface UserInfo {
  username: string;
  display_name: string;
  role: Role;
  provider_id: string | null;
  member_id: string | null;
  active: boolean;
  locked_until: string | null;
  password_changed_at: string | null;
  created_at: string | null;
}

/** GET /v1/audit/events (admin, D-AUD-1). */
export interface AuditSearch {
  events: (AuditEvent & { claim_id: string })[];
  limit: number;
  event_types: string[];
}

/** GET /v1/notifications (D-NTF-1): what happened lately on the user's claims. */
export interface Notification {
  id: number;
  claim_id: string;
  event_type: string;
  outcome: Outcome | "DUPLICATE" | null;
  appeal_outcome: "UPHELD" | "CHANGED" | null;
  created_at: string;
}

export interface Notifications {
  items: Notification[];
  latest_id: number | null;
}

/** Another reviewer with the claim open (D-REV-10). */
export interface OtherReviewer {
  reviewer_id: string;
  opened: string;
}

/** The coverage policy library (D-POL-9). */
export interface PolicySummary {
  policy_id: string;
  title: string;
  codes: { code: string; name: string | null }[];
  criteria: number;
  billing_article: string;
  effective_date: string;
}

export interface PolicyDetail extends PolicySummary {
  sources: string[];
  items: {
    criterion_id: string;
    text: string;
    criterion_type: string | null;
    applies_to: string[];
    group: string | null;
    source: string;
  }[];
}

/** GET /v1/metrics/system (admin): the versions the decision records name and the API's own. */
export interface SystemVersions {
  configured: Record<string, string>;
  in_records: {
    rules_version: string;
    model_name: string | null;
    prompt_version: string | null;
    policy_versions: string[];
    records: number;
    latest: string;
  }[];
}

export interface ResultsModelRow {
  model: string;
  records: number;
  valid_output: number;
  line_accuracy: number | null;
  macro_f1: number | null;
  deny_precision: number | null;
  criterion_accuracy: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
}

export interface GuardRow {
  model: string;
  line_accuracy: number;
  macro_f1: number;
  deny_precision: number;
  wrong_approvals: number;
  wrong_denials: number;
}

/** GET /v1/metrics/results (admin): the P6.1 results file, as scripts/verify/results_report.py writes it. */
export interface Results {
  generated: string;
  rules_and_calculator: Record<string, { passed: number; failed: number; skipped: number; error: number }>;
  extraction:
    | { held_out_claims: number; fields: number; field_accuracy: number; blank_read_as_blank: number; target: number }
    | string;
  retrieval_recall_at_3: string;
  models: ResultsModelRow[];
  evidence_guard: GuardRow[];
  macro_f1_target: number;
  latency_per_stage_ms: { source: string; claims: number } & Record<string, unknown>;
  reviewer_agreement: string;
  review_time: string;
}

/** GET /v1/plans/{plan_id} (reviewers and admins): the plan's terms, benefits and exclusions. */
export interface PlanBenefit {
  benefit_category: string;
  covered: boolean;
  auth_required: boolean;
  visit_limit: number | null;
  cost_share_rule: string;
  copay_cents: number | null;
}

export interface Plan {
  plan_id: string;
  name: string;
  plan_type: string;
  effective_date: string;
  filing_window_inn_days: number;
  filing_window_oon_days: number;
  oon_covered: boolean;
  inn_deductible_cents: number;
  inn_coinsurance_bps: number;
  inn_oop_max_cents: number;
  oon_deductible_cents: number | null;
  oon_coinsurance_bps: number | null;
  oon_oop_max_cents: number | null;
  benefits: PlanBenefit[];
  excluded_codes: string[];
}

/** One box of our claim form as read (D-FIX-1): its text as the form prints it. */
export interface FormBox {
  field: string;
  text: string | null;
  confidence: number | null;
  correctable: boolean;
  corrected: boolean;
}

/** A claim read from our form, box by box, and whether its boxes can still be corrected. */
export interface ClaimForm {
  claim_id: string;
  status: string;
  source_format: SourceFormat;
  correctable: boolean;
  boxes: FormBox[];
  contract_errors: string[];
}

export type CheckOutcome = "READY" | "LINES_DENIED" | "REJECTED" | "DENIED" | "PENDED";

export interface CheckItem {
  line_no: number | null;
  text: string;
  checks: string[];
  fields: string[];
}

export interface CoverageLine {
  line_no: number;
  procedure_code: string;
  policies: string[];
  needed: string[];
  one_of: string[];
  applies_when: string[];
  not_covered: string[];
}

/** What processing would find, before it runs (D-CHK-1). */
export interface ClaimCheck {
  claim_id: string;
  outcome: CheckOutcome;
  heading: string;
  problems: CheckItem[];
  notes: CheckItem[];
  coverage: CoverageLine[] | null;
  coverage_note: string | null;
}

export interface EobLine {
  line_no: number;
  date_of_service: string | null;
  procedure_code: string;
  service: string | null;
  status: "PAID" | "NOT_PAID" | "PENDING";
  billed_cents: number | null;
  allowed_cents: number | null;
  plan_pays_cents: number | null;
  patient_pays_cents: number | null;
  other_plan_paid_cents: number | null;
  notes: string[];
  codes: string[];
}

export interface EobTotals {
  billed_cents: number;
  allowed_cents: number;
  plan_pays_cents: number;
  patient_pays_cents: number;
  other_plan_paid_cents: number;
}

export interface YearToDate {
  network: string;
  period_start: string;
  deductible_met_cents: number;
  deductible_cents: number;
  oop_met_cents: number;
  oop_max_cents: number;
}

/** The patient's explanation of benefits of a decided claim (D-EOB-1). */
export interface PatientEob {
  claim_id: string;
  outcome: Outcome;
  patient_name: string | null;
  member_id: string | null;
  plan_name: string | null;
  provider_name: string | null;
  provider_npi: string | null;
  network: string | null;
  received: string;
  processed: string | null;
  lines: EobLine[];
  totals: EobTotals | null;
  year_to_date: YearToDate | null;
  notes: string[];
  codes: string[];
}

// --- The member's own pages (D-MEM-1, D-MEM-2, D-MEM-3): GET /v1/member/... ----------------------

/** One of the member's claims: "being processed" (PROCESSING) until final, then its outcome. */
export interface MemberClaim {
  claim_id: string;
  received: string;
  service_date: string | null;
  provider_name: string | null;
  final: boolean;
  outcome: Outcome | "PROCESSING" | "DUPLICATE";
  heading: string;
  message: string;
  /** GET /v1/member/claims/{id}/eob has the claim's patient EOB (D-EOB-1). */
  eob: boolean;
  /** Final claims with a calculation only: the record's totals. */
  billed_cents: number | null;
  plan_pays_cents: number | null;
  patient_pays_cents: number | null;
  /** Each service line's plain procedure name, in line order. */
  services: string[];
  appeal: MemberAppeal | null;
  /** POST /v1/member/claims/{id}/appeal accepts it now (D-APL-1). */
  can_appeal: boolean;
}

export interface MemberAppeal {
  status: "OPEN" | "DECIDED";
  outcome: "UPHELD" | "CHANGED" | null;
  filed_on: string;
  decided_on: string | null;
  filed_by_you: boolean;
}

export interface VisitBenefit {
  benefit_category: string;
  visit_limit: number;
  visits_used: number;
  /** The calculator's (D-MEM-5): never below zero. */
  visits_left: number;
  used_bps: number;
}

/** A network's year to date with what is left of each limit (the calculator's, D-MEM-3). */
export interface NetworkProgress extends YearToDate {
  deductible_left_cents: number;
  deductible_met_bps: number;
  oop_left_cents: number;
  oop_met_bps: number;
}

/** The plan's summary of benefits and coverage (P3.2), read into blocks by the API. */
export interface PlanSummary {
  plan_id: string;
  title: string;
  sections: {
    heading: string | null;
    blocks: {
      kind: "paragraph" | "list" | "table";
      text: string | null;
      items: string[];
      header: string[];
      rows: string[][];
    }[];
  }[];
}

/** The member's benefit year so far: each network's limits and what is met, as stored. */
export interface MemberBenefits {
  member_id: string;
  plan_id: string;
  plan_name: string;
  plan_type: string;
  benefit_year_start: string;
  benefit_year_end: string;
  as_of: string;
  networks: NetworkProgress[];
  visits: VisitBenefit[];
}

export interface MemberProfile {
  member_id: string;
  name: string;
  plan_id: string;
  plan_name: string;
  plan_type: string;
  coverage_start: string;
  coverage_end: string | null;
}
