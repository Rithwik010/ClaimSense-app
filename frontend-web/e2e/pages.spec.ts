// The team's UI changes (D-UI-6, D-DOC-1), run after e2e/demo-claims.spec.ts on its claims (CLM-DEMO-08
// still waits for review): the provider's plain-words explanation and billing, the reviewer and admin
// Claims pages' search and filters, the Reason column, the renamed "Returned and auto-denied" page,
// the original file in a side sheet and a new tab (JSON, PDF and an image filed here), and the claim
// page's Summary, Clinical note and Audit trail tabs. Every page checked here has no serious or
// critical axe violation; tabs, the sheet and the filters are used by keyboard; one run with reduced
// motion. Nothing is saved: no screenshots.

import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { loginAs } from "./session";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
// What a provider page never shows: rule IDs, internal reason codes and criterion IDs.
const HIDDEN = /\bR(?:0[1-9]|1\d|20)\b|\bDUP\b|\b(?:RJ|DN|PD|RV)_[A-Z0-9_]+\b|\bMODEL_OUTPUT_INVALID\b|\bPOL-[A-Z]+-\d{3}\.c\d+\b/;
const LABELS: Record<string, string> = {
  NOT_PROCESSED: "Not processed",
  IN_REVIEW: "In review",
  APPROVED: "Approved",
  PARTLY_APPROVED: "Partly approved",
  PENDED: "Pended",
  DENIED: "Denied",
  REJECTED: "Rejected",
};
const IMAGE_CLAIM = `CLM-IMG-${String(Date.now()).slice(-6)}`; // digits: the OCR reads them reliably

test.describe.configure({ mode: "serial" });
test.setTimeout(120_000);

/** No serious or critical axe violation on the page, or inside `scope` (an open modal sheet: the
 * page behind it is inert and dimmed, so only the sheet is checked). */
