// Every demo claim (demo/claims/, demo plan item 8) through the React UI, in order, on a database
// fresh from `make demo-reset` with `make demo-up` running. Each claim is filed and processed by its
// provider (D-AUTH-1), who sees it "In review" or final on My claims; reviewer1 then takes it down
// its path. The API is read only to check what the screen cannot show (accumulators and visit usage
// in the FINALIZED audit event), with the logged-in reviewer's session.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { FILED_BY, loginAs } from "./session";

const DIR = fileURLToPath(new URL("../../demo/claims/", import.meta.url));

test.describe.configure({ mode: "serial" });
test.setTimeout(180_000);

/** File and process a claim as its provider; returns its row on My claims. */
async function submit(page: Page, file: string, claimId: string) {
  await loginAs(page, FILED_BY[file]!);
  await page.goto("/submit");
  const isPdf = file.endsWith(".pdf");
  await page.getByLabel("Claim file").setInputFiles({
    name: file,
    mimeType: isPdf ? "application/pdf" : "application/json",
    buffer: readFileSync(DIR + file),
  });
  await page.getByRole("button", { name: "Read claim" }).click();
  await expect(page.getByText(`Claim ${claimId} was filed from`)).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Process claim" }).click();
  await expect(page).toHaveURL(/\/my-claims$/, { timeout: 120_000 });
  return page.getByRole("row", { name: new RegExp(claimId) });
}

/** Open a claim as reviewer1. */
async function asReviewer(page: Page, claimId: string) {
  await loginAs(page, "reviewer1");
  await page.goto(`/claims/${claimId}`);
  await expect(page.getByRole("heading", { name: `Claim ${claimId}` })).toBeVisible();
}

async function finalize(page: Page, claimId: string) {
  await page.getByRole("link", { name: "Review claim" }).click();
  await expect(page.getByRole("heading", { name: `Review claim ${claimId}` })).toBeVisible();
}

