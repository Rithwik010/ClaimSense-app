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

A provider files and processes: **Submit claim** → Claim file → **Read claim** → **Process
claim**; the claim then shows on **My claims**. A reviewer reviews: **Review queue** → the claim
→ **Accept recommendation** (or **Override line**) → **Finalize claim**.

| # | Who | File and steps | Expected result |
|---|---|---|---|
| 1 | provider1 | `01-approve-quick.json`: file and process | My claims: **In review** |
|   | reviewer1 | Review queue → `CLM-DEMO-01` (quick tier) → click a criterion's quote → **Accept recommendation** → **Finalize claim** | **Approved**; provider1 now sees **Approved** too |
| 2 | provider1 | `02-pend-standard.json`: file and process | **In review** |
|   | reviewer1 | `CLM-DEMO-02` (standard tier) → **Accept recommendation** → **Finalize claim** | **Needs information** |
| 3 | provider1 | `03-deny-full-override.json`: file and process | **In review** |
|   | reviewer1 | `CLM-DEMO-03` (full tier; the model recommends Deny) → **Override line** → New decision Approve, a reason → **Override line** → **Finalize claim** | **Approved**, amounts recomputed |
| 4 | provider2 | `04-partial-ncci.json`: file and process | **In review** |
|   | reviewer1 | `CLM-DEMO-04`: line 2 denied by an NCCI rule (cannot be overridden) → **Accept recommendation** → **Finalize claim** | **Partly approved** |
| 5 | provider2 | `05-rule-deny-r15.json`: file and process | **Denied by a rule** at once: no review |
| 6 | provider2 | `06-reject-invalid-npi.json`: file and process | **Rejected**: invalid NPI |
| 7 | provider1 | `07-duplicate-of-01.json`: file and process | **Rejected**: duplicate of claim 1 |
| 8 | provider2 | `08-scanned-clean.pdf`: **Read claim** (OCR, a few seconds) → check Fields read → process | **In review**; reviewer1 sees it awaiting review |
| 9 | provider2 | `09-scanned-low-confidence.pdf`: **Read claim** → the mistyped NPI is highlighted → process | **Rejected** for a low-confidence field, never denied |

Then, as reviewer1: **Claims** → `CLM-DEMO-03` → **Explanation** and **Audit trail** tabs;
**Rule outcomes** lists claims 5, 6, 7 and 9, and their claim pages show the standard codes:
5 CARC 11 with RARC N115 and the billing article's LCD, 6 CARC 16 with N257, 7 CARC 18, 9 CARC 16
with MA130. As admin: **Metrics**; any page of another role shows "You don't have access".

## If a step fails

| Symptom | Do |
|---|---|
| The login page comes back | The session ended (8 hours) or the API restarted with another `SECRET_KEY`: log in again |
| "Wrong username or password" | Use the password from `.env`; `make demo-users` resets the logins |
| "A claim with this claim ID is already on file" | The database was not reset: `make demo-reset`, then start again |
| "A service the API needs is not available" | Ollama is down: `make ollama-up`, then **Process claim** again |
| Processing takes over a minute | Ollama is loading the model; wait |
