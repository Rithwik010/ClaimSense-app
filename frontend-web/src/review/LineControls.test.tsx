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
  reason: "",
};

function Harness({ start }: { start: LineState }) {
  const [line, setLine] = useState(start);
  return <OverrideForm line={line} error={check([line]).errors[1]} onChange={setLine} />;
}

describe("override form", () => {
  it("labels every input and asks for a reason", async () => {
    const user = userEvent.setup();
    render(<Harness start={LINE} />);

    expect(screen.getByLabelText("New decision for line 1")).toBeInTheDocument();
    expect(screen.queryByLabelText("Benefit category")).not.toBeInTheDocument(); // not approved
    expect(screen.getByText("Give a reason for changing line 1.")).toBeInTheDocument();
    expect(screen.getByLabelText("Reason (required)")).toHaveAttribute("aria-invalid", "true");

    await user.type(screen.getByLabelText("Reason (required)"), "Not medically necessary.");
    expect(screen.queryByText("Give a reason for changing line 1.")).not.toBeInTheDocument();
  });

  it("asks for the benefit category only on an approved line with several", () => {
    render(<Harness start={{ ...LINE, decision: "APPROVE", category: null, reason: "Billed by a chiropractor." }} />);

    expect(screen.getByLabelText("Benefit category")).toBeInTheDocument();
    expect(screen.getByText("Choose a benefit category for line 1.")).toBeInTheDocument();
  });
});