test("01 clean approve: quick tier, accepted, accumulators and visit usage change", async ({ page }) => {
  const row = await submit(page, "01-approve-quick.json", "CLM-DEMO-01");
  await expect(row.getByText("In review")).toBeVisible();
  await asReviewer(page, "CLM-DEMO-01");
  await expect(page.getByText("Waiting, quick tier")).toBeVisible();
  await finalize(page, "CLM-DEMO-01");
  await page.getByRole("button", { name: "Accept recommendation" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Finalize claim" }).click();
  await expect(page.getByText("Claim CLM-DEMO-01 is final")).toBeVisible();
  const events = (await (await page.request.get("/v1/claims/CLM-DEMO-01/audit")).json()) as {
    event_type: string;
    payload: Record<string, unknown>;
  }[];
  const finalized = events.find((e) => e.event_type === "FINALIZED")!;
  const visits = finalized.payload.visit_usage as Record<string, { before: number; after: number }>;
  expect(visits.REHAB_THERAPY!.after).toBe(visits.REHAB_THERAPY!.before + 1);
  const accumulators = finalized.payload.accumulators as { before: unknown; after: unknown };
  expect(accumulators.after).not.toEqual(accumulators.before);
  await loginAs(page, "provider1");
  await expect(page.getByRole("row", { name: /CLM-DEMO-01/ }).getByText("Approved")).toBeVisible();
});

test("02 model pend: standard tier", async ({ page }) => {
  const row = await submit(page, "02-pend-standard.json", "CLM-DEMO-02");
  await expect(row.getByText("In review")).toBeVisible();
  await asReviewer(page, "CLM-DEMO-02");
  await expect(page.getByText("Waiting, standard tier")).toBeVisible();
});

test("03 model deny: full tier, a line overridden with a reason, amounts recomputed", async ({ page }) => {
  await submit(page, "03-deny-full-override.json", "CLM-DEMO-03");
  await asReviewer(page, "CLM-DEMO-03");
  await expect(page.getByText("Waiting, full tier")).toBeVisible();
  await finalize(page, "CLM-DEMO-03");
  await page.getByRole("button", { name: "Override line" }).first().click();
  await page.getByLabel("New decision for line 1").click();
  await page.getByRole("option", { name: /^Approve/ }).click();
  await page.getByLabel("Reason (required)").fill("The note documents the criterion; approved on review.");
  await page.getByRole("dialog").getByRole("button", { name: "Override line" }).click();
  await page.getByRole("button", { name: "Finalize claim" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Finalize claim" }).click();
  await expect(page.getByText("Claim CLM-DEMO-03 is final")).toBeVisible();
  await expect(page.getByRole("status").getByText("Approved", { exact: true })).toBeVisible();
});

test("04 partial: a rule denies one line, the model approves the other", async ({ page }) => {
  await submit(page, "04-partial-ncci.json", "CLM-DEMO-04");
  await asReviewer(page, "CLM-DEMO-04");
  await finalize(page, "CLM-DEMO-04");
  await expect(page.getByText("Decided by a rule. Rule outcomes are automatic and cannot be overridden.")).toBeVisible();
  await page.getByRole("button", { name: "Accept recommendation" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Finalize claim" }).click();
  await expect(page.getByRole("status").getByText("Partly approved", { exact: true })).toBeVisible();
});

test("05 every line denied by R15: denied by a rule, read-only", async ({ page }) => {
  const row = await submit(page, "05-rule-deny-r15.json", "CLM-DEMO-05");
  await expect(row.getByText("Denied by a rule")).toBeVisible(); // final at once
  await asReviewer(page, "CLM-DEMO-05");
  await expect(page.getByText("Denied by a rule").first()).toBeVisible();
  await expect(page.getByText("Not reached: rule outcomes are final")).toBeVisible();
  await page.goto("/rule-outcomes");
  await expect(page.getByRole("link", { name: "CLM-DEMO-05" })).toBeVisible();
});

test("06 invalid NPI: rejected", async ({ page }) => {
  const row = await submit(page, "06-reject-invalid-npi.json", "CLM-DEMO-06");
  await expect(row.getByText("Rejected")).toBeVisible();
});

test("07 duplicate of 01: rejected as a duplicate", async ({ page }) => {
  const row = await submit(page, "07-duplicate-of-01.json", "CLM-DEMO-07");
  await expect(row.getByText("Rejected")).toBeVisible();
  await asReviewer(page, "CLM-DEMO-07");
  await page.getByRole("tab", { name: "Rule checks" }).click();
  await expect(page.getByText("RJ_DUPLICATE").first()).toBeVisible();
});

test("08 clean scanned form: read by OCR and decided", async ({ page }) => {
  const row = await submit(page, "08-scanned-clean.pdf", "CLM-DEMO-08");
  await expect(row.getByText("In review")).toBeVisible();
  await asReviewer(page, "CLM-DEMO-08");
  await expect(page.getByText("Scanned form").first()).toBeVisible();
  await expect(page.getByText("Awaiting review").first()).toBeVisible();
});

test("09 scanned form with a mistyped NPI: rejected for a low-confidence field", async ({ page }) => {
  const row = await submit(page, "09-scanned-low-confidence.pdf", "CLM-DEMO-09");
  await expect(row.getByText("Rejected")).toBeVisible();
  await asReviewer(page, "CLM-DEMO-09");
  await page.getByRole("tab", { name: "Rule checks" }).click();
  await expect(page.getByText("RJ_LOW_CONFIDENCE_FIELD").first()).toBeVisible();
});

test("roles: another provider's claim and another role's page are out of reach", async ({ page }) => {
  await loginAs(page, "provider2");
  await expect(page.getByRole("row", { name: /CLM-DEMO-01/ })).toHaveCount(0);
  await page.goto("/claims/CLM-DEMO-01");
  await expect(page.getByText("You don't have access")).toBeVisible();
  await loginAs(page, "admin");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await page.goto("/review/CLM-DEMO-08");
  await expect(page.getByText("You don't have access")).toBeVisible();
  await page.getByRole("button", { name: /open the user menu/ }).click();
  await page.getByRole("menuitem", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
});
