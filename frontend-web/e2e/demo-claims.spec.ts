// Every demo claim (demo/claims/) through the web app, in order, on a database fresh from `make
// demo-reset` with `make demo-up` running, logged in as each role (D-AUTH-1). A provider drops the
// file on Submit claim, processes it (the stage strip fills in) and opens the claim result; reviewer1
// reviews from the queue; the admin reads the overview, the model metrics, an audit trail and the
// system status. The API is read only for what the screen cannot show (the FINALIZED audit event).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { FILED_BY, loginAs } from "./session";

const DIR = fileURLToPath(new URL("../../demo/claims/", import.meta.url));

test.describe.configure({ mode: "serial" });
test.setTimeout(180_000);

/** File and process a claim as its provider; leaves the page on the claim result. */
async function submit(page: Page, file: string, claimId: string, expected: RegExp) {
  await loginAs(page, FILED_BY[file]!);
  await page.goto("/submit");
  await page.getByLabel("Claim file").setInputFiles({
    name: file,
    mimeType: file.endsWith(".pdf") ? "application/pdf" : "application/json",
    buffer: readFileSync(DIR + file),
  });
  await page.getByRole("button", { name: "Read claim" }).click();
  await expect(page.getByText(`Claim ${claimId} was filed from`)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("heading", { name: "Fields read" })).toBeVisible();
  await page.getByRole("button", { name: "Process claim" }).click();
  const result = page.getByRole("region", { name: "Result" });
  await expect(result.getByRole("list", { name: "Pipeline stages" })).toBeVisible({ timeout: 120_000 });
  await expect(result.getByText(expected).first()).toBeVisible();
  await page.getByRole("link", { name: "Open claim result" }).click();
  await expect(page.getByRole("heading", { name: `Claim ${claimId}` })).toBeVisible();
}

/** Open a claim from the review queue as reviewer1, from whichever tier's tab holds it. */
async function review(page: Page, claimId: string) {
  await loginAs(page, "reviewer1");
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  for (const tier of ["Full", "Standard", "Quick"]) {
    await page.getByRole("tab", { name: new RegExp(`^${tier} \\(`) }).click();
    if (await page.getByRole("link", { name: claimId }).isVisible()) break;
  }
  await page.getByRole("link", { name: claimId }).click();
  await expect(page.getByRole("heading", { name: `Review claim ${claimId}` })).toBeVisible();
}

async function finalize(page: Page, claimId: string) {
  await page.getByRole("dialog").getByRole("button", { name: "Finalize claim" }).click();
  await expect(page.getByText(`Claim ${claimId} is final`)).toBeVisible();
  await expect(page.getByText(`Claim ${claimId}.`, { exact: true })).toBeVisible(); // the toast
}

test("01 clean approve: in review for the provider, accepted by reviewer1, then approved", async ({ page }) => {
  await submit(page, "01-approve-quick.json", "CLM-DEMO-01", /In review/);
  await expect(page.getByText(/In review\. A reviewer is checking/)).toBeVisible();
  await expect(page.getByText("Waiting for a reviewer")).toBeVisible();

  await review(page, "CLM-DEMO-01");
  await page.getByRole("button", { name: "Accept all lines" }).click();
  await finalize(page, "CLM-DEMO-01");
  const events = (await (await page.request.get("/v1/claims/CLM-DEMO-01/audit")).json()) as {
    event_type: string;
    payload: Record<string, unknown>;
  }[];
  const finalized = events.find((e) => e.event_type === "FINALIZED")!;
  const visits = finalized.payload.visit_usage as Record<string, { before: number; after: number }>;
  expect(visits.REHAB_THERAPY!.after).toBe(visits.REHAB_THERAPY!.before + 1);

  await loginAs(page, "provider1");
  await page.getByRole("link", { name: "CLM-DEMO-01" }).click();
  await expect(page.getByRole("region", { name: "Lines", exact: true })).toBeVisible();
  await expect(page.getByText("Covered under the plan's benefits.")).toBeVisible();
  for (const label of ["Billed", "Allowed", "Plan pays", "Member pays"]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByTestId("explanation").getByRole("heading", { name: "Summary" })).toBeVisible();
});

