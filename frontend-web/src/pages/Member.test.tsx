// The member's pages (D-MEM-1, D-MEM-2, D-MEM-3): a member lands on My claims with only their own
// pages; a claim shows "Being processed" until final and nothing of its outcome; a decided claim
// opens its EOB; benefits and profile show what the API sends, formatted only (nothing computed);
// another role's pages say "You don't have access", and a member's pages do to other roles.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { MemberBenefits, MemberClaim, MemberProfile, PatientEob, User } from "../api/types";
import { TooltipProvider } from "../components/ui/tooltip";
import { AuthProvider } from "../lib/auth";

const MEMBER: User = {
  username: "member1",
  display_name: "Timothy Townsend",
  role: "member",
  provider_id: null,
  member_id: "MBR-000152",
};
const PROVIDER: User = { username: "provider1", display_name: "Gregory Hernandez, DPT", role: "provider", provider_id: "2829620345" };

const PROCESSING: MemberClaim = {
  claim_id: "CLM-NEW-1",
  received: "2026-11-12",
  service_date: "2026-11-10",
  provider_name: "Gregory Hernandez, DPT",
  final: false,
  outcome: "PROCESSING",
  heading: "Your claim is being processed",
  message: "Your plan has the claim. What it pays shows here once the claim is decided.",
  eob: false,
  billed_cents: null,
  plan_pays_cents: null,
  patient_pays_cents: null,
  services: ["Physical therapy, therapeutic exercise"],
  appeal: null,
  can_appeal: false,
};
const APPROVED: MemberClaim = {
  ...PROCESSING,
  claim_id: "CLM-DEMO-01",
  service_date: "2026-10-06",
  final: true,
  outcome: "APPROVED",
  heading: "Your claim was approved",
  message: "Your plan paid its share of each service.",
  eob: true,
  billed_cents: 15500,
  plan_pays_cents: 12345,
  patient_pays_cents: 200, // as the API sends it: not billed - plan paid
};
const EOB: PatientEob = {
  claim_id: "CLM-DEMO-01",
  outcome: "APPROVED",
  patient_name: "Timothy Townsend",
  member_id: "MBR-000152",
  plan_name: "ClaimSense HMO Select",
  provider_name: "Gregory Hernandez, DPT",
  provider_npi: "2829620345",
  network: "IN_NETWORK",
  received: "2026-10-09",
  processed: "2026-10-20",
  lines: [
    {
      line_no: 1,
      date_of_service: "2026-10-06",
      procedure_code: "97161",
      service: "Physical therapy evaluation",
      status: "PAID",
      billed_cents: 15500,
      allowed_cents: 12545,
      plan_pays_cents: 12345,
      patient_pays_cents: 200,
      other_plan_paid_cents: 0,
      notes: [],
      codes: [],
    },
  ],
  totals: { billed_cents: 15500, allowed_cents: 12545, plan_pays_cents: 12345, patient_pays_cents: 200, other_plan_paid_cents: 0 },
  year_to_date: null,
  notes: ["This is not a bill."],
  codes: [],
};
const BENEFITS: MemberBenefits = {
  member_id: "MBR-000152",
  plan_id: "PLN-HMO",
  plan_name: "ClaimSense HMO Select",
  plan_type: "HMO",
  benefit_year_start: "2026-01-01",
  benefit_year_end: "2026-12-31",
  as_of: "2026-10-20",
  networks: [
    {
      network: "IN_NETWORK",
      period_start: "2026-01-01",
      deductible_met_cents: 25000,
      deductible_cents: 25000,
      oop_met_cents: 399800,
      oop_max_cents: 400000,
      // The calculator's: nothing left of the deductible (100%); 4000.00 - 3998.00 = 2.00 left,
      // 99.95% used.
      deductible_left_cents: 0,
      deductible_met_bps: 10000,
      oop_left_cents: 200,
      oop_met_bps: 9995,
    },
  ],
  visits: [{ benefit_category: "REHAB_THERAPY", visit_limit: 20, visits_used: 13, visits_left: 7, used_bps: 6500 }],
};
const PROFILE: MemberProfile = {
  member_id: "MBR-000152",
  name: "Timothy Townsend",
  plan_id: "PLN-HMO",
  plan_name: "ClaimSense HMO Select",
  plan_type: "HMO",
  coverage_start: "2025-01-01",
  coverage_end: null,
};

