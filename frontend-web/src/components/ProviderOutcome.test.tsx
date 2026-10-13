import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ProviderExplanation } from "../api/types";
import { Billing } from "./Billing";
import { ProviderOutcome } from "./ProviderOutcome";

const REJECTED: ProviderExplanation = {
  outcome: "REJECTED",
  heading: "Claim rejected",
  why: [{ line_no: null, text: "The member ID on the claim does not match any member of the plan." }],
  review: [{ line_no: null, text: "Member ID on the claim: MBR-977777" }],
  codes: [{ line_no: null, codes: [{ kind: "CARC", code: "31", description: "Patient cannot be identified." }], billing_article: null, lcds: [] }],
  billing: null,
};

const LINE = {
  line_no: 1,
  procedure_code: "99213",
  paid: true,
  billed_cents: 30000,
  allowed_cents: 24000,
  deductible_cents: 5000,
  copay_cents: 0,
  coinsurance_cents: 3800,
  plan_pays_cents: 15200,
  patient_pays_cents: 8800,
  other_plan_paid_cents: 0,
  reductions: [
    { kind: "allowed_amount" as const, amount_cents: 6000, text: "Reduced by $60.00 to the plan's allowed amount for this service." },
    { kind: "deductible" as const, amount_cents: 5000, text: "$50.00 applied to the patient's deductible." },
  ],
};

describe("the provider's explanation", () => {
  it("shows the outcome, why, what to check and the codes, in that order", () => {
    render(<ProviderOutcome explanation={REJECTED} />);

    expect(screen.getByRole("heading", { level: 2, name: "Claim rejected" })).toBeInTheDocument();
    const why = screen.getByRole("region", { name: "Why" });
    expect(within(why).getByText(/does not match any member/)).toBeInTheDocument();
    const check = screen.getByRole("region", { name: "Please review the following details" });
    expect(within(check).getByText("Member ID on the claim: MBR-977777")).toBeInTheDocument();
    expect(screen.getByText("CARC 31")).toBeInTheDocument();
  });

  it("labels a line-level reason by its line", () => {
    render(<ProviderOutcome explanation={{ ...REJECTED, why: [{ line_no: 2, text: "Not paid separately." }] }} />);

    expect(screen.getByText("Line 2: Not paid separately.")).toBeInTheDocument();
  });

  it("shows the billing per line, its reductions and the totals as the API gives them", () => {
    render(<Billing lines={[LINE]} totals={LINE} />);

    const table = screen.getByRole("table", { name: "Billing" });
    for (const header of ["Billed", "Allowed", "Deductible", "Copay", "Coinsurance", "Plan pays", "Patient pays"]) {
      expect(within(table).getByRole("columnheader", { name: header })).toBeInTheDocument();
    }
    expect(within(table).getAllByText("$300.00")).toHaveLength(2); // the line and the total
    expect(within(table).getByText("Reduced by $60.00 to the plan's allowed amount for this service.")).toBeInTheDocument();
    // The phone layout: the same line and sentences as cards (CSS shows one or the other).
    const cards = screen.getByRole("list", { name: "Billing" });
    expect(within(cards).getByText("Reduced by $60.00 to the plan's allowed amount for this service.")).toBeInTheDocument();
    expect(within(cards).getAllByText("$300.00")).toHaveLength(2);
  });
});