test("02 model pend: filed now, reviewed once claim 3 waits too", async ({ page }) => {
  await submit(page, "02-pend-standard.json", "CLM-DEMO-02", /In review/);
});

test("03 model deny: after accepting claim 2, Next claim opens it; a line overridden with a reason", async ({ page }) => {
  await submit(page, "03-deny-full-override.json", "CLM-DEMO-03", /In review/);
  await review(page, "CLM-DEMO-02");
  await expect(page.getByText("Standard review tier")).toBeVisible();
  await page.getByRole("button", { name: "Accept all lines" }).click();
  await finalize(page, "CLM-DEMO-02");
  await expect(page.getByRole("status").getByText("Needs information", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Next claim" }).click();

  await expect(page.getByRole("heading", { name: "Review claim CLM-DEMO-03" })).toBeVisible();
  await expect(page.getByText("Full review tier")).toBeVisible();
  await page.getByRole("button", { name: "Override line" }).first().click();
  await page.getByLabel("New decision for line 1").click();
  await page.getByRole("option", { name: /^Approve/ }).click();
  await page.getByLabel("Reason (required)").fill("The note documents the criterion; approved on review.");
  await page.getByRole("dialog").getByRole("button", { name: "Override line" }).click();
  await page.getByRole("button", { name: "Finalize claim" }).click();
  await finalize(page, "CLM-DEMO-03");
  await expect(page.getByRole("status").getByText("Approved", { exact: true })).toBeVisible();
});

test("04 partial: a rule denies one line with its CARC, the model approves the other", async ({ page }) => {
  await submit(page, "04-partial-ncci.json", "CLM-DEMO-04", /In review/);
  await review(page, "CLM-DEMO-04");
  await expect(page.getByText("Decided by a rule. Rule outcomes are automatic and cannot be overridden.")).toBeVisible();
  await expect(page.getByText("CARC 236").first()).toBeVisible();
  await page.getByRole("button", { name: "Accept all lines" }).click();
  await finalize(page, "CLM-DEMO-04");
  await expect(page.getByRole("status").getByText("Partly approved", { exact: true })).toBeVisible();
});

test("05 every line denied by R15: final at once, with CARC 11, RARC N115, the article and its LCD", async ({ page }) => {
  await submit(page, "05-rule-deny-r15.json", "CLM-DEMO-05", /Denied by a rule/);
  await expect(page.getByText("CARC 11").first()).toBeVisible();
  await expect(page.getByText("RARC N115").first()).toBeVisible();
  await expect(page.getByText(/Billing article A\d+; related LCD L\d+/).first()).toBeVisible();
});

test("06 invalid NPI: rejected with CARC 16 and RARC N257", async ({ page }) => {
  await submit(page, "06-reject-invalid-npi.json", "CLM-DEMO-06", /Rejected/);
  await expect(page.getByText("CARC 16").first()).toBeVisible();
  await expect(page.getByText("RARC N257").first()).toBeVisible();
});

test("07 duplicate of 01: rejected as a duplicate with CARC 18", async ({ page }) => {
  await submit(page, "07-duplicate-of-01.json", "CLM-DEMO-07", /Rejected/);
  await expect(page.getByText("CARC 18").first()).toBeVisible();
});

test("08 clean scanned form: read by OCR, in review", async ({ page }) => {
  await submit(page, "08-scanned-clean.pdf", "CLM-DEMO-08", /In review/);
  await expect(page.getByText("Scanned form").first()).toBeVisible();
});

test("09 scanned form with a mistyped NPI: rejected for a low-confidence field", async ({ page }) => {
  await submit(page, "09-scanned-low-confidence.pdf", "CLM-DEMO-09", /Rejected/);
  await expect(page.getByText("RARC MA130").first()).toBeVisible();
});

test("reviewer: rule outcomes with codes, a claim's explanation and audit trail", async ({ page }) => {
  await loginAs(page, "reviewer1");
  await page.goto("/rule-outcomes");
  for (const id of ["CLM-DEMO-05", "CLM-DEMO-06", "CLM-DEMO-07", "CLM-DEMO-09"]) {
    await expect(page.getByRole("link", { name: id })).toBeVisible();
  }
  await expect(page.getByText("CARC 18").first()).toBeVisible();
  await page.goto("/claims/CLM-DEMO-03");
  await page.getByRole("tab", { name: "Explanation" }).click();
  await expect(page.getByTestId("explanation").getByText("reviewer1").first()).toBeVisible();
  await page.getByRole("tab", { name: "Audit trail" }).click();
  const trail = page.getByRole("list", { name: "Audit trail" });
  await expect(trail.getByText("Lines overridden")).toBeVisible();
  await expect(trail.getByText(/by reviewer1/).first()).toBeVisible();
  await expect(trail.getByText(/rules \d/).first()).toBeVisible();
});

test("provider: my claims, searched and filtered", async ({ page }) => {
  await loginAs(page, "provider2");
  await expect(page.getByRole("heading", { name: "My claims" })).toBeVisible();
  await expect(page.getByRole("link", { name: "CLM-DEMO-01" })).toHaveCount(0); // provider1's
  await page.getByLabel("Search by claim ID").fill("DEMO-08");
  await expect(page.getByRole("link", { name: "CLM-DEMO-08" })).toBeVisible();
  await expect(page.getByRole("link", { name: "CLM-DEMO-05" })).toHaveCount(0);
  await page.getByLabel("Search by claim ID").fill("");
  await page.getByLabel("Status").click();
  await page.getByRole("option", { name: "Rejected" }).click();
  await expect(page.getByRole("link", { name: "CLM-DEMO-06" })).toBeVisible();
  await expect(page.getByRole("link", { name: "CLM-DEMO-08" })).toHaveCount(0);
});

test("admin: overview, model metrics, audit lookup and system status, read-only", async ({ page }) => {
  await loginAs(page, "admin");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("Demo data")).toBeVisible();
  await expect(page.getByRole("region", { name: "Review queue by tier" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Reviewed claims" }).getByText("Lines overridden")).toBeVisible();

  await page.goto("/metrics");
  await expect(page.getByRole("heading", { name: "Side by side" })).toBeVisible();
  for (const model of ["Model v1", "Model v2", "Model E4B"]) {
    await expect(page.getByRole("columnheader", { name: model })).toBeVisible();
  }
  await expect(page.getByText("not measured").first()).toBeVisible();
  await expect(page.getByText(/^not applicable/)).toBeVisible();

  await page.goto("/audit");
  await page.getByLabel("Claim ID").fill("CLM-DEMO-03");
  await page.getByRole("button", { name: "Show audit trail" }).click();
  await expect(page.getByRole("list", { name: "Audit trail" }).getByText("Finalized")).toBeVisible();

  await page.goto("/system");
  await expect(page.getByText("Reachable", { exact: true })).toHaveCount(3);
  await expect(page.getByText("claimsense-decision:v2").first()).toBeVisible();

  await page.goto("/queue");
  await expect(page.getByText("Read only.", { exact: false })).toBeVisible();
  await page.goto("/claims/CLM-DEMO-08");
  await expect(page.getByRole("link", { name: "Review claim" })).toHaveCount(0);
});

test("roles: another provider's claim and another role's page are out of reach", async ({ page }) => {
  await loginAs(page, "provider2");
  await page.goto("/my-claims/CLM-DEMO-01");
  await expect(page.getByText("Not found: claim CLM-DEMO-01 not found")).toBeVisible();
  for (const [user, path] of [
    ["provider2", "/claims/CLM-DEMO-01"],
    ["provider1", "/queue"],
    ["reviewer1", "/metrics"],
    ["reviewer1", "/submit"],
    ["admin", "/review/CLM-DEMO-08"],
    ["admin", "/my-claims"],
  ] as const) {
    await loginAs(page, user);
    await page.goto(path);
    await expect(page.getByText("You don't have access"), `${user} ${path}`).toBeVisible();
  }
  await page.getByRole("button", { name: /open the user menu/ }).click();
  await page.getByRole("menuitem", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
});
