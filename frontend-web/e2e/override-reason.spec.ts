// The override sheet's reason (D-REV-9), with the API mocked (e2e/mock-review.ts): no running stack
// and no database. A line changed to Deny cannot be saved without a reason from the list; once
// chosen, the review sends the reason code with the reviewer's note.

import { expect, test } from "@playwright/test";

import { CLAIM_ID, mockApi } from "./mock-review";

test("a line changed to deny cannot be saved without a reason; the reason code is sent", async ({ page }) => {
  const { sent } = await mockApi(page);
  await page.goto(`/review/${CLAIM_ID}`);
  await expect(page.getByRole("heading", { name: `Review claim ${CLAIM_ID}` })).toBeVisible();

  await page.getByRole("button", { name: "Override line" }).first().click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByRole("heading", { name: "Override line 1" })).toBeVisible();
  await sheet.getByLabel("New decision for line 1").click();
  await page.getByRole("option", { name: /^Deny/ }).click();
  await sheet.getByLabel("Note (required)").fill("Repeat scan within 30 days, no change in symptoms.");

  // No reason chosen: the sheet stays open and says what is missing.
  await sheet.getByRole("button", { name: "Override line" }).click();
  await expect(sheet.getByText("Choose a reason for line 1.")).toBeVisible();
  await expect(sheet.getByLabel("Reason (required)")).toHaveAttribute("aria-invalid", "true");
  await expect(sheet).toBeVisible();

  await sheet.getByLabel("Reason (required)").click();
  await page
    .getByRole("option", { name: "Not medically necessary under the coverage criteria (DN_NOT_MEDICALLY_NECESSARY)" })
    .click();
  await sheet.getByRole("button", { name: "Override line" }).click();
  await expect(sheet).toBeHidden();

  await page.getByRole("button", { name: "Finalize claim" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Finalize claim" }).click();
  await expect(page.getByText(`Claim ${CLAIM_ID} is final`)).toBeVisible();
  expect(sent).toHaveLength(1);
  expect((sent[0] as { line_overrides: unknown[] }).line_overrides).toEqual([
    {
      line_no: 1,
      decision: "DENY",
      reason: "Repeat scan within 30 days, no change in symptoms.",
      reason_code: "DN_NOT_MEDICALLY_NECESSARY",
    },
  ]);
});
