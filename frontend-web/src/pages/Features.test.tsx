// The dashboard improvements (D-UI-12 and the review fixes): formatting helpers, the provider's
// list (not processed, on hold, the columns filed), the follow-up buttons, the audit trail's
// override details, the notifications' words, and the review page's appeal and other-reviewer
// notices. Every amount and rate here is the API's, as sent.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { AuditEvent, Notification, ProviderClaimSummary, ProviderClaimView, User } from "../api/types";
import { details } from "../components/AuditTimeline";
import { notificationText } from "../components/HeaderTools";
import { csvMoney, toCsv } from "../components/ListTools";
import { TooltipProvider } from "../components/ui/tooltip";
import { AuthProvider } from "../lib/auth";
import { duration } from "../lib/format";
import { memberOutcome, providerListOutcome } from "../lib/labels";
import { totalNames } from "./ClaimDetail";

const PROVIDER: User = { username: "provider1", display_name: "Joshua Rodriguez, DPT", role: "provider", provider_id: "2615054733" };

function mine(claim_id: string, status: string, outcome: ProviderClaimSummary["outcome"], final: boolean): ProviderClaimSummary {
  return {
    claim_id,
    status: status as ProviderClaimSummary["status"],
    outcome,
    final,
    source_format: "JSON",
    received_date: "2026-11-01",
    updated: "2026-11-02T10:00:00Z",
    claim_decision: null,
    total_billed_cents: final ? 20800 : null,
    total_allowed_cents: null,
    plan_pays_cents: final ? 0 : null,
    patient_name: "Erica Ramsey",
    service_date: "2026-10-28",
    billed_cents: 20800,
    appeal_open: false,
  };
}

function serve(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).split("?")[0]!;
      const found = path in routes;
      return new Response(JSON.stringify(found ? routes[path] : { detail: "Not Found" }), {
        status: found ? 200 : 404,
        headers: { "content-type": "application/json" },
      });
    }),
  );
}

function openAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <TooltipProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {} }));
});
afterEach(() => vi.unstubAllGlobals());

describe("formatting only", () => {
  it("writes CSV with quoting and dollars from cents", () => {
    expect(csvMoney(123456)).toBe("1234.56");
    expect(csvMoney(5)).toBe("0.05");
    expect(csvMoney(null)).toBe("");
    const text = toCsv([{ a: 'say "hi", then go', b: 3 }], [
      { header: "A", value: (r) => r.a },
      { header: "B", value: (r) => r.b },
    ]);
    expect(text).toBe('A,B\r\n"say ""hi"", then go",3\r\n');
  });

  it("says durations in words", () => {
    expect(duration(null)).toBe("—");
    expect(duration(42)).toBe("42 s");
    expect(duration(720)).toBe("12 min");
    expect(duration(3 * 3600 + 5 * 60)).toBe("3 h 5 min");
    expect(duration(2 * 86400 + 4 * 3600)).toBe("2 d 4 h");
  });

  it("names changed totals in words, never field names (fix 6)", () => {
    expect(totalNames(["allowed_cents", "contractual_adjustment_cents", "plan_pays_cents"])).toBe(
      "allowed, contractual adjustment and plan pays",
    );
  });
});

