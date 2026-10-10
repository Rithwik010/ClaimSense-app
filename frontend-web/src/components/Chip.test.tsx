import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ClaimStatus } from "../api/types";
import { DecisionChip, StatusChip } from "./Chip";

describe("status chips", () => {
  it.each<[ClaimStatus, string, string]>([
    ["FINAL_APPROVED", "Approved", "bg-green-50"],
    ["FINAL_PENDED", "Needs information", "bg-amber-50"],
    ["PENDED_BY_RULE", "Pended by a rule", "bg-amber-50"],
    ["FINAL_DENIED", "Denied", "bg-red-50"],
    ["DENIED_BY_RULE", "Denied by a rule", "bg-red-50"],
    ["REJECTED", "Rejected", "bg-gray-100"],
  ])("shows %s as text with a muted colour", (status, label, colour) => {
    render(<StatusChip status={status} />);

    const chip = screen.getByText(label);
    expect(chip).toHaveClass(colour);
  });

  it("shows the plain-language hint when asked", () => {
    render(<DecisionChip decision="PEND" showHint />);

    expect(screen.getByText("Needs information")).toHaveAttribute("title", "PEND: needs more information");
    expect(screen.getByText("PEND: needs more information")).toBeInTheDocument();
  });
});
