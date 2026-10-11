// Layout at the four sizes DESIGN.md and the demo use (390, 768 and 1440 px wide, and the 1280x720
// projector), for every role's pages, the login page and the no-access page: each page loads, no
// horizontal page scroll, and the user menu stays inside the window. Run after
// e2e/demo-claims.spec.ts (it opens CLM-DEMO-03 and the claim still waiting, CLM-DEMO-08).
// Nothing is saved: no screenshots.

import { expect, test, type Page } from "@playwright/test";

import { loginAs } from "./session";

const SIZES = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
];

const PAGES: Record<string, [string, string][]> = {
  provider1: [
    ["/my-claims", "My claims"],
    ["/submit", "Submit claim"],
    ["/queue", "You don't have access"],
  ],
  reviewer1: [
    ["/queue", "Review queue"],
    ["/claims", "Claims"],
    ["/claims/CLM-DEMO-03", "Claim CLM-DEMO-03"],
    ["/review/CLM-DEMO-08", "Review claim CLM-DEMO-08"],
    ["/rule-outcomes", "Rule outcomes"],
  ],
  admin: [
    ["/overview", "Overview"],
    ["/metrics", "Metrics"],
    ["/claims/CLM-DEMO-01", "Claim CLM-DEMO-01"],
  ],
};

async function fits(page: Page, what: string) {
  const { scroll, width } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    width: window.innerWidth,
  }));
  expect(scroll, `${what}: no horizontal page scroll`).toBeLessThanOrEqual(width);
}

for (const size of SIZES) {
  test.describe(`${size.width}x${size.height}`, () => {
    test.use({ viewport: size });

    test("login page", async ({ page }) => {
      await page.request.post("/v1/auth/logout");
      await page.goto("/login");
      const form = page.locator("form");
      await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
      const box = (await form.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(size.width);
      expect(box.y + box.height, "the whole form on screen").toBeLessThanOrEqual(size.height);
      await fits(page, "login");
    });

    for (const [username, pages] of Object.entries(PAGES)) {
      test(`${username}'s pages`, async ({ page }) => {
        await loginAs(page, username);
        for (const [path, heading] of pages) {
          await page.goto(path);
          const title =
            heading === "You don't have access"
              ? page.getByText(heading)
              : page.getByRole("heading", { name: heading, exact: true });
          await expect(title, `${username} ${path}`).toBeVisible({ timeout: 15_000 });
          await fits(page, `${username} ${path}`);
          const menu = (await page.getByRole("button", { name: /open the user menu/ }).boundingBox())!;
          expect(menu.x + menu.width, `${path}: user menu inside the window`).toBeLessThanOrEqual(size.width);
        }
      });
    }
  });
}
