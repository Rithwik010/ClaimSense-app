// Logging in for the Playwright specs (D-AUTH-1): the demo users of `make demo-users`, with their
// passwords from the repository's .env (git-ignored). Switching user logs out first.

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, type Page } from "@playwright/test";

const ENV = fileURLToPath(new URL("../../.env", import.meta.url));

/** Which provider files which demo claim (scripts/demo/users.py FILED_BY). */
export const FILED_BY: Record<string, string> = {
  "01-approve-quick.json": "provider1",
  "02-pend-standard.json": "provider1",
  "03-deny-full-override.json": "provider1",
  "07-duplicate-of-01.json": "provider1",
  "04-partial-ncci.json": "provider2",
  "05-rule-deny-r15.json": "provider2",
  "06-reject-invalid-npi.json": "provider2",
  "08-scanned-clean.pdf": "provider2",
  "09-scanned-low-confidence.pdf": "provider2",
};

export function password(username: string): string {
  const key = `DEMO_PASSWORD_${username.toUpperCase()}`;
  const line = existsSync(ENV)
    ? readFileSync(ENV, "utf-8")
        .split("\n")
        .find((l) => l.startsWith(`${key}=`))
    : undefined;
  if (!line) throw new Error(`${key} is not in .env: run make demo-users`);
  return line.slice(key.length + 1).trim();
}

/** Log in through the login page as a demo user (logging out whoever was logged in). */
export async function loginAs(page: Page, username: string): Promise<void> {
  await page.request.post("/v1/auth/logout");
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password(username));
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}
