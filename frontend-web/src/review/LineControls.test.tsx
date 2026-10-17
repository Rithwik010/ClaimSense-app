import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { OverrideForm } from "../pages/ReviewClaim";
import { check, type LineState } from "./form";

const LINE: LineState = {
  lineNo: 1,
  editable: true,
  original: { decision: "APPROVE", category: "PHYSICAL_THERAPY" },
  candidates: ["PHYSICAL_THERAPY", "CHIROPRACTIC"],
  decision: "DENY",
  category: "PHYSICAL_THERAPY",
  reasonCode: "DN_NOT_MEDICALLY_NECESSARY",
  reason: "",
};

function Harness({ start }: { start: LineState }) {
  const [line, setLine] = useState(start);
  const checked = check([line]);
  return <OverrideForm line={line} error={checked.errors[1]} field={checked.fields[1]} onChange={setLine} />;
}

describe("override form", () => {
  it("labels every input and asks for a note", async () => {
    const user = userEvent.setup();
    render(<Harness start={LINE} />);

    expect(screen.getByLabelText("New decision for line 1")).toBeInTheDocument();
    expect(screen.queryByLabelText("Benefit category")).not.toBeInTheDocument(); // not approved
    expect(screen.getByLabelText("Reason (required)")).toHaveTextContent(
      "Not medically necessary under the coverage criteria (DN_NOT_MEDICALLY_NECESSARY)",
    );
    expect(screen.getByText("Write a note for changing line 1.")).toBeInTheDocument();
    expect(screen.getByLabelText("Note (required)")).toHaveAttribute("aria-invalid", "true");

    await user.type(screen.getByLabelText("Note (required)"), "Not medically necessary.");
    expect(screen.queryByText("Write a note for changing line 1.")).not.toBeInTheDocument();
  });

  it("asks for a reason code first on a line changed to deny or pend", () => {
    render(<Harness start={{ ...LINE, reasonCode: null, reason: "Repeat test this month." }} />);

    expect(screen.getByText("Choose a reason for line 1.")).toBeInTheDocument();
    expect(screen.getByLabelText("Reason (required)")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Note (required)")).toHaveAttribute("aria-invalid", "false");
  });

  it("shows no reason choice for an approved line", () => {
    render(<Harness start={{ ...LINE, decision: "APPROVE", reasonCode: null, reason: "Covered." }} />);

    expect(screen.queryByLabelText("Reason (required)")).not.toBeInTheDocument();
  });

  it("asks for the benefit category only on an approved line with several", () => {
    render(
      <Harness start={{ ...LINE, decision: "APPROVE", category: null, reasonCode: null, reason: "Billed by a chiropractor." }} />,
    );

    expect(screen.getByLabelText("Benefit category")).toBeInTheDocument();
    expect(screen.getByText("Choose a benefit category for line 1.")).toBeInTheDocument();
  });
});
