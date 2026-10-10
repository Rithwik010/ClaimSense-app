import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { confidenceOf, FieldsTable, flatten } from "./Fields";

describe("fields table", () => {
  it("flattens a claim into labelled paths and formats cents", () => {
    const rows = flatten({ claim_id: "C1", service_lines: [{ charge_cents: 12345, modifiers: ["25", "59"] }] });

    expect(rows).toEqual([
      { path: "claim_id", value: "C1" },
      { path: "service_lines.0.charge_cents", value: "$123.45" },
      { path: "service_lines.0.modifiers", value: "25 59" },
    ]);
  });

  it("takes a field's confidence from the box it was read from", () => {
    expect(confidenceOf("other_coverage.primary_paid.0.paid_cents", { "other_coverage.primary_paid.0": 0.7 })).toBe(0.7);
    expect(confidenceOf("claim_id", {})).toBeNull();
  });

  it("highlights low confidence and lists unreadable fields", () => {
    render(
      <FieldsTable
        claim={{ claim_id: "C1", member_id: "M1" }}
        confidences={{ claim_id: 0.97, member_id: 0.42, billing_tin: 0 }}
        jsonClaim={false}
      />,
    );

    expect(screen.getByText("2 fields read with low confidence", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("(could not be read)")).toBeInTheDocument();
    expect(screen.getAllByText("Low")).toHaveLength(2);
  });
});
