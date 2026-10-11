// Local smoke test (D-UI-1): needs `make demo-up` running (the API serves the web app on :8000;
// CLAIMSENSE_WEB_URL=http://localhost:5173 for `make demo`) and the demo users (`make demo-users`).
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  // The runbook recording runs only for `make demo-video` (it files the demo claims).
  testIgnore: process.env.DEMO_VIDEO ? [] : ["**/demo-runbook.spec.ts"],
  timeout: 120_000,
  // One database for every spec, and layout.spec.ts opens claims demo-claims.spec.ts files: one at a time.
  workers: 1,
  use: { baseURL: process.env.CLAIMSENSE_WEB_URL ?? "http://localhost:8000", trace: "retain-on-failure" },
  reporter: [["list"]],
});
