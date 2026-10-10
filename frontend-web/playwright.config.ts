// Local smoke test (D-UI-1): needs `make demo` running (database containers, API, web app).
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  use: { baseURL: process.env.CLAIMSENSE_WEB_URL ?? "http://localhost:5173", trace: "retain-on-failure" },
  reporter: [["list"]],
});
