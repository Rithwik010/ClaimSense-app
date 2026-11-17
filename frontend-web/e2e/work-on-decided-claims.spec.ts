// What people do with a decided claim and the new pages (D-FUP-1, D-APL-1, D-AUTH-2, D-AUD-1,
// D-NTF-1, D-QLT-1, D-POL-9, D-MEM-5), in the browser. Runs last (its name sorts after the other
// specs): it changes CLM-DEMO-02, which the other specs read as pended. Needs demo-claims.spec.ts
// first (claim 2 pended after review). Steps:
// - provider1 sends documentation for CLM-DEMO-02: back to Not processed, then processed again;
// - reviewer1 denies it; provider1 appeals; reviewer1 may not decide the appeal, reviewer2 upholds it;
// - the admin finds the documentation in the audit search, sees Review quality, adds a login that
//   five wrong passwords lock, and unlocks it; that user changes their own password;
// - the bell, the policy library and the member's plan page; no serious or critical axe violation.

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { loginAs } from "./session";

const CLAIM = "CLM-DEMO-02";
const TEMP_USER = `reviewer-t${String(Date.now()).slice(-5)}`;
const TEMP_PASSWORD = "a temporary password 1";
const NEW_PASSWORD = "a newer password 22";

test.describe.configure({ mode: "serial" });
test.setTimeout(180_000);

