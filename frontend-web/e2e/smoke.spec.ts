// Smoke test (D-UI-1), local only, against a running `make demo`: submit a JSON claim -> process ->
// open it from the review queue -> accept -> the claim detail shows the explanation and the audit
// trail. The claim is a synthetic corpus claim whose rules pass (data/generated/claims/), one not
// yet on file, so each run files a new claim.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const CORPUS = fileURLToPath(new URL("../../data/generated/claims/claims.jsonl", import.meta.url));

interface CorpusRecord {
  scenario_type: string;
  claim: { claim_id: string };
  expected: { rule_outcome: string };
}

test("submit, process, review and explain a claim", async ({ page, request }) => {
  const onFile = new Set(
    ((await (await request.get("/v1/claims")).json()) as { claim_id: string }[]).map((c) => c.claim_id),
  );
  const record = readFileSync(CORPUS, "utf-8")
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as CorpusRecord)
    .find(
      (r) =>
        r.expected.rule_outcome === "PASS" &&
        r.scenario_type === "approve_single" &&
        !onFile.has(r.claim.claim_id),
    );
  test.skip(!record, "every corpus claim of the scenario is already on file");
  const claim = record!.claim;
  const claimId = claim.claim_id;

  await page.goto("/submit");
  await page.getByLabel("Role").selectOption("reviewer");
  await page.getByLabel("Reviewer ID").fill("reviewer-smoke");
  await page.getByLabel("Claim file").setInputFiles({
    name: `${claimId}.json`,
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(claim)),
  });
  await page.getByRole("button", { name: "Read claim" }).click();
  await expect(page.getByText(`Claim ${claimId} filed from a JSON claim.`)).toBeVisible();

  await page.getByRole("button", { name: "Process claim" }).click();
  await expect(page).toHaveURL(new RegExp(`/claims/${claimId}$`), { timeout: 110_000 });
  await expect(page.getByText("Awaiting review").first()).toBeVisible();

  await page.getByRole("link", { name: "Review queue" }).click();
  await page.getByRole("link", { name: claimId }).click();
  await expect(page.getByRole("heading", { name: `Review claim ${claimId}` })).toBeVisible();
  await page.getByRole("button", { name: "Accept all" }).click();
  await page.getByRole("button", { name: "Accept and finalize" }).click();
  await expect(page.getByText(`Claim ${claimId} is final:`)).toBeVisible();

  await page.getByRole("link", { name: "See the claim and its explanation" }).click();
  const explanation = page.getByTestId("explanation");
  await expect(explanation.getByRole("heading", { name: "Summary" })).toBeVisible();
  await expect(explanation.getByRole("heading", { name: "Rule checks" })).toBeVisible();
  await expect(explanation.getByText("reviewer-smoke")).toBeVisible();
  await expect(page.getByTestId("audit-trail").getByText("Finalized")).toBeVisible();
});
