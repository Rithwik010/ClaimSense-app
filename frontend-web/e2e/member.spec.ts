// The member's pages (D-MEM-1, D-MEM-2, D-MEM-3), run after e2e/demo-claims.spec.ts on its claims:
// member1 is the patient of CLM-DEMO-01 (approved after review) and CLM-DEMO-07 (rejected as its
// duplicate), member2 of CLM-DEMO-04 (partly approved). A claim filed here for member1 and not
// processed shows "Being processed" and nothing else. The EOB a member sees is the one the provider
// gets, to the cent; benefits and profile show what the API sends; a member has no access to any
// provider, reviewer or admin page or endpoint, and other roles none to the member's pages. Every
// member page has no serious or critical axe violation and fits at 390, 768 and 1440 px. Nothing is
// saved: no screenshots.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { loginAs } from "./session";

const DEMO_01 = fileURLToPath(new URL("../../demo/claims/01-approve-quick.json", import.meta.url));
// What a member page never shows: rule IDs, internal reason codes, criterion IDs, a reviewer.
const HIDDEN = /\bR(?:0[1-9]|1\d|20)\b|\bDUP\b|\b(?:RJ|DN|PD|RV)_[A-Z0-9_]+\b|\bMODEL_OUTPUT_INVALID\b|\bPOL-[A-Z]+-\d{3}\.c\d+\b|reviewer\d/;
const NEW_CLAIM = `CLM-MBR-${String(Date.now()).slice(-6)}`;
const MEMBER1 = "MBR-000015";
const MEMBER2 = "MBR-000495";

test.describe.configure({ mode: "serial" });
test.setTimeout(120_000);

/** The web app's own formatting of integer cents (src/lib/format.ts), to read amounts on screen. */
function money(cents: number | null): string {
  if (cents === null) return "—";
  const rest = cents % 100;
  return `$${((cents - rest) / 100).toLocaleString("en-US")}.${String(rest).padStart(2, "0")}`;
}

/** No serious or critical axe violation, checked at rest (after the page's fade-in). */
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

async function mainText(page: Page): Promise<string> {
  return page.getByRole("main").innerText();
}

/** The claims a reviewer sees for a member: what the member's list must hold, no more. */
async function claimsOf(page: Page, memberId: string): Promise<string[]> {
  await loginAs(page, "reviewer1");
  const all = (await (await page.request.get("/v1/claims")).json()) as { claim_id: string; member_id: string }[];
  return all
    .filter((c) => c.member_id === memberId)
    .map((c) => c.claim_id)
    .sort();
}

async function listed(page: Page): Promise<string[]> {
  return (await page.getByRole("table", { name: "My claims" }).getByRole("link").allTextContents()).sort();
}