async function axeClean(page: Page, what: string) {
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every((a) => a.playState !== "running" || a.effect?.getTiming().iterations === Infinity),
  );
  await page.waitForTimeout(250);
  const results = await new AxeBuilder({ page }).analyze();
  const bad = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).join("; ")}`);
  expect(bad, `${what}: serious or critical axe violations`).toEqual([]);
}

async function logInWith(page: Page, username: string, password: string) {
  await page.request.post("/v1/auth/logout");
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
}

test("provider1 sends documentation for a pended claim, then processes it again", async ({ page }) => {
  await loginAs(page, "provider1");
  await page.goto(`/my-claims/${CLAIM}`);
  await expect(page.getByRole("heading", { name: "What you can do next" })).toBeVisible();
  await page.getByRole("button", { name: "Send documentation" }).click();
  const dialog = page.getByRole("dialog", { name: "Send documentation" });
  await dialog.getByLabel("Documentation").fill("Colonoscopy report: two polyps removed by snare; pathology attached.");
  await axeClean(page, "send documentation dialog");
  await dialog.getByRole("button", { name: "Add to the claim" }).click();
  await expect(page.getByText(/Sent back to you/)).toBeVisible();
  await expect(page.getByText("Not processed").first()).toBeVisible();

  await page.getByRole("button", { name: "Process claim" }).click();
  await expect(page.getByText(/In review\. A reviewer is checking/)).toBeVisible({ timeout: 150_000 });
});

test("reviewer1 denies it; provider1 appeals; reviewer2, not reviewer1, decides the appeal", async ({ page }) => {
  await loginAs(page, "reviewer1");
  const view = (await (await page.request.get(`/v1/claims/${CLAIM}`)).json()) as {
    record: { line_decisions: { line_no: number; decision: string; source: string }[] };
  };
  const lines = view.record.line_decisions.filter((l) => l.source !== "RULE" && l.decision !== "DENY");
  const denied = await page.request.post(`/v1/claims/${CLAIM}/review`, {
    data: {
      claim_id: CLAIM,
      reviewer_id: "reviewer1",
      action: lines.length ? "OVERRIDE" : "ACCEPT",
      line_overrides: lines.map((l) => ({
        line_no: l.line_no,
        decision: "DENY",
        reason_code: "DN_NOT_MEDICALLY_NECESSARY",
        reason: "The report does not show the criteria for this procedure.",
      })),
      timestamp: new Date().toISOString(),
    },
  });
  expect(denied.status(), await denied.text()).toBe(200);

  await loginAs(page, "provider1");
  await page.goto(`/my-claims/${CLAIM}`);
  await page.getByRole("button", { name: "Appeal the decision" }).click();
  const dialog = page.getByRole("dialog", { name: "Appeal the decision" });
  await dialog.getByLabel("Why the claim should be decided again").fill("The pathology report shows the polyps the policy asks about.");
  await dialog.getByRole("button", { name: "File the appeal" }).click();
  await expect(page.getByText(/Appealed\. A reviewer who did not deny the claim/)).toBeVisible();

  await loginAs(page, "reviewer1");
  await page.goto(`/review/${CLAIM}`);
  await expect(page.getByText(/Appeal: the provider asks for this denied claim to be decided again/)).toBeVisible();
  await expect(page.getByText("You made the decision under appeal, so another reviewer decides it.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Accept all lines" })).toBeDisabled();

  await loginAs(page, "reviewer2");
  await page.goto("/queue");
  await page.getByLabel("Search the queue").fill(CLAIM); // opens the tier that holds it
  await expect(page.getByRole("row", { name: new RegExp(CLAIM) })).toContainText("Appeal: decide again");
  await page.goto(`/review/${CLAIM}`);
  await expect(page.getByText(/reviewer1 opened this claim/)).toBeVisible();
  await page.getByRole("button", { name: "Accept all lines" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Finalize claim" }).click();
  await expect(page.getByText(`Claim ${CLAIM} is final`)).toBeVisible();
  await expect(page.getByRole("button", { name: "Correct the model's criteria" })).toBeVisible();

  await loginAs(page, "provider1");
  await page.goto(`/my-claims/${CLAIM}`);
  await expect(page.getByText("The decision stood")).toBeVisible();
  await expect(page.getByRole("button", { name: "Appeal the decision" })).toHaveCount(0); // once only
  await page.getByRole("button", { name: /^Notifications/ }).click();
  await expect(page.getByRole("menu").getByText(`The appeal of claim ${CLAIM} is decided: the decision stood`)).toBeVisible();
  await page.keyboard.press("Escape");
});

test("the admin's audit search, review quality and users; a locked login", async ({ page }) => {
  await loginAs(page, "admin");
  await page.goto("/audit?event_type=DOCUMENTATION_ADDED");
  const row = page.getByRole("row").filter({ has: page.getByRole("link", { name: CLAIM }) });
  await expect(row).toContainText("Documentation added");
  await expect(row).toContainText(/characters added to the clinical notes/);
  await axeClean(page, "audit search");

  await page.goto("/quality");
  await expect(page.getByRole("heading", { name: "Review quality", level: 1 })).toBeVisible();
  await expect(page.getByText("Model lines accepted")).toBeVisible();
  await expect(page.getByRole("region", { name: "Appeals" }).getByText("Decision stood")).toBeVisible();
  await axeClean(page, "review quality");

  await page.goto("/users");
  await page.getByRole("button", { name: "Add a login" }).click();
  const dialog = page.getByRole("dialog", { name: "Add a login" });
  await dialog.getByLabel("Username").fill(TEMP_USER);
  await dialog.getByLabel("Password").fill(TEMP_PASSWORD);
  await dialog.getByRole("button", { name: "Add login" }).click();
  const user = page.getByRole("row").filter({ hasText: TEMP_USER });
  await expect(user).toContainText("Active");
  await axeClean(page, "users");

  for (let i = 0; i < 5; i += 1) {
    const wrong = await page.request.post("/v1/auth/login", { data: { username: TEMP_USER, password: "not the password" } });
    expect(wrong.status()).toBe(401);
  }
  const locked = await page.request.post("/v1/auth/login", { data: { username: TEMP_USER, password: TEMP_PASSWORD } });
  expect(locked.status()).toBe(429);
  await page.reload();
  await expect(user).toContainText("Locked");
  await user.getByRole("button", { name: "Unlock" }).click();
  await expect(user).toContainText("Active");
});

test("a user changes their own password", async ({ page }) => {
  await logInWith(page, TEMP_USER, TEMP_PASSWORD);
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  await page.getByRole("button", { name: /open the user menu/ }).click();
  await page.getByRole("menuitem", { name: "Change password" }).click();
  const dialog = page.getByRole("dialog", { name: "Change your password" });
  await dialog.getByLabel("Current password").fill(TEMP_PASSWORD);
  await dialog.getByLabel("New password", { exact: true }).fill(NEW_PASSWORD);
  await dialog.getByLabel("New password again").fill(NEW_PASSWORD);
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(dialog).toHaveCount(0);

  await logInWith(page, TEMP_USER, NEW_PASSWORD);
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
});

test("the policy library and the member's plan", async ({ page }) => {
  await loginAs(page, "provider1");
  await page.goto("/policies");
  await page.getByLabel("Search by procedure code or words").fill("45378");
  await page.getByRole("list", { name: "Policies" }).getByRole("button").first().click();
  await expect(page.getByText("Sources:", { exact: false })).toBeVisible();
  await axeClean(page, "coverage policies");

  await loginAs(page, "member1");
  await page.goto("/member/plan");
  await expect(page.getByRole("heading", { name: "My plan", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What you pay for covered services" })).toBeVisible();
  await axeClean(page, "my plan");
  await page.goto("/member/benefits");
  await expect(page.getByRole("meter").first()).toBeVisible();
  await page.getByRole("button", { name: /Ask about your plan/ }).click();
  const panel = page.getByRole("dialog", { name: /Plan assistant/ });
  await panel.getByLabel("Ask in your own words").fill("how many therapy visits do I have left?");
  await panel.getByRole("button", { name: "Send" }).click();
  await expect(panel.getByRole("list", { name: "Answers" })).toContainText(/visits used this benefit year/);
});
