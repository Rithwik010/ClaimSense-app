# ClaimSense — Decision log

Decisions made after `INSTRUCTIONS.md` was written. Where they differ, this file wins.
Add rows only for decisions the team has made.

| Date | Decision | Reason |
|---|---|---|
| 2026-09-21 | Rule failures are automatic: REJECT (return to provider), DENY (reason code) or PEND; no human edit review. A failure on a low-confidence field becomes REJECT, never DENY. | Rules are factual checks; avoids wrong denials from OCR errors |
| 2026-09-21 | Every SLM recommendation is human-reviewed; review tier set by code from decision, complexity and amount | Compliance; task differentiation |
| 2026-09-21 | Claim-level decision derived by code from line decisions (APPROVE / PEND / DENY / PARTIAL) | Fewer model errors |
| 2026-09-21 | Pipeline is synchronous; Redis/RQ deferred to stretch | Simplicity for the prototype |
| 2026-09-21 | COB default: traditional (secondary pays the lesser of its normal payment and the remaining balance) | Needs a defined rule for the calculator |
| 2026-09-21 | INSTRUCTIONS.md v1.0 adopted as the implementation specification | Single source of truth |
| 2026-09-21 | No pull requests. Each task is built on a local `p<phase>.<task>` branch, merged into `main` locally, and pushed only when a team member says so. Overrides H13 and the pull-request steps in §11, §12 and §14. | Team reviews changes together before pushing |
| 2026-09-21 | Laptop (Manideep3183): Apple M5, 16 GB RAM, macOS, no NVIDIA GPU. Training and server machines to be decided. | Hardware record (SETUP Part G) |