test("member1: only their own claims; one not yet final shows nothing of its outcome", async ({ page }) => {
  // A claim for member1 that provider1 files and does not process: demo claim 01 five weeks later.
  const claim = JSON.parse(readFileSync(DEMO_01, "utf-8")) as {
    claim_id: string;
    service_lines: { date_of_service: string }[];
  };
  claim.claim_id = NEW_CLAIM;
  for (const line of claim.service_lines) {
    const day = new Date(`${line.date_of_service}T00:00:00Z`);
    day.setUTCDate(day.getUTCDate() + 35);
    line.date_of_service = day.toISOString().slice(0, 10);
  }
  await loginAs(page, "provider1");
  expect((await page.request.post("/v1/claims/intake", { data: claim })).status()).toBe(201);

  const theirs = await claimsOf(page, MEMBER1);
  expect(theirs).toEqual(expect.arrayContaining(["CLM-DEMO-01", "CLM-DEMO-07", NEW_CLAIM]));

  await loginAs(page, "member1"); // a member's home is their claims
  await expect(page.getByRole("heading", { name: "My claims" })).toBeVisible();
  await expect.poll(() => listed(page)).toEqual(theirs);
  const table = page.getByRole("table", { name: "My claims" });
  await expect(table.getByRole("link", { name: "CLM-DEMO-04" })).toHaveCount(0); // member2's
  const waiting = table.getByRole("row", { name: new RegExp(NEW_CLAIM) });
  await expect(waiting.getByText("Being processed")).toBeVisible();
  await expect(waiting.getByText(/\$/)).toHaveCount(0);
  await expect(table.getByRole("row", { name: /CLM-DEMO-01/ }).getByText("Approved")).toBeVisible();
  await expect(table.getByRole("row", { name: /CLM-DEMO-07/ }).getByText("Rejected")).toBeVisible();
  expect(await mainText(page)).not.toMatch(HIDDEN);
  await axeClean(page, "member: my claims");

  await waiting.getByRole("link", { name: NEW_CLAIM }).click();
  await expect(page.getByRole("heading", { name: "Your claim is being processed" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Explanation of benefits" })).toHaveCount(0);
  await expect(page.getByRole("main").getByText(/\$/)).toHaveCount(0);
  await axeClean(page, "member: a claim being processed");

  await page.goto("/member/claims/CLM-DEMO-07");
  await expect(page.getByRole("heading", { name: "Your claim was returned to your provider" })).toBeVisible();
  expect(await mainText(page)).not.toMatch(HIDDEN);
});

test("member1: the approved claim's EOB is the provider's EOB, to the cent", async ({ page }) => {
  await loginAs(page, "provider1");
  const providers = await (await page.request.get("/v1/claims/CLM-DEMO-01/eob")).json();
  await loginAs(page, "member1");
  const mine = (await (await page.request.get("/v1/member/claims/CLM-DEMO-01/eob")).json()) as {
    totals: { billed_cents: number; plan_pays_cents: number; patient_pays_cents: number };
  };
  expect(mine).toEqual(providers);

  await page.goto("/member/claims");
  await page.getByRole("link", { name: "CLM-DEMO-01" }).click();
  await expect(page.getByRole("heading", { name: "Explanation of benefits" })).toBeVisible();
  await expect(page.getByText("This is not a bill.")).toBeVisible();
  const total = page.getByRole("table", { name: "Services" }).getByRole("row", { name: /^Total/ });
  for (const cents of [mine.totals.billed_cents, mine.totals.plan_pays_cents, mine.totals.patient_pays_cents]) {
    await expect(total).toContainText(money(cents));
  }
  expect(await mainText(page)).not.toMatch(HIDDEN);
  await axeClean(page, "member: the EOB");
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("button", { name: "Print" })).toBeHidden();
  await expect(page.locator("header").first()).toBeHidden();
  await page.emulateMedia({ media: "screen" });
  await page.getByRole("link", { name: "Back to my claims" }).click();
  await expect(page).toHaveURL(/\/member\/claims$/);
});

test("member2: a partly approved claim; another member's claim is not found", async ({ page }) => {
  const theirs = await claimsOf(page, MEMBER2);
  expect(theirs).toContain("CLM-DEMO-04");
  await loginAs(page, "member2");
  await expect.poll(() => listed(page)).toEqual(theirs);
  await page.getByRole("link", { name: "CLM-DEMO-04" }).click();
  const services = page.getByRole("table", { name: "Services" });
  await expect(services.getByText("Paid", { exact: true })).toBeVisible();
  await expect(services.getByText("Not paid", { exact: true })).toBeVisible();
  expect(await mainText(page)).not.toMatch(HIDDEN);
  await axeClean(page, "member: a partly approved EOB");

  await page.goto("/member/claims/CLM-DEMO-01"); // member1's
  await expect(page.getByText("Not found: claim CLM-DEMO-01 not found")).toBeVisible();
  expect((await page.request.get("/v1/member/claims/CLM-DEMO-01/eob")).status()).toBe(404);
});

test("member1: benefits and profile, as the API sends them", async ({ page }) => {
  await loginAs(page, "member1");
  const benefits = (await (await page.request.get("/v1/member/benefits")).json()) as {
    plan_name: string;
    networks: { network: string; deductible_met_cents: number; deductible_cents: number; oop_met_cents: number; oop_max_cents: number }[];
    visits: { benefit_category: string; visit_limit: number; visits_used: number }[];
  };
  await page.getByRole("link", { name: "My benefits" }).click();
  await expect(page.getByRole("heading", { name: "My benefits" })).toBeVisible();
  for (const network of benefits.networks) {
    const region = page.getByRole("region", { name: network.network === "IN_NETWORK" ? "In network" : "Out of network" });
    await expect(region).toContainText(money(network.deductible_met_cents));
    await expect(region).toContainText(`of a ${money(network.deductible_cents)} deductible`);
    await expect(region).toContainText(money(network.oop_met_cents));
    await expect(region).toContainText(`of a ${money(network.oop_max_cents)} out-of-pocket maximum`);
  }
  const rehab = benefits.visits.find((v) => v.benefit_category === "REHAB_THERAPY")!;
  const row = page.getByRole("table", { name: "Visits" }).getByRole("row", { name: /Rehab therapy/ });
  await expect(row).toContainText(String(rehab.visits_used));
  await expect(row).toContainText(String(rehab.visit_limit));
  await expect(page.getByText(benefits.plan_name, { exact: false }).first()).toBeVisible();
  await axeClean(page, "member: my benefits");

  await page.getByRole("link", { name: "Profile" }).click();
  await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
  const profile = page.getByRole("main");
  for (const text of [MEMBER1, "Carl Sanchez", "ClaimSense PPO Gold (PPO)", "01/01/2026", "No end date"]) {
    await expect(profile).toContainText(text);
  }
  await axeClean(page, "member: profile");
});

test("a member has no access to provider, reviewer and admin pages or endpoints, nor they to a member's", async ({ page }) => {
  await loginAs(page, "member1");
  for (const path of [
    "/my-claims",
    "/submit",
    "/my-claims/CLM-DEMO-01/eob",
    "/queue",
    "/claims",
    "/claims/CLM-DEMO-01",
    "/review/CLM-DEMO-08",
    "/rule-outcomes",
    "/overview",
    "/metrics",
    "/audit",
    "/system",
  ]) {
    await page.goto(path);
    await expect(page.getByText("You don't have access"), path).toBeVisible();
  }
  await axeClean(page, "member: no access");
  for (const [method, path] of [
    ["GET", "/v1/claims"],
    ["GET", "/v1/claims/CLM-DEMO-01"],
    ["GET", "/v1/claims/CLM-DEMO-01/eob"],
    ["GET", "/v1/claims/CLM-DEMO-01/document"],
    ["GET", "/v1/claims/CLM-DEMO-01/explanation"],
    ["GET", "/v1/review/queue"],
    ["GET", "/v1/metrics/overview"],
    ["POST", "/v1/claims/intake"],
    ["POST", "/v1/claims/CLM-DEMO-08/process"],
  ] as const) {
    const response = await page.request.fetch(path, { method, data: method === "POST" ? {} : undefined });
    expect(response.status(), `${method} ${path}`).toBe(403);
  }
  for (const [user, path] of [
    ["provider1", "/member/claims"],
    ["reviewer1", "/member/benefits"],
    ["admin", "/member/profile"],
  ] as const) {
    await loginAs(page, user);
    await page.goto(path);
    await expect(page.getByText("You don't have access"), `${user} ${path}`).toBeVisible();
  }
});

for (const size of [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
]) {
  test(`member pages fit at ${size.width}x${size.height}`, async ({ page }) => {
    await page.setViewportSize(size);
    await loginAs(page, "member1");
    for (const [path, heading] of [
      ["/member/claims", "My claims"],
      ["/member/claims/CLM-DEMO-01", "Explanation of benefits"],
      [`/member/claims/${NEW_CLAIM}`, "Your claim is being processed"],
      ["/member/benefits", "My benefits"],
      ["/member/profile", "Profile"],
    ] as const) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: heading, exact: true }), path).toBeVisible({ timeout: 15_000 });
      const { scroll, width } = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        width: window.innerWidth,
      }));
      expect(scroll, `${path}: no horizontal page scroll`).toBeLessThanOrEqual(width);
      const menu = (await page.getByRole("button", { name: /open the user menu/ }).boundingBox())!;
      expect(menu.x + menu.width, `${path}: user menu inside the window`).toBeLessThanOrEqual(size.width);
    }
  });
}
