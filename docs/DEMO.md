# ClaimSense demo runbook

About 10 minutes. Synthetic data only. The claims are in `demo/claims/`; each step names its file.
Say the lines in quotes in your own words.

## Before the audience arrives (5 minutes)

1. `make demo-reset`, then `make demo` in a second terminal. Wait for "Ready" and for the web app
   on http://localhost:5173. Both start `ollama serve` themselves when it is not running (models
   kept loaded, cloud features off; log in `data/generated/logs/ollama.log`), so after a reboot
   nothing else is needed.
2. Open the web app at 1440 px or wider. In the sidebar set the role to **Reviewer** and the
   reviewer ID to `reviewer-demo`.
3. Open http://localhost:5173/metrics once (it loads the evaluation reports), then go to
   **Submit claim**.
4. Keep `demo-video/demo.webm` (the backup recording, `make demo-video`) open in a player in
   another window.

If anything below fails twice, switch to the backup video at the same step and keep talking.

## 1. A clean claim, end to end (2 minutes)

| Do | Say |
|---|---|
| **Submit claim** → Claim file → `01-approve-quick.json` → **Read claim** | "A provider submits a claim. JSON, a PDF of our form or a scanned form all work." |
| Point at **Fields read** | "Every field with the confidence it was read with. A JSON claim is exact." |
| **Process claim** | "Rules first, then the coverage policy, then our fine-tuned model, then the calculator." |
| On the claim page, watch the stage strip fill in | "Each stage with its result. The model only recommends; it never computes money." |
| **Review claim** → open line 1 → click a criterion's quote | "The recommendation cites the policy criterion and quotes the note; the quote is highlighted in the note." |
| **Accept recommendation** → **Finalize claim** | "A person always decides. Finalizing updates the member's accumulators and therapy visits used." |

If **Process claim** shows an error: check the `make demo` terminal; if Ollama is down, start it
and press **Process claim** again on the claim page.

## 2. The model denies, the reviewer overrides (2 minutes)

| Do | Say |
|---|---|
| **Submit claim** → `03-deny-full-override.json` → **Read claim** → **Process claim** | "This one the model recommends denying, so it goes to full review." |
| **Review claim** → line 1: a criterion **Not met**, with its quote | "Denials are where the model is most careful: on our test set it never denied a line that should be paid." |
| **Override line** → new decision Approve → reason → **Override line** | "A reviewer can disagree. The reason is required and kept in the audit trail." |
| **Finalize claim** → **Finalize claim** | "The calculator recomputes the amounts from the reviewer's decision; reviewers never type amounts." |

## 3. Rules decide on their own (2 minutes)

| Do | Say |
|---|---|
| `04-partial-ncci.json` → read → process → **Review claim** | "Line 2 is bundled under NCCI: a rule denied it, and rule outcomes can't be overridden. Line 1 goes on to the model." |
| **Accept recommendation** → **Finalize claim** | "Partly approved." |
| `05-rule-deny-r15.json` → read → process | "The diagnosis doesn't support the service under the billing article, so a rule denies it. The model never sees it; the strip shows those stages as not reached." |
| `06-reject-invalid-npi.json` → read | "An NPI with a wrong check digit: the claim is filed, then rejected back to the provider." |
| `07-duplicate-of-01.json` → read → process | "The same services again under a new claim number: rejected as a duplicate." |
| Open **Rule outcomes** | "Everything the rules decided, with the reason, read-only." |

## 4. Scanned forms (2 minutes)

| Do | Say |
|---|---|
| `08-scanned-clean.pdf` → **Read claim** (a few seconds) | "A scanned form read by OCR: 93.8% field accuracy on held-out scans." |
| Point at the confidence column → **Process claim** | "It goes through the same pipeline as JSON." |
| `09-scanned-low-confidence.pdf` → **Read claim** → point at the highlighted rows | "Here the NPI was mistyped on the form. It is read with low confidence, so it is highlighted." |
| **Process claim** → **Rule checks** tab | "A rule failed on a field we couldn't trust, so the claim is rejected for the provider to resubmit, never denied." |

## 5. Explanation and evidence (1 minute)

| Do | Say |
|---|---|
| **Claims** → `CLM-DEMO-03` → **Explanation** tab | "Every amount and reason in this explanation comes from the decision record; we test that on every golden claim." |
| **Audit trail** tab | "Every step, who did it and when." |

## 6. How good is it (1 minute)

| Do | Say |
|---|---|
| **Metrics** | "Model v2 against v1 on 300 synthetic test claims: macro-F1 0.853, up from 0.694, short of our 0.90 target, so every recommendation goes to a person." |
| Point at **Where v2 goes wrong** | "Its mistakes lean towards asking for more information or approving, not towards wrong denials, and they are spread across policies." |

## Offline

A demo run needs no internet. Checked on 11 Oct: the app and the web app call only localhost
(fonts are bundled); Qdrant's telemetry is off (`docker-compose.yml`); onnxruntime's telemetry to
Microsoft is off (`ORT_DISABLE_TELEMETRY=1`, set by `app/rag/embedding.py` and the Makefile,
D-PROC-4); the Makefile sets `HF_HUB_OFFLINE=1` (the v2 policy lookup embeds nothing; the
embedding model is cached by setup);
`ollama serve` makes no calls for a local model, though the Ollama desktop app checks for updates,
so run `ollama serve` or turn updates off. Downloads happen only in setup: Docker images, npm and
uv packages, the embedding model, Playwright's browser.

## If a step fails

| Symptom | Do |
|---|---|
| "The API cannot be reached" or "is not forwarding" | Restart `make demo`; reload the page. |
| "A claim with this claim ID is already on file" | The database was not reset: `make demo-reset`, then start again (or skip to the next claim). |
| Processing takes over a minute | Ollama is loading the model; wait, or use the backup video for that step. |
| A scanned form is rejected unexpectedly | Use the JSON claims and say OCR results are on the Metrics page. |
| A page shows "This page could not be shown" | Reload the page. |

The same run, clicked by a script: `make demo-video` (records `demo-video/demo.webm`).
