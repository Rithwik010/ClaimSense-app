import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ClaimStatus, LineDecision } from "../api/types";
import { FLAGS, lineReason, providerStatus, STATUS } from "../lib/labels";
import { Chip, DecisionChip, PlainBadge, StatusChip } from "./Chip";

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

  it("gives every claim status a text label and an icon", () => {
    for (const status of Object.keys(STATUS) as ClaimStatus[]) {
      const { unmount } = render(<StatusChip status={status} />);
      const chip = screen.getByText(STATUS[status].label);
      expect(chip.textContent?.trim()).not.toBe("");
      expect(chip.querySelector("svg")).not.toBeNull();
      unmount();
    }
  });

  it.each<[LineDecision, string, string]>([
    ["APPROVE", "Approve", "bg-approve-tint"],
    ["PEND", "Pend", "bg-pend-tint"],
    ["DENY", "Deny", "bg-deny-tint"],
  ])("shows a line decision %s as text and an icon on a tint", (decision, label, tint) => {
    render(<DecisionChip decision={decision} />);

    const chip = screen.getByText(label);
    expect(chip).toHaveClass(tint);
    expect(chip.querySelector("svg")).not.toBeNull();
  });
});

describe("what a provider sees", () => {
  it("shows a claim in review as In review, neutral, with no decision colour", () => {
    render(<Chip label={providerStatus("IN_REVIEW")} showHint />);

    const chip = screen.getByText("In review");
    expect(chip).not.toHaveClass("bg-approve-tint");
    expect(chip).not.toHaveClass("bg-deny-tint");
    expect(screen.getByText("A reviewer checks it; the decision shows once it is final")).toBeInTheDocument();
  });

  it("shows a final status as the reviewer sees it", () => {
    expect(providerStatus("FINAL_APPROVED")).toBe(STATUS.FINAL_APPROVED);
    expect(providerStatus("REJECTED").label).toBe("Rejected");
  });

  it("explains a line in plain words, from its reasons or its decision", () => {
    expect(lineReason("DENY", ["DN_NCCI_BUNDLED"])).toBe(
      "The service is bundled into another service on the claim (NCCI)",
    );
    expect(lineReason("APPROVE", [])).toBe("Covered under the plan's benefits");
    expect(lineReason("PEND", ["UNKNOWN_CODE"])).toBe("More information is needed");
  });
});

describe("plain badges", () => {
  it("labels review flags in words", () => {
    render(<PlainBadge>{FLAGS.LOW_CONFIDENCE_FIELDS}</PlainBadge>);

    expect(screen.getByText("Low-confidence fields")).toBeInTheDocument();
  });
});
