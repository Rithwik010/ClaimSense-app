import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuditEvent, ClaimForm } from "../api/types";
import { corrections } from "./AuditTimeline";
import { formatHint } from "./CorrectDialog";
import { FormFields } from "./FormFields";

const FORM: ClaimForm = {
  claim_id: "CLM-FIX-1",
  status: "RECEIVED",
  source_format: "SCANNED",
  correctable: true,
  contract_errors: [],
  boxes: [
    { field: "claim_id", text: "CLM-FIX-1", confidence: 0.99, correctable: false, corrected: false },
    { field: "billing_npi", text: "1234567890", confidence: 0.41, correctable: true, corrected: false },
    { field: "member_id", text: "MBR-000123", confidence: 1, correctable: true, corrected: true },
    { field: "service_lines.0.units", text: null, confidence: 0, correctable: true, corrected: false },
  ],
};

describe("the boxes read from the form (D-FIX-1)", () => {
  it("marks low-confidence and corrected boxes in words, and offers Correct where allowed", () => {
    const onCorrect = vi.fn();
    render(<FormFields form={FORM} onCorrect={onCorrect} flagged={new Set(["billing_npi"])} />);

    const table = screen.getByRole("table", { name: "Boxes read from the form" });
    const npi = within(table).getByRole("row", { name: /Billing NPI/ });
    expect(within(npi).getByText("Low")).toBeInTheDocument();
    expect(within(npi).getByText("Named by the check")).toBeInTheDocument();
    expect(within(npi).getByText("41%")).toBeInTheDocument();
    const member = within(table).getByRole("row", { name: /Member ID/ });
    expect(within(member).getByText("Corrected")).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /Line 1 · Units/ })).toHaveTextContent("(could not be read)");
    expect(screen.queryByRole("button", { name: "Correct Claim ID" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Correct Billing NPI" }));
    expect(onCorrect).toHaveBeenCalledWith("billing_npi");
    expect(screen.getByText(/2 boxes were read with low confidence/)).toBeInTheDocument();
  });

  it("has no Correct buttons once the claim is processed", () => {
    render(<FormFields form={{ ...FORM, correctable: false }} onCorrect={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /^Correct / })).not.toBeInTheDocument();
  });

  it("hints how the form prints each kind of box", () => {
    expect(formatHint("service_lines.0.date_of_service")).toMatch(/MM\/DD\/YYYY/);
    expect(formatHint("diagnoses.2")).toMatch(/M54\.5/);
    expect(formatHint("service_lines.1.charge_cents")).toMatch(/132\.00/);
    expect(formatHint("other_coverage.primary_paid.0")).toMatch(/Line 1: 40\.00/);
  });
});

describe("a correction in the audit trail", () => {
  const event = (fields: unknown[]): AuditEvent => ({
    id: 1,
    event_type: "FIELD_CORRECTED",
    actor: "provider1",
    payload: { fields },
    created_at: "2026-10-15T10:00:00Z",
  });

  it("shows each box with its text before and after, but never a patient's", () => {
    expect(
      corrections(
        event([
          { field: "billing_npi", confidence_before: 0.41, before: "1234567890", after: "1234567893" },
          { field: "patient.address.city", confidence_before: 0.6 },
        ]),
      ),
    ).toEqual(["Billing NPI: 1234567890 → 1234567893", "Patient · Address · City (patient detail, not shown)"]);
  });
});
