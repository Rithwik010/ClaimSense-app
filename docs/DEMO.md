# ClaimSense demo run-sheet

Synthetic data only. The nine claims are in `demo/claims/`; run them in this order.

## Before

1. `make demo-reset` (clean database, demo logins, model loaded), then `make demo-up` in a
   second terminal (it starts `ollama serve` itself if needed).
2. `make demo-check`: five OK lines, Logins included.
3. Open **http://localhost:8000**. No internet is needed (`make offline-check`).

## Logins

| Username | Who | Lands on |
|---|---|---|
| `provider1` | Gregory Hernandez, DPT (provider) | My claims |
| `provider2` | Jennifer Dunn, DPM (provider) | My claims |
| `reviewer1`, `reviewer2` | reviewers | Review queue |
| `admin` | read-only admin | Overview |

Passwords are in `.env` at the repository root (`DEMO_PASSWORD_PROVIDER1` and so on); `make
demo-users` or `make demo-reset` writes any that are missing. Switch user with the menu at the
top right: **Log out**.

## The nine claims

A provider files: **Submit claim** → drop the file on the box (or choose it) → **Read claim** →
check **Fields read** → **Process claim** (the stage strip fills in) → **Open claim result**. A
reviewer reviews: **Review queue** → the tier's tab → the claim → **Accept all lines** (or
**Override line**) → **Finalize claim** → confirm; then **Next claim** opens the next one waiting.

| # | Who | File and steps | Expected result |
|---|---|---|---|
| 1 | provider1 | `01-approve-quick.json`: file and process | **In review**; the strip shows "Waiting for a reviewer" |
|   | reviewer1 | **Quick** tab → `CLM-DEMO-01` → click a criterion's quote (the note scrolls to it) → **Accept all lines** → **Finalize claim** | **Approved**. provider1 → **My claims** → `CLM-DEMO-01`: lines, amounts, explanation |
| 2 | provider1 | `02-pend-standard.json`: file and process | **In review** |
| 3 | provider1 | `03-deny-full-override.json`: file and process | **In review** |
|   | reviewer1 | **Standard** tab → `CLM-DEMO-02` → **Accept all lines** → **Finalize claim** → **Next claim** | 2 **Needs information**; **Next claim** opens `CLM-DEMO-03` |
|   | reviewer1 | `CLM-DEMO-03` (full tier; the model recommends Deny) → **Override line** → New decision Approve, a reason → **Override line** → **Finalize claim** | **Approved**, amounts recomputed |
| 4 | provider2 | `04-partial-ncci.json`: file and process | **In review** |
|   | reviewer1 | `CLM-DEMO-04`: line 2 denied by an NCCI rule, CARC 236 (cannot be overridden) → **Accept all lines** → **Finalize claim** | **Partly approved** |
| 5 | provider2 | `05-rule-deny-r15.json`: file and process → **Open claim result** | **Denied by a rule** at once: CARC 11, RARC N115, the billing article and its LCD |
| 6 | provider2 | `06-reject-invalid-npi.json`: file and process | **Rejected**: invalid NPI, CARC 16 with RARC N257 |
| 7 | provider1 | `07-duplicate-of-01.json`: file and process | **Rejected**: duplicate of claim 1, CARC 18 |
| 8 | provider2 | `08-scanned-clean.pdf`: **Read claim** (OCR, a few seconds) → the confidence column → process | **In review**; it waits in the queue |
| 9 | provider2 | `09-scanned-low-confidence.pdf`: **Read claim** → the mistyped NPI is highlighted → process | **Rejected** for a low-confidence field, never denied: CARC 16 with RARC MA130 |

Then:

- **reviewer1**: **Rule outcomes** lists claims 5, 6, 7 and 9 with their reasons and codes;
  **Claims** → `CLM-DEMO-03` → **Explanation** and **Audit trail** (time, event, who, versions).
- **provider2**: **My claims** → search `DEMO-08`, or filter by status.
- **admin**: **Overview** (demo data: final outcomes, queue by tier, decided by rules, accepted
  or overridden) → **Model metrics** (v1, v2 and E4B side by side) → **Audit lookup**
  `CLM-DEMO-03` → **System status**. Everything is read only; another role's page shows "You
  don't have access".

## If a step fails

| Symptom | Do |
|---|---|
| The login page comes back | The session ended (8 hours) or the API restarted with another `SECRET_KEY`: log in again |
| "Wrong username or password" | Use the password from `.env`; `make demo-users` resets the logins |
| "A claim with this claim ID is already on file" | The database was not reset: `make demo-reset`, then start again |
| "A service the API needs is not available" | Ollama is down: `make ollama-up`, then **Process claim** again |
| Processing takes over a minute | Ollama is loading the model; wait |
