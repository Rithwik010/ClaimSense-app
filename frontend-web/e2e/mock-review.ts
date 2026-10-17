// A synthetic claim awaiting review and a mocked API for the Playwright specs that need no running
// stack and no database (D-REV-9 override sheet). The claim is synthetic.

import type { Page, Route } from "@playwright/test";

export const CLAIM_ID = "CLM-MOCK-REASON-01";
const ZERO = {
  billed_cents: 0,
  allowed_cents: 0,
  contractual_adjustment_cents: 0,
  deductible_cents: 0,
  copay_cents: 0,
  coinsurance_cents: 0,
  cob_primary_paid_cents: 0,
  plan_pays_cents: 0,
  member_pays_cents: 0,
  balance_bill_exposure_cents: 0,
};
const AMOUNTS = {
  ...ZERO,
  billed_cents: 120000,
  allowed_cents: 45000,
  contractual_adjustment_cents: 75000,
  deductible_cents: 20000,
  coinsurance_cents: 5000,
  plan_pays_cents: 20000,
  member_pays_cents: 25000,
};
const CLAIM = {
  claim_id: CLAIM_ID,
  member_id: "MBR-000123",
  patient: {
    first_name: "Test",
    last_name: "Patient",
    date_of_birth: "1981-04-02",
    sex: "F",
    address: { line1: "1 Test Way", city: "Austin", state: "TX", zip_code: "78701" },
  },
  subscriber_is_patient: true,
  billing_npi: "1234567893",
  billing_tin: "123456789",
  referring_npi: null,
  prior_auth_number: null,
  diagnoses: ["R51.9"],
  service_lines: [
    {
      line_no: 1,
      date_of_service: "2026-10-05",
      place_of_service: "11",
      procedure_code: "70551",
      modifiers: [],
      diagnosis_pointers: ["A"],
      units: 1,
      charge_cents: 120000,
      rendering_npi: "1234567893",
    },
  ],
  clinical_notes: "Headache for 6 weeks with new focal weakness on examination.",
  received_date: "2026-10-12",
  frequency_code: "1",
  other_coverage: null,
};
const RECORD = {
  claim_id: CLAIM_ID,
  status: "AWAITING_REVIEW",
  rules_outcome: { claim_outcome: "PASS", rule_results: [], line_outcomes: [], flags: [] },
  context_refs: {
    claim_id: CLAIM_ID,
    plan_id: "PLN-PPO-GOLD",
    plan_type: "PPO",
    network: "IN_NETWORK",
    excluded_codes: [],
    lines: [
      {
        line_no: 1,
        procedure_code: "70551",
        candidate_benefits: [{ benefit_category: "ADVANCED_IMAGING" }],
        criteria: [
          {
            criterion_id: "POL-IMG-001.c1",
            policy_id: "POL-IMG-001",
            policy_title: "Brain MRI",
            text: "A neurologic deficit is documented.",
          },
        ],
        rule_flags: [],
      },
    ],
  },
  slm_output: {
    lines: [
      {
        line_no: 1,
        decision: "APPROVE",
        benefit_category: "ADVANCED_IMAGING",
        criteria: [{ criterion_id: "POL-IMG-001.c1", status: "MET", evidence: "new focal weakness on examination" }],
        reasons: [],
        missing_information: [],
      },
    ],
    complexity: "LOW",
  },
  output_errors: [],
  line_decisions: [
    { line_no: 1, decision: "APPROVE", benefit_category: "ADVANCED_IMAGING", source: "MODEL", reason_codes: [] },
  ],
  claim_decision: "APPROVE",
  amounts: { lines: [{ line_no: 1, ...AMOUNTS }], totals: AMOUNTS },
  review_tier: "QUICK",
  review: null,
  versions: { rules_version: "2.2.0", model_name: "claimsense-decision:v2", prompt_version: "decision_v3" },
  timestamps: { received: "2026-10-12", processed: "2026-10-12T10:00:00Z", finalized: null },
};
const VIEW = {
  claim_id: CLAIM_ID,
  status: "AWAITING_REVIEW",
  source_format: "JSON",
  intake: { claim: CLAIM, field_confidences: {}, source_format: "JSON" },
  received: CLAIM,
  field_confidences: {},
  record: RECORD,
  adjustments: [],
};

/** Answers every API call the review page makes; records the review the page sends. */
export async function mockApi(page: Page): Promise<{ sent: unknown[] }> {
  const sent: unknown[] = [];
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  await page.route("**/health", (route) => json(route, { status: "ok" }));
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    if (url.pathname === "/v1/auth/me") {
      return json(route, { username: "reviewer-mock", display_name: "Mock Reviewer", role: "reviewer", provider_id: null });
    }
    if (url.pathname === `/v1/claims/${CLAIM_ID}` && method === "GET") return json(route, VIEW);
    if (url.pathname === `/v1/claims/${CLAIM_ID}/review/open`) return json(route, {});
    if (url.pathname === `/v1/claims/${CLAIM_ID}/review` && method === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      sent.push(body);
      return json(route, {
        ...RECORD,
        status: "FINAL_DENIED",
        claim_decision: "DENY",
        line_decisions: [
          { line_no: 1, decision: "DENY", benefit_category: "ADVANCED_IMAGING", source: "REVIEWER", reason_codes: ["DN_NOT_MEDICALLY_NECESSARY"] },
        ],
        amounts: { lines: [{ line_no: 1, ...ZERO, billed_cents: 120000 }], totals: { ...ZERO, billed_cents: 120000 } },
        review: { reviewer_id: "reviewer-mock", action: "OVERRIDE" },
      });
    }
    if (url.pathname.endsWith("/audit") || url.pathname.startsWith("/v1/review/queue")) return json(route, []);
    return json(route, []);
  });
  return { sent };
}
