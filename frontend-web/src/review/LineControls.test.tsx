import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { LineControls } from "../pages/ReviewClaim";
import { check, type LineState } from "./form";

const LINE: LineState = {
  lineNo: 1,
  editable: true,
  original: { decision: "APPROVE", category: "PHYSICAL_THERAPY" },
  candidates: ["PHYSICAL_THERAPY", "CHIROPRACTIC"],
  decision: "APPROVE",
  category: "PHYSICAL_THERAPY",
  reason: "",
};

function Harness() {
  const [line, setLine] = useState(LINE);
  const error = check([line]).errors[1];
  return <LineControls line={line} error={error} onChange={setLine} />;
}

describe("line controls", () => {
  it("label every input and show the category only while the line is approved", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    expect(screen.getByLabelText(/Benefit category/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/Your decision for line 1/), "DENY");

    expect(screen.queryByLabelText(/Benefit category/)).not.toBeInTheDocument();
    expect(screen.getByText("Give a reason for changing line 1.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Reason \(required\)/)).toHaveAttribute("aria-invalid", "true");

    await user.type(screen.getByLabelText(/Reason/), "Not medically necessary.");
    expect(screen.queryByText("Give a reason for changing line 1.")).not.toBeInTheDocument();
  });
});