async function axeClean(page: Page, what: string, scope?: string) {
  // Colours are checked at rest: after the page's fade-in and any other running animation.
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every((a) => a.playState !== "running" || a.effect?.getTiming().iterations === Infinity),
  );
  await page.waitForTimeout(250);
  const builder = new AxeBuilder({ page });
  const results = await (scope ? builder.include(scope) : builder).analyze();
  const bad = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).join("; ")}`);
  expect(bad, `${what}: serious or critical axe violations`).toEqual([]);
}

async function shownClaims(page: Page): Promise<string[]> {
  return (await page.getByRole("table").getByRole("link").allTextContents()).sort();
}

async function chooseStatus(page: Page, label: string) {
  await page.getByLabel("Status").click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

async function providerPageText(page: Page): Promise<string> {
  return page.getByRole("main").innerText();
}

test("provider: a rejected claim in plain words, what to check and its codes, no rule IDs", async ({ page }) => {
  await loginAs(page, "provider2");
  await page.goto("/my-claims/CLM-DEMO-06");
  await expect(page.getByRole("heading", { name: "Claim rejected" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Why" })).toContainText("is not a valid NPI");
  const check = page.getByRole("region", { name: "Please review the following details" });
  await expect(check).toContainText("(not a valid NPI)");
  await expect(page.getByText("CARC 16")).toBeVisible();
  expect(await providerPageText(page)).not.toMatch(HIDDEN);
  await axeClean(page, "provider rejected claim");

  await page.goto("/my-claims/CLM-DEMO-09");
  await expect(page.getByRole("heading", { name: "Claim rejected" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Please review the following details" })).toContainText(
    "could not be read",
  );
  expect(await providerPageText(page)).not.toMatch(HIDDEN);
});

test("provider: a paid claim shows its billing with a sentence for each reduction", async ({ page }) => {
  await loginAs(page, "provider1");
  await page.goto("/my-claims/CLM-DEMO-01");
  await expect(page.getByRole("heading", { name: "Claim approved" })).toBeVisible();
  const billing = page.getByRole("table", { name: "Billing" });
  await expect(billing.getByText("to the plan's allowed amount for this service")).toBeVisible();
  await expect(billing.getByRole("row", { name: /^Total/ })).toBeVisible();
  expect(await providerPageText(page)).not.toMatch(HIDDEN);
  await axeClean(page, "provider approved claim");

  await loginAs(page, "provider2");
  await page.goto("/my-claims/CLM-DEMO-04");
  await expect(page.getByRole("heading", { name: "Claim partly approved" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Why" })).toContainText("Line 2:");
  await expect(page.getByRole("table", { name: "Billing" }).getByText(/^Not paid:/)).toBeVisible();
  expect(await providerPageText(page)).not.toMatch(HIDDEN);
});

test("reviewer: the Claims page searches and filters, kept in the URL", async ({ page }) => {
  await loginAs(page, "reviewer1");
  const listed = (await (await page.request.get("/v1/claims")).json()) as {
    claim_id: string;
    member_id: string;
    provider_npi: string | null;
    provider_name: string | null;
    outcome: string;
  }[];
  await page.goto("/claims");
  await expect(page.getByText(`${listed.length} claims`)).toBeVisible();

  const search = page.getByLabel("Search claims");
  await search.fill("demo-06");
  await expect(page.getByText("1 claim", { exact: true })).toBeVisible();
  await expect.poll(() => shownClaims(page)).toEqual(["CLM-DEMO-06"]);
  await expect(page).toHaveURL(/q=demo-06/);
  await page.reload();
  await expect(search).toHaveValue("demo-06");
  await expect.poll(() => shownClaims(page)).toEqual(["CLM-DEMO-06"]);

  const one = listed.find((c) => c.claim_id === "CLM-DEMO-04")!;
  for (const query of [one.member_id.toLowerCase(), one.provider_npi!.slice(2, 8), one.provider_name!.toUpperCase()]) {
    await search.fill(query);
    const expected = listed
      .filter((c) =>
        [c.claim_id, c.member_id, c.provider_name ?? "", c.provider_npi ?? ""].some((v) =>
          v.toLowerCase().includes(query.toLowerCase()),
        ),
      )
      .map((c) => c.claim_id)
      .sort();
    expect(expected).toContain("CLM-DEMO-04");
    await expect.poll(() => shownClaims(page)).toEqual(expected);
  }

  await search.fill("");
  for (const [outcome, label] of Object.entries(LABELS)) {
    await chooseStatus(page, label);
    const expected = listed.filter((c) => c.outcome === outcome).map((c) => c.claim_id).sort();
    if (expected.length) {
      await expect.poll(() => shownClaims(page)).toEqual(expected);
    } else {
      await expect(page.getByText("No claims match")).toBeVisible();
    }
  }
  await chooseStatus(page, "Rejected");
  await search.fill("zzz-nothing");
  await expect(page.getByText("No claims match")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByText(`${listed.length} claims`)).toBeVisible();

  // Back to a filtered list keeps its filter.
  await chooseStatus(page, "Denied");
  await page.getByRole("link", { name: "CLM-DEMO-05" }).click();
  await expect(page.getByRole("heading", { name: "Claim CLM-DEMO-05" })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/status=DENIED/);
  await expect(page.getByLabel("Status")).toContainText("Denied");
  await axeClean(page, "reviewer claims page");
});

test("admin: the Claims page reads and filters every claim, view only", async ({ page }) => {
  await loginAs(page, "admin");
  const rejected = ((await (await page.request.get("/v1/claims")).json()) as { claim_id: string; outcome: string }[])
    .filter((c) => c.outcome === "REJECTED")
    .map((c) => c.claim_id)
    .sort();
  expect(rejected).toEqual(expect.arrayContaining(["CLM-DEMO-06", "CLM-DEMO-07", "CLM-DEMO-09"]));
  await page.goto("/claims?status=REJECTED");
  await expect(page.getByLabel("Status")).toContainText("Rejected");
  await expect.poll(() => shownClaims(page)).toEqual(rejected);
  await page.getByLabel("Search claims").fill("demo-07");
  await expect.poll(() => shownClaims(page)).toEqual(["CLM-DEMO-07"]);
  await page.getByRole("link", { name: "CLM-DEMO-07" }).click();
  await expect(page.getByRole("button", { name: "Review claim" })).toHaveCount(0);
  await axeClean(page, "admin claim page");
});

test("the Reason column and the renamed page", async ({ page }) => {
  await loginAs(page, "reviewer1");
  await page.goto("/claims");
  const reasonOf = (id: string) => page.getByRole("row").filter({ has: page.getByRole("link", { name: id }) });
  await expect(reasonOf("CLM-DEMO-06").getByTestId("reason")).toHaveText(/A provider NPI is not valid/);
  await expect(reasonOf("CLM-DEMO-01").getByRole("cell").nth(2)).toHaveText("—");
  await reasonOf("CLM-DEMO-04").getByTestId("reason").focus();
  await expect(page.getByRole("tooltip")).toContainText("DN_NCCI_BUNDLED, R11");

  await page.getByRole("link", { name: "Returned and auto-denied" }).click();
  await expect(page).toHaveURL(/\/rule-outcomes$/);
  await expect(page.getByRole("heading", { name: "Returned and auto-denied", level: 1 })).toBeVisible();
  await expect(page.getByText("Claims the automatic checks returned, denied or put on hold, without a reviewer.")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "breadcrumb" })).toContainText("Returned and auto-denied");
  await page.getByLabel("Status").click();
  await expect(page.getByRole("option")).toHaveText(["All", "Rejected", "Denied", "Pended"]);
  await page.keyboard.press("Escape");
  await chooseStatus(page, "Denied");
  await expect.poll(() => shownClaims(page)).toEqual(["CLM-DEMO-05"]);
  await expect(reasonOf("CLM-DEMO-05").getByTestId("reason")).toHaveText(/Diagnoses do not support the service/);
  await axeClean(page, "returned and auto-denied page");

  await page.goto("/queue");
  await page.getByLabel("Search the queue").fill("demo-08");
  await expect(page.getByRole("link", { name: "CLM-DEMO-08" })).toBeVisible();
  await page.getByLabel("Search the queue").fill("nothing-like-it");
  await expect(page.getByText("No claims match")).toBeVisible();
  await axeClean(page, "review queue");
});

test("the original file: a JSON claim, a PDF and an image, in the sheet and a new tab", async ({ page }) => {
  // An image claim, filed here (the demo claims hold no image).
  const folder = mkdtempSync(join(tmpdir(), "claimsense-image-"));
  const image = join(folder, `${IMAGE_CLAIM}.png`);
  try {
    execFileSync("uv", ["run", "python", "-m", "scripts.demo.claim_image", "--claim-id", IMAGE_CLAIM, "--out", image], {
      cwd: ROOT,
      stdio: "ignore",
    });
    await loginAs(page, "provider1");
    await page.goto("/submit");
    await page.getByLabel("Claim file").setInputFiles(image);
    await page.getByRole("button", { name: "Read claim" }).click();
    await expect(page.getByText(`Claim ${IMAGE_CLAIM} was filed from a scanned form`)).toBeVisible({ timeout: 60_000 });
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
  await page.goto(`/my-claims/${IMAGE_CLAIM}`);
  await page.getByRole("button", { name: "View original file" }).click();
  const sheet = page.getByRole("dialog", { name: "Original file" });
  const picture = sheet.getByRole("img", { name: `Original file: ${IMAGE_CLAIM}.png` });
  await expect(picture).toBeVisible();
  expect(await picture.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  const fitted = await picture.evaluate((img) => img.getBoundingClientRect().width);
  await sheet.getByRole("button", { name: "Zoom in" }).click();
  expect(await picture.evaluate((img) => img.getBoundingClientRect().width)).toBeGreaterThan(fitted * 1.3);
  const [tab] = await Promise.all([page.waitForEvent("popup"), sheet.getByRole("link", { name: "Open in new tab" }).click()]);
  expect(tab.url()).toMatch(new RegExp(`/v1/claims/${IMAGE_CLAIM}/document$`));
  await tab.close();
  await axeClean(page, "image in the sheet", '[role="dialog"]');
  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);
  expect((await page.request.get("/v1/claims/CLM-DEMO-04/document")).status()).toBe(404); // provider2's

  await loginAs(page, "reviewer1");
  await page.goto("/claims/CLM-DEMO-01");
  const open = page.getByRole("button", { name: "View original file" });
  await open.focus();
  await page.keyboard.press("Enter"); // by keyboard
  await expect(sheet.getByTestId("original-json")).toContainText('"claim_id": "CLM-DEMO-01"');
  await axeClean(page, "JSON in the sheet", '[role="dialog"]');
  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);
  await expect(open).toBeFocused();

  await page.goto("/review/CLM-DEMO-08");
  await page.getByRole("button", { name: "View original file" }).click();
  const frame = sheet.locator("iframe");
  await expect(frame).toHaveAttribute("src", "/v1/claims/CLM-DEMO-08/document");
  const served = await page.request.get("/v1/claims/CLM-DEMO-08/document");
  expect([served.status(), served.headers()["content-type"]]).toEqual([200, "application/pdf"]);
  // Headless Chromium hands a PDF tab to a download, so the tab's own URL stays empty: the link and
  // the new tab it opens are checked, and the file it serves above.
  const link = sheet.getByRole("link", { name: "Open in new tab" });
  await expect(link).toHaveAttribute("href", "/v1/claims/CLM-DEMO-08/document");
  await expect(link).toHaveAttribute("target", "_blank");
  const [pdf] = await Promise.all([page.waitForEvent("popup"), link.click()]);
  await pdf.close();

  await page.goto("/claims");
  await chooseStatus(page, "Not processed"); // filed, never processed: "In review" to its provider
  await expect.poll(() => shownClaims(page)).toContain(IMAGE_CLAIM);
});

test("claim page: the summary first, then the clinical note and the audit trail as tabs", async ({ page }) => {
  await loginAs(page, "reviewer1");
  await page.goto("/claims/CLM-DEMO-01");
  const side = page.getByRole("complementary", { name: "Summary, clinical note and audit trail" });
  await expect(side.getByRole("tab", { name: "Summary" })).toHaveAttribute("aria-selected", "true");
  await expect(side.getByTestId("claim-summary")).toContainText("All checks passed.");
  await expect(side.getByTestId("claim-summary")).toContainText("Outcome: approved after review");
  await axeClean(page, "claim page, summary");

  await page.getByRole("button", { name: /Show the quote in the clinical note/ }).first().click();
  await expect(side.getByRole("tab", { name: "Clinical note" })).toHaveAttribute("aria-selected", "true");
  await expect(side.locator("mark.ring-2")).toBeInViewport();

  await side.getByRole("tab", { name: "Clinical note" }).focus();
  await page.keyboard.press("ArrowRight"); // tabs by keyboard
  await expect(side.getByRole("tab", { name: "Audit trail" })).toHaveAttribute("aria-selected", "true");
  await expect(side.getByRole("list", { name: "Audit trail" }).getByText("Finalized")).toBeVisible();
  await axeClean(page, "claim page, audit trail");

  await page.goto("/review/CLM-DEMO-08");
  await expect(side.getByRole("tab", { name: "Summary" })).toHaveAttribute("aria-selected", "true");
  await expect(side.getByTestId("claim-summary")).toContainText("If accepted:");
  // The review page's action bar is sticky and translucent: axe would blend it into the colours of
  // whatever text scrolls under it. A window tall enough for the whole page leaves nothing under it.
  await page.setViewportSize({ width: 1280, height: 2400 });
  await axeClean(page, "review page");
});

test("the filters and tabs by keyboard", async ({ page }) => {
  await loginAs(page, "provider2");
  await page.goto("/my-claims");
  await page.getByLabel("Search by claim ID").focus();
  await page.keyboard.type("demo");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Status")).toBeFocused();
  await page.keyboard.press("Enter");
  await page.getByRole("option", { name: "Rejected", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/status=REJECTED/);
  await expect.poll(() => shownClaims(page)).toEqual(["CLM-DEMO-06", "CLM-DEMO-09"]);
  await axeClean(page, "my claims");
});

test.describe("with reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("the evidence still opens the note at its quote, the sheet still opens", async ({ page }) => {
    await loginAs(page, "reviewer1");
    await page.goto("/claims/CLM-DEMO-03");
    const side = page.getByRole("complementary", { name: "Summary, clinical note and audit trail" });
    await expect(side.getByRole("tab", { name: "Summary" })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("button", { name: /Show the quote in the clinical note/ }).first().click();
    await expect(side.getByRole("tab", { name: "Clinical note" })).toHaveAttribute("aria-selected", "true");
    await expect(side.locator("mark.ring-2")).toBeInViewport();
    await page.getByRole("button", { name: "View original file" }).click();
    await expect(page.getByRole("dialog", { name: "Original file" })).toBeVisible();
    await axeClean(page, "reduced motion, the sheet", '[role="dialog"]');
    await page.keyboard.press("Escape");
    await axeClean(page, "reduced motion, the claim page");
  });
});
