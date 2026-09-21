# ClaimSense — Setup (do this before Claude Code starts Phase 1)

Work through the parts in order. Parts A–C are done by **every team member** on their own
laptop. Parts D–G are done **once**, by one person, then everyone pulls the repo.

---

## Part A — Accounts

| ☐ | Account | Who | Notes |
|---|---|---|---|
| ☐ | GitHub account | Everyone | |
| ☐ | GitHub Student Developer Pack | Repo owner (at least) | Gives GitHub Pro, which is needed for branch protection on a **private** repo. Approval can take a few days. |
| ☐ | Hugging Face account + **read** access token | Training-machine owner | For downloading Gemma 4 weights. Accept model terms on the model page if asked. |
| ☐ | Kaggle and/or Google account | Training-machine owner | Backup GPU if the laptop can't train |
| ☐ | Claude Pro (one shared subscription) | One person | Share the login privately. Never put it in the repo. |

---

## Part B — Tools on every laptop

| ☐ | Tool | macOS | Windows | Linux (Ubuntu) |
|---|---|---|---|---|
| ☐ | Git | `xcode-select --install` or `brew install git` | git-scm.com installer | `sudo apt install git` |
| ☐ | GitHub CLI | `brew install gh` | `winget install --id GitHub.cli` | See cli.github.com |
| ☐ | uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` | same as macOS |
| ☐ | Python 3.11 (via uv) | `uv python install 3.11` | same | same |
| ☐ | Docker Desktop | docker.com installer | Run `wsl --install` first, restart, then the docker.com installer | Docker Engine + Compose plugin |
| ☐ | Ollama (v0.20.0 or later, needed for Gemma 4) | ollama.com installer | ollama.com installer | `curl -fsSL https://ollama.com/install.sh \| sh` |
| ☐ | Tesseract OCR | `brew install tesseract` | Windows installer (e.g. the UB Mannheim build); add its folder to `PATH` | `sudo apt install tesseract-ocr` |
| ☐ | VS Code | code.visualstudio.com | same | same |
| ☐ | Claude Code | Follow the official guide: https://docs.claude.com/en/docs/claude-code/overview | same | same |

Then log in to GitHub from the terminal:

```bash
gh auth login
gh auth refresh -s project      # lets gh manage project boards
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

---

## Part C — Training machine only

| ☐ | Step | Command / action |
|---|---|---|
| ☐ | NVIDIA: confirm driver and GPU | `nvidia-smi` shows your GPU and memory |
| ☐ | Apple Silicon: confirm memory | `system_profiler SPHardwareDataType` (16 GB+ recommended) |
| ☐ | Hugging Face CLI login | `uv tool install "huggingface_hub[cli]"` then `hf auth login` (older versions: `huggingface-cli login`) |
| ☐ | Note free disk space | Keep 60 GB+ free for weights, checkpoints and exports |

Do **not** install training libraries (Unsloth, torch, mlx-lm) yet. They are added to the
project's separate `train` dependency group in task P4.3, following Unsloth's install guide for
your OS and CUDA version (or `mlx-lm` on a Mac).

---

## Part D — Repository

If you already ran the Day 0 Claude Code prompt, the repo exists: skip to step 3.

1. Create a **private** GitHub repo named `claimsense`, add both teammates as collaborators.
2. Clone it:
   ```bash
   git clone https://github.com/<owner>/claimsense.git
   cd claimsense
   ```
3. Create a branch and add the project documents to the repo root:
   ```bash
   git checkout -b setup-docs
   # copy CLAUDE.md, INSTRUCTIONS.md, SETUP.md into the repo root
   mkdir -p data/curated confidential
   ```
4. Make sure `.gitignore` contains at least:
   ```gitignore
   __pycache__/
   *.pyc
   .venv/
   .env
   data/raw/
   data/generated/
   *.gguf
   *.safetensors
   models/
   outputs/
   checkpoints/
   confidential/
   .DS_Store
   .vscode/
   .idea/
   ```
5. Add these lines to the table in `DECISIONS.md`:
   ```markdown
   | 2026-09-21 | Rule failures are automatic: REJECT (return to provider), DENY (reason code) or PEND; no human edit review. A failure on a low-confidence field becomes REJECT, never DENY. | Rules are factual checks; avoids wrong denials from OCR errors |
   | 2026-09-21 | Every SLM recommendation is human-reviewed; review tier set by code from decision, complexity and amount | Compliance; task differentiation |
   | 2026-09-21 | Claim-level decision derived by code from line decisions (APPROVE / PEND / DENY / PARTIAL) | Fewer model errors |
   | 2026-09-21 | Pipeline is synchronous; Redis/RQ deferred to stretch | Simplicity for the prototype |
   | 2026-09-21 | COB default: traditional (secondary pays the lesser of its normal payment and the remaining balance) | Needs a defined rule for the calculator |
   | 2026-09-21 | INSTRUCTIONS.md v1.0 adopted as the implementation specification | Single source of truth |
   ```
   Remove the old open item about human review of rule failures.
6. Commit, push and open a pull request:
   ```bash
   git add .
   git commit -m "Add CLAUDE.md, INSTRUCTIONS.md, SETUP.md; record decisions"
   git push -u origin setup-docs
   gh pr create --fill
   ```
   A teammate reviews and merges it.
7. Once GitHub Pro is active: protect `main` (require a pull request, 1 approval, block force
   pushes). Required status checks are added after task P1.1 creates CI.

---

## Part E — Shared confidential folder (outside git)

Create a shared drive folder, restricted to the three of you, containing:
the Evernorth EDI claim guide, the Evernorth architecture document, AHM 250, and your CMS-1500
document. On laptops, keep local copies only in the repo's `confidential/` folder (gitignored).

---

## Part F — Model

On every laptop that will run the application:

```bash
ollama pull gemma4:e2b
ollama run gemma4:e2b "Reply with the single word: ready"
```

The pull is roughly 7 GB. Always use the explicit `:e2b` tag; the untagged name pulls E4B.

---

## Part G — Verify

Run these; every line must succeed before Phase 1 starts.

| ☐ | Command | Expect |
|---|---|---|
| ☐ | `git --version` | A version number |
| ☐ | `gh auth status` | Logged in |
| ☐ | `uv --version` | A version number |
| ☐ | `uv python find 3.11` | A path to Python 3.11 |
| ☐ | `docker compose version` | A version number |
| ☐ | `docker run --rm hello-world` | "Hello from Docker!" |
| ☐ | `ollama --version` | 0.20.0 or later |
| ☐ | `ollama list` | `gemma4:e2b` listed |
| ☐ | `tesseract --version` | A version number |
| ☐ | `claude --version` | A version number |
| ☐ | Training machine: `nvidia-smi` (NVIDIA) | GPU listed |

Record each laptop's GPU/VRAM, RAM and OS, and the chosen training and server machines, in
`DECISIONS.md` through a pull request.

---

## Part H — First Claude Code session

```bash
cd claimsense
git checkout main && git pull
claude
```

Inside Claude Code:

1. `/model` → choose **Sonnet**.
2. `/memory` → confirm `CLAUDE.md` is loaded.
3. Send:

```text
Do task P1.1. Read DECISIONS.md and INSTRUCTIONS.md sections 6, 7 and 11 (P1.1 only).
Restate the task and acceptance criteria, then show me your plan before making changes.
Work on branch p1.1-project-setup.
```

After the task report, review the pull request, merge it, and run `/clear` before starting P1.2.