type Answer = { status: number; body?: unknown };

function serve(routes: Record<string, Answer>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).split("?")[0]!;
      calls.push(path);
      const { status, body } = routes[path] ?? { status: 404, body: { detail: "Not Found" } };
      return new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
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
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});
afterEach(() => vi.unstubAllGlobals());

const ME = { "/v1/auth/me": { status: 200, body: MEMBER } };

describe("a member's pages", () => {
  it("lands a member on My claims, with only a member's pages", async () => {
    serve({ ...ME, "/v1/member/claims": { status: 200, body: [] } });
    openAt("/");

    expect(await screen.findByRole("heading", { name: "My claims" })).toBeInTheDocument();
    const nav = screen.getAllByRole("list")[0]!;
    expect(within(nav).getByText("My benefits")).toBeInTheDocument();
    expect(within(nav).getByText("Profile")).toBeInTheDocument();
    for (const other of ["Submit claim", "Review queue", "Claims", "Overview", "Audit lookup"]) {
      expect(within(nav).queryByText(other)).not.toBeInTheDocument();
    }
    expect(screen.getAllByText("Member").length).toBeGreaterThan(0);
    expect(await screen.findByText("No claims yet")).toBeInTheDocument();
  });

  it("shows a claim being processed with nothing of its outcome, and a final one as the API sends it", async () => {
    serve({ ...ME, "/v1/member/claims": { status: 200, body: [PROCESSING, APPROVED] } });
    openAt("/member/claims");

    const table = await screen.findByRole("table", { name: "My claims" });
    const waiting = within(table).getByRole("row", { name: /CLM-NEW-1/ });
    expect(within(waiting).getByText("Being processed")).toBeInTheDocument();
    expect(within(waiting).queryByText(/\$/)).not.toBeInTheDocument();
    const decided = within(table).getByRole("row", { name: /CLM-DEMO-01/ });
    expect(within(decided).getByText("Approved")).toBeInTheDocument();
    expect(within(decided).getByText("$123.45")).toBeInTheDocument();
    expect(within(decided).getByText("$2.00")).toBeInTheDocument(); // the API's amount, not billed - paid
    expect(within(decided).getByText("10/06/2026")).toBeInTheDocument();
    expect(within(decided).getByRole("link", { name: "CLM-DEMO-01" })).toHaveAttribute("href", "/member/claims/CLM-DEMO-01");
  });

  it("opens a decided claim on its explanation of benefits", async () => {
    serve({
      ...ME,
      "/v1/member/claims/CLM-DEMO-01": { status: 200, body: APPROVED },
      "/v1/member/claims/CLM-DEMO-01/eob": { status: 200, body: EOB },
    });
    openAt("/member/claims/CLM-DEMO-01");

    expect(await screen.findByRole("heading", { name: "Explanation of benefits" })).toBeInTheDocument();
    expect(screen.getByText("This is not a bill.")).toBeInTheDocument();
    expect(screen.getByText(/What your plan did with each service/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to my claims" })).toHaveAttribute("href", "/member/claims");
    expect(screen.getAllByText("$123.45").length).toBeGreaterThan(0);
  });

  it("says a claim is being processed and does not ask for an EOB it does not have", async () => {
    const calls = serve({ ...ME, "/v1/member/claims/CLM-NEW-1": { status: 200, body: PROCESSING } });
    openAt("/member/claims/CLM-NEW-1");

    expect(await screen.findByRole("heading", { name: "Your claim is being processed" })).toBeInTheDocument();
    expect(screen.getByText("Being processed")).toBeInTheDocument();
    expect(screen.queryByText("Explanation of benefits")).not.toBeInTheDocument();
    expect(calls).not.toContain("/v1/member/claims/CLM-NEW-1/eob");
  });

  it("says another member's claim is not found", async () => {
    serve({ ...ME, "/v1/member/claims/CLM-DEMO-04": { status: 404, body: { detail: "claim CLM-DEMO-04 not found" } } });
    openAt("/member/claims/CLM-DEMO-04");
    expect(await screen.findByText("Not found: claim CLM-DEMO-04 not found")).toBeInTheDocument();
  });

  it("shows the benefits as the API sends them, what is left included, computing nothing", async () => {
    serve({ ...ME, "/v1/member/benefits": { status: 200, body: BENEFITS } });
    openAt("/member/benefits");

    expect(await screen.findByRole("heading", { name: "My benefits" })).toBeInTheDocument();
    const inNetwork = screen.getByRole("region", { name: "In network" });
    expect(within(inNetwork).getByText("$250.00")).toBeInTheDocument();
    expect(within(inNetwork).getByText("of a $250.00 deductible")).toBeInTheDocument();
    expect(within(inNetwork).getByText("$3,998.00")).toBeInTheDocument();
    expect(within(inNetwork).getByText("of a $4,000.00 out-of-pocket maximum")).toBeInTheDocument();
    // What is left and the bars are the API's (the calculator's, D-MEM-5), as sent.
    expect(within(inNetwork).getByText("Met for this year")).toBeInTheDocument();
    expect(within(inNetwork).getByText("$2.00 to go before you pay no more cost share for covered care")).toBeInTheDocument();
    expect(within(inNetwork).getByRole("meter", { name: "Out-of-pocket spent" })).toHaveAttribute("aria-valuenow", "99.95");
    expect(screen.queryByRole("region", { name: "Out of network" })).not.toBeInTheDocument();
    expect(screen.getByText("Your plan covers in-network care only.")).toBeInTheDocument();
    const visits = within(screen.getByRole("table", { name: "Visits" })).getByRole("row", { name: /Rehab therapy/ });
    expect(within(visits).getByText("13")).toBeInTheDocument();
    expect(within(visits).getByText("20")).toBeInTheDocument();
    expect(within(visits).getByText("7")).toBeInTheDocument(); // visits left, as sent
    expect(screen.getByText(/ClaimSense HMO Select \(HMO\), benefit year 01\/01\/2026 to 12\/31\/2026/)).toBeInTheDocument();
  });

  it("shows the profile: name, member ID, plan and coverage dates", async () => {
    serve({ ...ME, "/v1/member/profile": { status: 200, body: PROFILE } });
    openAt("/member/profile");

    expect(await screen.findByRole("heading", { name: "Profile" })).toBeInTheDocument();
    for (const text of ["Timothy Townsend", "MBR-000152", "ClaimSense HMO Select (HMO)", "01/01/2025", "No end date"]) {
      expect(screen.getAllByText(text).length).toBeGreaterThan(0);
    }
  });

  it.each(["/my-claims", "/submit", "/my-claims/CLM-DEMO-01/eob", "/queue", "/claims/CLM-DEMO-01", "/review/CLM-DEMO-08", "/overview", "/metrics"])(
    "tells a member they have no access to %s",
    async (path) => {
      serve(ME);
      openAt(path);
      expect(await screen.findByText("You don't have access")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Go to your home page" })).toHaveAttribute("href", "/member/claims");
    },
  );

  it.each(["/member/claims", "/member/benefits", "/member/profile"])("tells a provider they have no access to %s", async (path) => {
    serve({ "/v1/auth/me": { status: 200, body: PROVIDER } });
    openAt(path);
    expect(await screen.findByText("You don't have access")).toBeInTheDocument();
    expect(screen.getByText(/This page is for a member\./)).toBeInTheDocument();
  });
});
