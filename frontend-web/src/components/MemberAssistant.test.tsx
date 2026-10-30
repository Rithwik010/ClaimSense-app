// The member's plan assistant preview (D-MEM-4): on a member's pages only; its three quick questions
// answer from the member's own records as the API sends them, formatted only; asking in one's own
// words is shown disabled, as the later phase.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { MemberBenefits, MemberClaim, User } from "../api/types";
import { TooltipProvider } from "./ui/tooltip";
import { AuthProvider } from "../lib/auth";

const MEMBER: User = { username: "member1", display_name: "Carl Sanchez", role: "member", provider_id: null, member_id: "MBR-000015" };
const PROVIDER: User = { username: "provider1", display_name: "Joshua Rodriguez, DPT", role: "provider", provider_id: "2615054733" };

const OLDER: MemberClaim = {
  claim_id: "CLM-DEMO-01",
  received: "2026-11-05",
  service_date: "2026-10-28",
  provider_name: "Joshua Rodriguez, DPT",
  final: true,
  outcome: "APPROVED",
  heading: "Your claim was approved",
  message: "Your plan paid its share of each service.",
  eob: true,
  billed_cents: 20800,
  plan_pays_cents: 9233,
  patient_pays_cents: 3000,
};
const NEWER: MemberClaim = {
  ...OLDER,
  claim_id: "CLM-NEW-2",
  received: "2026-11-20",
  service_date: "2026-11-18",
  final: false,
  outcome: "PROCESSING",
  heading: "Your claim is being processed",
  message: "Your plan has the claim. What it pays shows here once the claim is decided.",
  eob: false,
  billed_cents: null,
  plan_pays_cents: null,
  patient_pays_cents: null,
};
const BENEFITS: MemberBenefits = {
  member_id: "MBR-000015",
  plan_id: "PLN-PPO-GOLD",
  plan_name: "ClaimSense PPO Gold",
  plan_type: "PPO",
  benefit_year_start: "2026-01-01",
  benefit_year_end: "2026-12-31",
  as_of: "2026-10-30",
  networks: [
    { network: "IN_NETWORK", period_start: "2026-01-01", deductible_met_cents: 42000, deductible_cents: 150000, oop_met_cents: 61240, oop_max_cents: 500000 },
    { network: "OUT_OF_NETWORK", period_start: "2026-01-01", deductible_met_cents: 0, deductible_cents: 300000, oop_met_cents: 0, oop_max_cents: 1000000 },
  ],
  visits: [{ benefit_category: "REHAB_THERAPY", visit_limit: 20, visits_used: 1 }],
};

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

describe("the member's plan assistant preview", () => {
  it("answers the quick questions from the member's own records, as the API sends them", async () => {
    serve({ "/v1/auth/me": MEMBER, "/v1/member/claims": [OLDER, NEWER], "/v1/member/benefits": BENEFITS });
    openAt("/member/claims");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Ask about your plan/ }));
    const panel = await screen.findByRole("dialog", { name: /Plan assistant/ });
    await user.click(within(panel).getByRole("button", { name: "How much of my deductible have I met?" }));
    await user.click(within(panel).getByRole("button", { name: "What is the status of my latest claim?" }));
    await user.click(within(panel).getByRole("button", { name: "How many visits have I used this year?" }));

    const answers = within(panel).getByRole("list", { name: "Answers" });
    expect(await within(answers).findByText(/In network: you have met \$420\.00 of your \$1,500\.00 deductible\./)).toBeInTheDocument();
    expect(within(answers).getByText(/Out of network: you have met \$0\.00 of your \$3,000\.00 deductible\./)).toBeInTheDocument();
    expect(within(answers).getByText(/Claim CLM-NEW-2, received 11\/20\/2026/)).toBeInTheDocument(); // the latest
    expect(within(answers).getByText("Being processed")).toBeInTheDocument();
    expect(within(answers).getByText(/Rehab therapy: 1 of 20 visits used this benefit year\./)).toBeInTheDocument();
    expect(within(answers).queryByText(/left|remaining/i)).not.toBeInTheDocument(); // nothing computed (D-MEM-3)
    expect(within(answers).getByRole("link", { name: "Open the claim" })).toHaveAttribute("href", "/member/claims/CLM-NEW-2");
  });

  it("shows asking in one's own words as a later phase, disabled", async () => {
    serve({ "/v1/auth/me": MEMBER, "/v1/member/claims": [] });
    openAt("/member/claims");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Ask about your plan/ }));
    const panel = await screen.findByRole("dialog", { name: /Plan assistant/ });
    expect(within(panel).getByLabelText("Ask in your own words")).toBeDisabled();
    expect(within(panel).getByRole("button", { name: "Send" })).toBeDisabled();
    expect(within(panel).getByText(/no AI model is used in this preview/)).toBeInTheDocument();
  });

  it("is on a member's pages only", async () => {
    serve({ "/v1/auth/me": PROVIDER, "/v1/claims": [] });
    openAt("/my-claims");

    expect(await screen.findByRole("heading", { name: "My claims" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Ask about your plan/ })).not.toBeInTheDocument();
  });
});
