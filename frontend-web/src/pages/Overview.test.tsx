// The admin's Overview (D-UI-10): each headline count opens the list behind it, the reviewed-claims
// tile opens the claims a reviewer finalized, and there is no "Demo data" badge; Claims keeps
// ?reviewed=1 to those claims, under a note that shows them all again.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { ClaimStatus, ClaimSummary, Outcome, Overview, User } from "../api/types";
import { TooltipProvider } from "../components/ui/tooltip";
import { AuthProvider } from "../lib/auth";

const ADMIN: User = { username: "admin1", display_name: "Demo Admin", role: "admin", provider_id: null };

const OVERVIEW: Overview = {
  claims: 3,
  by_status: { FINAL_APPROVED: 1, DENIED_BY_RULE: 1, AWAITING_REVIEW: 1 },
  final_outcomes: { FINAL_APPROVED: 1, DENIED_BY_RULE: 1 },
  queue_by_tier: { QUICK: 0, STANDARD: 0, FULL: 1 },
  decided_by_rules: 1,
  reviewed_accepted: 1,
  reviewed_overridden: 0,
};

function claim(claim_id: string, status: ClaimStatus, outcome: Outcome): ClaimSummary {
  return {
    claim_id,
    status,
    source_format: "JSON",
    received_date: "2026-10-28",
    updated: "2026-10-30T10:00:00Z",
    claim_decision: null,
    review_tier: null,
    total_billed_cents: 20800,
    total_allowed_cents: null,
    plan_pays_cents: null,
    failed_rules: [],
    adjustments: [],
    member_id: "MBR-000015",
    provider_npi: "2615054733",
    provider_name: "Joshua Rodriguez, DPT",
    outcome,
    reasons: [],
  };
}

const CLAIMS = [
  claim("CLM-REVIEWED", "FINAL_APPROVED", "APPROVED"),
  claim("CLM-BY-RULE", "DENIED_BY_RULE", "DENIED"),
  claim("CLM-WAITING", "AWAITING_REVIEW", "IN_REVIEW"),
];

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

describe("the admin's overview", () => {
  it("opens the list behind each headline count, with no demo-data badge", async () => {
    serve({ "/v1/auth/me": ADMIN, "/v1/metrics/overview": OVERVIEW });
    openAt("/overview");

    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    for (const [tile, href] of [
      ["Claims on file", "/claims"],
      ["Waiting for review", "/queue"],
      ["Decided by rules", "/rule-outcomes"],
      ["Lines overridden", "/claims?reviewed=1"],
    ] as const) {
      expect(await screen.findByRole("link", { name: new RegExp(tile) })).toHaveAttribute("href", href);
    }
    expect(screen.getByRole("link", { name: "Open reviewed claims" })).toHaveAttribute("href", "/claims?reviewed=1");
    expect(screen.queryByText("Demo data")).not.toBeInTheDocument();
  });

  it("keeps the claims list to the claims a reviewer finalized until asked to show all", async () => {
    serve({ "/v1/auth/me": ADMIN, "/v1/claims": CLAIMS });
    openAt("/claims?reviewed=1");
    const user = userEvent.setup();

    // The list is cards on a phone and a table from 768 px, both in the page: look in the table.
    const table = async () => within(await screen.findByRole("table"));
    expect((await table()).getByRole("link", { name: "CLM-REVIEWED" })).toBeInTheDocument();
    expect((await table()).queryByRole("link", { name: "CLM-BY-RULE" })).not.toBeInTheDocument(); // a rule outcome
    expect((await table()).queryByRole("link", { name: "CLM-WAITING" })).not.toBeInTheDocument();
    expect(screen.getByText(/Showing the claims a reviewer finalized/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show all claims" }));
    expect(await (await table()).findByRole("link", { name: "CLM-BY-RULE" })).toBeInTheDocument();
    expect((await table()).getByRole("link", { name: "CLM-WAITING" })).toBeInTheDocument();
    expect(screen.queryByText(/Showing the claims a reviewer finalized/)).not.toBeInTheDocument();
  });
});