describe("labels", () => {
  it("shows a provider's unprocessed claim as not processed (fix 1)", () => {
    expect(providerListOutcome({ status: "RECEIVED", outcome: "IN_REVIEW" })).toBe("NOT_PROCESSED");
    expect(providerListOutcome({ status: "IN_REVIEW", outcome: "IN_REVIEW" })).toBe("IN_REVIEW");
  });

  it("tells a member a duplicate apart from a returned claim", () => {
    expect(memberOutcome("DUPLICATE").label).toBe("Already sent");
    expect(memberOutcome("REJECTED").label).toBe("Rejected");
  });

  it("puts an override's lines, decisions, code and note in the audit trail (fix 4)", () => {
    const event: AuditEvent = {
      id: 1,
      event_type: "REVIEW_OVERRIDDEN",
      actor: "reviewer1",
      created_at: "2026-11-02T10:00:00Z",
      payload: {
        changes: [
          {
            line_no: 1,
            reason: "Test repeated this month",
            reason_code: "DN_NOT_MEDICALLY_NECESSARY",
            before: { decision: "APPROVE" },
            after: { decision: "DENY" },
          },
        ],
      },
    };
    expect(details(event)).toEqual(["Line 1: Approve → Deny (DN_NOT_MEDICALLY_NECESSARY). Note: Test repeated this month"]);
  });

  it("words each notification for its reader", () => {
    const base: Notification = {
      id: 9,
      claim_id: "CLM-1",
      event_type: "FINALIZED",
      outcome: "DENIED",
      appeal_outcome: null,
      created_at: "2026-11-02T10:00:00Z",
    };
    expect(notificationText(base, "provider")).toBe("Claim CLM-1 is final: denied");
    expect(notificationText({ ...base, event_type: "AUTO_OUTCOME", outcome: "DUPLICATE" }, "member")).toBe(
      "Claim CLM-1 is final: already sent",
    );
    expect(notificationText({ ...base, event_type: "APPEAL_DECIDED", appeal_outcome: "CHANGED" }, "provider")).toBe(
      "The appeal of claim CLM-1 is decided: the decision changed",
    );
    expect(notificationText({ ...base, event_type: "SLM_RECOMMENDED" }, "reviewer")).toBe("Claim CLM-1 is ready for review");
  });
});

describe("the provider's pages", () => {
  it("lists the patient, date of service and billed amount; not processed and on hold in words", async () => {
    serve({
      "/v1/auth/me": PROVIDER,
      "/v1/claims": [
        mine("CLM-READ", "RECEIVED", "IN_REVIEW", false),
        mine("CLM-HOLD", "FINAL_PENDED", "PENDED", true),
      ],
      "/v1/notifications": { items: [], latest_id: null },
    });
    openAt("/my-claims");

    const table = within(await screen.findByRole("table"));
    const read = table.getByRole("row", { name: /CLM-READ/ });
    expect(within(read).getByText("Not processed")).toBeInTheDocument();
    expect(within(read).getByText("Erica Ramsey")).toBeInTheDocument();
    expect(within(read).getByText("10/28/2026")).toBeInTheDocument();
    expect(within(read).getByText("$208.00")).toBeInTheDocument();
    const hold = table.getByRole("row", { name: /CLM-HOLD/ });
    expect(within(hold).getByText("On hold")).toBeInTheDocument(); // not "$0.00" (fix 7)
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeEnabled();
  });

  it("offers what can be done with a decided claim, as the API allows", async () => {
    const view: ProviderClaimView = {
      claim_id: "CLM-HOLD",
      status: "FINAL_PENDED",
      outcome: "PENDED",
      final: true,
      source_format: "JSON",
      received: {},
      filed_by: "provider1",
      explanation: {
        outcome: "PENDED",
        heading: "More information needed",
        why: [{ line_no: 1, text: "Documentation is missing." }],
        review: [],
        codes: [],
        billing: null,
      },
      stages: ["INTAKE_COMPLETED", "RULES_EVALUATED", "SLM_RECOMMENDED", "EXPLANATION_BUILT", "FINALIZED"],
      documents: [],
      follow_ups: { correct: false, documentation: true, appeal: false, reopened: false },
      appeals: [],
    };
    serve({ "/v1/auth/me": PROVIDER, "/v1/claims/CLM-HOLD": view, "/v1/notifications": { items: [], latest_id: null } });
    openAt("/my-claims/CLM-HOLD");

    expect(await screen.findByRole("button", { name: "Send documentation" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Correct and resubmit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Appeal the decision" })).not.toBeInTheDocument();
  });
});
