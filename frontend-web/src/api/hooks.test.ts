import { describe, expect, it } from "vitest";

import { intakeRequest } from "./hooks";

describe("where a claim file goes", () => {
  it("sends a JSON claim to POST /v1/claims/intake as its own text, kept as sent", async () => {
    const text = '{\n  "claim_id": "CLM-1"\n}';
    const file = new File([text], "claim.json", { type: "application/json" });

    await expect(intakeRequest(file)).resolves.toEqual({ path: "/v1/claims/intake", text });
  });

  it("recognises a .json file without a content type", async () => {
    const file = new File(['{"claim_id": "CLM-2"}'], "CLAIM.JSON");

    expect((await intakeRequest(file)).path).toBe("/v1/claims/intake");
  });

  it("sends a PDF, a scan, or JSON that does not parse to POST /v1/claims/intake/file", async () => {
    for (const file of [
      new File(["%PDF-1.4"], "claim.pdf", { type: "application/pdf" }),
      new File(["x"], "scan.png", { type: "image/png" }),
      new File(["{not json"], "broken.json", { type: "application/json" }),
    ]) {
      await expect(intakeRequest(file)).resolves.toEqual({ path: "/v1/claims/intake/file" });
    }
  });
});
