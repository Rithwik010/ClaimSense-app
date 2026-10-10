import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ClaimStatus } from "../api/types";
import { DecisionChip, StatusChip } from "./Chip";

describe("status chips", () => {
  it.each<[ClaimStatus, string, string]>([
    ["FINAL_APPROVED", "Approved", "bg-approve-tint"],
    ["FINAL_PENDED", "Needs information", "bg-pend-tint"],
    ["PENDED_BY_RULE", "Pended by a rule", "bg-pend-tint"],
    ["FINAL_DENIED", "Denied", "bg-deny-tint"],
    ["DENIED_BY_RULE", "Denied by a rule", "bg-deny-tint"],
    ["REJECTED", "Rejected", "bg-reject-tint"],
  ])("shows %s as text and an icon on a tint", (status, label, tint) => {
    render(<StatusChip status={status} />);

    const chip = screen.getByText(label);
    expect(chip).toHaveClass(tint);
    expect(chip.querySelector("svg")).not.toBeNull(); // never colour alone
  });

  it("shows the plain-language hint when asked", () => {
    render(<DecisionChip decision="PEND" showHint />);

    expect(screen.getByText("Pend")).toHaveAttribute("title", "Needs more information");
    expect(screen.getByText("Needs more information")).toBeInTheDocument();
  });
});
