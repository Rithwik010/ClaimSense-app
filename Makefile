# ClaimSense local commands (D-UI-1). `make demo` starts the database containers, the API and the
# React web app together; Ctrl-C stops the API and the web app. Ollama runs natively (`ollama serve`).
# First time on a machine: `make setup`.
SHELL := /bin/bash
MODEL_NAME ?= claimsense-decision:v2
API_PORT ?= 8000
# No downloads during a demo: the embedding model is cached by setup (and the v2 lookup needs none).
export HF_HUB_OFFLINE := 1

.PHONY: setup demo demo-up demo-check demo-reset demo-claims demo-video e2e-api results web-check smoke

setup: ## Python and web dependencies, database schema, reference data, policy collections
	uv sync
	cd frontend-web && npm ci
	docker compose up -d --wait
	uv run alembic upgrade head
	uv run python -m app.db.seed
	uv run python -m app.rag.knowledge

demo: ## database containers, then the API (port $(API_PORT)) and the web app (port 5173)
	docker compose up -d --wait
	uv run alembic upgrade head
	@test -d frontend-web/node_modules || (cd frontend-web && npm ci)
	@curl -sf http://localhost:11434/api/version >/dev/null || echo "Ollama is not running: start it with 'ollama serve'."
	@echo "Web app http://localhost:5173 · API http://localhost:$(API_PORT)/docs · model $(MODEL_NAME)"
	@trap 'kill 0' INT TERM EXIT; \
	MODEL_NAME=$(MODEL_NAME) uv run uvicorn app.api.main:app --port $(API_PORT) & \
	(cd frontend-web && npm run dev) & \
	wait

demo-up: ## like demo, but the web app is the production build (vite preview); API log in data/generated/logs/api.log
	docker compose up -d --wait
	uv run alembic upgrade head
	@test -d frontend-web/node_modules || (cd frontend-web && npm ci)
	cd frontend-web && npm run build
	@mkdir -p data/generated/logs
	@echo "Web app http://localhost:5173 · API http://localhost:$(API_PORT)/docs · model $(MODEL_NAME)"
	@trap 'kill 0' INT TERM EXIT; \
	MODEL_NAME=$(MODEL_NAME) uv run uvicorn app.api.main:app --port $(API_PORT) > data/generated/logs/api.log 2>&1 & \
	(cd frontend-web && npx vite preview --port 5173 --strictPort) & \
	wait

demo-check: ## OK/FAIL for Postgres, Ollama with the demo model loaded, the API and the web app
	MODEL_NAME=$(MODEL_NAME) uv run python -m scripts.demo.check

e2e-api: ## end-to-end check through the API alone; run right after demo-reset with the API up
	@mkdir -p data/generated/logs
	set -o pipefail; uv run python -m scripts.demo.e2e_api 2>&1 | tee data/generated/logs/e2e-api.log
	uv run python -m scripts.demo.e2e_api --privacy-only --log data/generated/logs/e2e-api.log \
		$(if $(wildcard data/generated/logs/api.log),--log data/generated/logs/api.log,)

results: ## regenerate docs/results.md and data/generated/eval/results.json (P6.1)
	uv run python -m scripts.verify.results_report

demo-reset: ## clean database (migrations, seeds, demo authorizations), Qdrant ready, demo model present
	docker compose up -d --wait
	MODEL_NAME=$(MODEL_NAME) uv run python -m scripts.demo.reset

demo-claims: ## rebuild demo/claims/ from the synthetic claim corpus
	uv run python -m scripts.demo.build_claims

demo-video: demo-reset ## backup video of docs/DEMO.md (needs `make demo` running), then a reset
	cd frontend-web && DEMO_VIDEO=1 npx playwright test e2e/demo-runbook.spec.ts
	mkdir -p demo-video && cp "$$(ls -t frontend-web/test-results/*/video.webm | head -1)" demo-video/demo.webm
	@echo "Backup video: demo-video/demo.webm"
	$(MAKE) demo-reset  # a recording never leaves the database full

web-check: ## what CI runs for the web app: install, lint, typecheck, unit tests, build
	cd frontend-web && npm ci && npm run lint && npm run typecheck && npm test && npm run build

smoke: ## Playwright smoke test against a running `make demo`
	cd frontend-web && npx playwright test
