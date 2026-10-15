# ClaimSense demo run-sheet

Synthetic data only. The nine claims are in `demo/claims/`; run them in this order.

## Before

1. `make demo-reset` (clean database, demo logins, model loaded), then `make demo-up` in a
   second terminal. Both start Docker Desktop and `ollama serve` themselves if needed.
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
|   | reviewer1 | **Quick** tab → `CLM-DEMO-01`: the **Summary** tab on the right opens first → click a criterion's quote (the **Clinical note** tab opens at it) → **Accept all lines** → **Finalize claim** | **Approved**. provider1 → **My claims** → `CLM-DEMO-01`: **Claim approved** and the billing, with a sentence for each reduction |
| 2 | provider1 | `02-pend-standard.json`: file and process | **In review** |
| 3 | provider1 | `03-deny-full-override.json`: file and process | **In review** |
|   | reviewer1 | **Standard** tab → `CLM-DEMO-02` → **Accept all lines** → **Finalize claim** → **Next claim** | 2 **Pended**; **Next claim** opens `CLM-DEMO-03` |
|   | reviewer1 | `CLM-DEMO-03` (full tier; the model recommends Deny) → **Override line** → New decision Approve, a reason → **Override line** → **Finalize claim** | **Approved**, amounts recomputed |
| 4 | provider2 | `04-partial-ncci.json`: file and process | **In review** |
|   | reviewer1 | `CLM-DEMO-04`: line 2 denied by an NCCI rule, CARC 236 (cannot be overridden) → **Accept all lines** → **Finalize claim** | **Partly approved** |
| 5 | provider2 | `05-rule-deny-r15.json`: file and process → **Open claim result** | **Denied** at once: **Claim denied**, why in plain words, what to check, CARC 11, RARC N115, the billing article and its LCD |
| 6 | provider2 | `06-reject-invalid-npi.json`: file and process → **Open claim result** | **Rejected**: **Claim rejected**, the NPI that is not valid under **Please review the following details**, CARC 16 with RARC N257 |
| 7 | provider1 | `07-duplicate-of-01.json`: file and process | **Rejected**: duplicate of claim 1, CARC 18 |
| 8 | provider2 | `08-scanned-clean.pdf`: **Read claim** (OCR, a few seconds) → the confidence column → process | **In review**; it waits in the queue |
| 9 | provider2 | `09-scanned-low-confidence.pdf`: **Read claim** → the mistyped NPI is highlighted → process | **Rejected** for a low-confidence field, never denied: CARC 16 with RARC MA130 |

Then:

- **reviewer1**: **Returned and auto-denied** lists claims 5, 6, 7 and 9 with a one-line
  **Reason** (hover or focus it for every reason with its code and rule) and their codes;
  **Claims** → search by claim ID, member ID, provider name or NPI, or filter by status (the
  search and the filter stay in the address) → `CLM-DEMO-03` → **View original file** (the JSON
  as filed) → **Explanation** on the left; **Summary**, **Clinical note** and **Audit trail**
  (time, event, who, versions) on the right. `CLM-DEMO-08` → **View original file** shows the
  scanned PDF.
- **provider2**: **My claims** → search `DEMO-08`, or filter by status; `CLM-DEMO-04` shows
  **Claim partly approved**: why line 2 was not paid, and the billing of line 1.
- **admin**: **Overview** (demo data: final outcomes, queue by tier, decided by rules, accepted
  or overridden) → **Claims** (search and filter, read only) → **Model metrics** (v1, v2 and
  E4B side by side) → **Audit lookup** `CLM-DEMO-03` → **System status**. Everything is read
  only; another role's page shows "You don't have access".

A claim can also come as its form's two pages in two files (for example two scans, `page 1.png`
and `page 2.png`): choose or drop both on **Submit claim** (or **Add page 2 as another file**),
check that **Page 1** is the claim and **Page 2** the clinical note (**Swap pages** if not), then
**Read claim**. The claim page's **View original files** shows each file.

Before processing, a provider can **Check claim** (on Submit claim, or on an unprocessed claim's
page): the rules run as processing would run them and nothing is saved. The check says whether
the claim would be rejected, denied or put on hold and why, in plain words, and what each line's
coverage policy asks the clinical notes to show. For a claim read from a PDF or a scan, any box
read wrong has a **Correct** button: type the value as the form shows it (the dialog gives the
format), **Save correction**, and the check runs again. To show it, make a claim with a misread
NPI and file it as provider1:

    uv run python -m scripts.demo.claim_image --claim-id CLM-FIX-0001 --days 21 --format pdf \
        --misread billing_npi=1234567890 --out /tmp/claim-misread.pdf

**Check claim** says it would be rejected, with the billing NPI read as 1234567890 → **Correct
Billing NPI** → `2829620345` → **Save correction** → the check is ready, with the physical therapy
policy's criterion. Process it; once a reviewer finalizes it, the audit trail shows the correction
(before and after).

A decided claim has a **Patient EOB** button (provider, reviewer and admin): the patient's
explanation of benefits with each service, what the plan allowed and paid, what the patient may
owe, the deductible and out-of-pocket so far this year, and "This is not a bill." **Print** gives
black text on white. Try it on `CLM-DEMO-01` (approved) or `CLM-DEMO-04` (partly approved).

Every dashboard uses one set of status labels: In review, Approved, Partly approved (some lines
paid, some not), Pended, Denied, Rejected; reviewers and admins also see Not processed for a
claim filed but never processed (a provider sees it as In review).

## If a step fails

| Symptom | Do |
|---|---|
| The login page comes back | The session ended (8 hours) or the API restarted with another `SECRET_KEY`: log in again |
| "Wrong username or password" | Use the password from `.env`; `make demo-users` resets the logins |
| "A claim with this claim ID is already on file" | The database was not reset: `make demo-reset`, then start again |
| "A service the API needs is not available" | Ollama is down: `make ollama-up`, then **Process claim** again |
| Processing takes over a minute | Ollama is loading the model; wait |
