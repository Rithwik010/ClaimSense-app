// The demo runbook (docs/DEMO.md), clicked by a script with video on: the backup recording.
// Runs only with DEMO_VIDEO=1 (make demo-video), right after `make demo-reset`, with `make demo`
// running. The pauses are for the viewer.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const DIR = fileURLToPath(new URL("../../demo/claims/", import.meta.url));

test.use({ viewport: { width: 1440, height: 900 }, video: { mode: "on", size: { width: 1440, height: 900 } } });
test.setTimeout(600_000);

const pause = (page: Page, ms = 1500) => page.waitForTimeout(ms);
const nav = (page: Page, name: string) =>
  page.locator('[data-slot="sidebar-menu-button"]').filter({ hasText: name }).click();

async function read(page: Page, file: string) {
  await nav(page, "Submit claim");
  await page.getByLabel("Claim file").setInputFiles({
    name: file,
    mimeType: file.endsWith(".pdf") ? "application/pdf" : "application/json",
    buffer: readFileSync(DIR + file),
  });
  await pause(page, 600);
  await page.getByRole("button", { name: "Read claim" }).click();
}

async function processClaim(page: Page, claimId: string) {
  await expect(page.getByText(`Claim ${claimId} was filed from`)).toBeVisible({ timeout: 60_000 });
  await pause(page);
  await page.getByRole("button", { name: "Process claim" }).click();
  await expect(page).toHaveURL(new RegExp(`/claims/${claimId}$`), { timeout: 120_000 });
  await pause(page, 2500); // the stage strip fills in
}

async function finalize(page: Page) {
  await page.getByRole("button", { name: /Accept recommendation|Finalize claim/ }).click();
  await pause(page, 1000);
  await page.getByRole("dialog").getByRole("button", { name: "Finalize claim" }).click();
  await pause(page, 2500);
}

test("demo runbook", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("claimsense.role", "reviewer");
    localStorage.setItem("claimsense.reviewerId", "reviewer-demo");
  });
  await page.goto("/submit");
  await pause(page);

  // 1. A clean claim, end to end.
  await read(page, "01-approve-quick.json");
  await processClaim(page, "CLM-DEMO-01");
  await page.getByRole("link", { name: "Review claim" }).click();
  await pause(page);
  const quote = page.getByRole("button", { name: /Met/ }).first();
  if (await quote.count()) {
    await quote.click();
    await pause(page, 2000);
  }
  await finalize(page);

  // 2. The model denies, the reviewer overrides.
  await read(page, "03-deny-full-override.json");
  await processClaim(page, "CLM-DEMO-03");
  await page.getByRole("link", { name: "Review claim" }).click();
  await pause(page, 2500);
  await page.getByRole("button", { name: "Override line" }).first().click();
  await page.getByLabel("New decision for line 1").click();
  await page.getByRole("option", { name: /^Approve/ }).click();
  await page.getByLabel("Reason (required)").pressSequentially("The note documents the criterion.", { delay: 30 });
  await pause(page, 800);
  await page.getByRole("dialog").getByRole("button", { name: "Override line" }).click();
  await pause(page);
  await finalize(page);

  // 3. Rules decide on their own.
  await read(page, "04-partial-ncci.json");
  await processClaim(page, "CLM-DEMO-04");
  await page.getByRole("link", { name: "Review claim" }).click();
  await pause(page, 2500);
  await finalize(page);
  await read(page, "05-rule-deny-r15.json");
  await processClaim(page, "CLM-DEMO-05");
  await read(page, "06-reject-invalid-npi.json");
  await pause(page, 2500);
  await read(page, "07-duplicate-of-01.json");
  await processClaim(page, "CLM-DEMO-07");
  await nav(page, "Rule outcomes");
  await pause(page, 2500);

  // 4. Scanned forms.
  await read(page, "08-scanned-clean.pdf");
  await processClaim(page, "CLM-DEMO-08");
  await read(page, "09-scanned-low-confidence.pdf");
  await expect(page.getByText("Claim CLM-DEMO-09 was filed from")).toBeVisible({ timeout: 60_000 });
  await page.getByText("Low").first().scrollIntoViewIfNeeded();
  await pause(page, 2500);
  await page.getByRole("button", { name: "Process claim" }).click();
  await expect(page).toHaveURL(/\/claims\/CLM-DEMO-09$/, { timeout: 120_000 });
  await page.getByRole("tab", { name: "Rule checks" }).click();
  await pause(page, 2500);

  // 5. Explanation and evidence.
  await page.goto("/claims/CLM-DEMO-03");
  await page.getByRole("tab", { name: "Explanation" }).click();
  await pause(page, 3000);
  await page.getByRole("tab", { name: "Audit trail" }).click();
  await pause(page, 2000);

  // 6. How good is it.
  await nav(page, "Metrics");
  await pause(page, 2000);
  await page.getByRole("heading", { name: "Where v2 goes wrong" }).scrollIntoViewIfNeeded();
  await pause(page, 3000);
});
