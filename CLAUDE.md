# ClaimSense — rules for Claude Code

ClaimSense: CMS-1500 claims → deterministic rules → fine-tuned Gemma 4 SLM recommendation
→ deterministic calculator → explanation → human review → audit. Synthetic data only.

## Before every task
- Read `DECISIONS.md` and the sections of `INSTRUCTIONS.md` referenced by the task ID (e.g. P2.3).
  Read only the relevant sections, not the whole file.
- If the request, `INSTRUCTIONS.md` and `DECISIONS.md` disagree: stop and ask.

## Hard rules
- The SLM never produces dollar amounts; only `app/calculator` does.
- Money = integer cents; percentages = integer basis points. No floats for money.
- `app/rules` and `app/calculator` must not import `app/ml`, `app/rag`, or model libraries.
- Every SLM recommendation goes to human review. Rule failures are automatic
  (REJECT / DENY / PEND); a failure on a low-confidence field is REJECT, never DENY.
- Never invent codes, clinical criteria or CARC mappings: codes come only from `data/raw/`;
  every criterion and CARC/RARC mapping cites its source in `data/raw/`. Plan and benefit
  values in `data/curated/` are fictional and synthesized (see `DECISIONS.md`).
- No external model APIs. Inference runs locally via Ollama only.
- Synthetic data only. Never commit `data/raw/`, `data/generated/`, `confidential/`,
  model weights, `.env`, or secrets. Never copy AMA CPT descriptor text.
- CPT text reproduced in CMS manuals (code descriptors, modifier definitions) counts as AMA text;
  paraphrase it and cite the page.
- `app/domain/contracts.py` is frozen: propose changes, don't make them.
- Golden test expected values are synthesized before the code they test, with worked steps,
  and spot-checked by the team. Never change them to make a test pass.
- No new dependencies without approval. No pull requests: commit to `main` and push only
  when a team member says so.
- Explanations are built from the decision record, never from model free text.

## Frontend (`frontend-web/`)
- React + Vite + TypeScript, shadcn/ui (Radix), Tailwind v4, TanStack Query, Motion; light theme only (D-UI-1, D-UI-2).
- Follow `DESIGN.md` (tokens, type, spacing, components, motion, breakpoints); it wins over the
  `frontend-design` project skill where they differ.
- Talks only to the API on its own origin (the Vite dev proxy, or the API serving the build in
  `make demo-up`; D-AUTH-1); never imports app code or touches the database.
  The UI computes no amounts and no decisions: it formats what the API returns.
- Add components with `npx shadcn@latest add <name>`; pin every npm package to an exact version at
  least two weeks old.
- Colour only for decisions (text + icon on a tint, never colour alone); borders, not shadows;
  sentence case; buttons say what happens; motion only for the four moments in `DESIGN.md`.
- Before calling UI work done: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`,
  the Playwright smoke test, and a look at every page at 390, 768 and 1440 px.

## Workflow
- Plan first for changes touching more than 2 files; wait for approval.
- Tests first for rules, calculator and validators.
- Before finishing: `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run pytest`, `uv run lint-imports` must all pass.
- Before any merge, run the full suite locally with data/raw present, and report both the local and the CI counts.
- Branch: `p<phase>.<task>-<short-name>`. One task per session.
- End with the task report format from `INSTRUCTIONS.md` §12.
- Stop-and-ask triggers: `INSTRUCTIONS.md` §13.
- Any code that produces data or report numbers must live under scripts/ and be committed; never keep it only in the session scratchpad.
