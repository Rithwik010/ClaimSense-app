# ClaimSense local commands (D-UI-1). `make demo` starts the database containers, the API and the
# React web app together; Ctrl-C stops the API and the web app. Ollama runs natively: `make ollama-up`
# (part of demo, demo-up and demo-reset) starts `ollama serve` when it is not running.
# First time on a machine: `make setup`.
SHELL := /bin/bash
MODEL_NAME ?= claimsense-decision:v2
API_PORT ?= 8000
# No internet during a demo (D-PROC-4, `make offline-check`). No downloads: the embedding model is
# cached by setup (and the v2 lookup needs none); no Hugging Face, onnxruntime or Qdrant telemetry
# (app/rag/embedding.py sets ORT_DISABLE_TELEMETRY too; docker-compose.yml sets Qdrant's).
export HF_HUB_OFFLINE := 1
export HF_HUB_DISABLE_TELEMETRY := 1
export ORT_DISABLE_TELEMETRY := 1
export QDRANT__TELEMETRY_DISABLED := true

.PHONY: setup docker-running ollama-up demo demo-up demo-check demo-reset demo-claims demo-users e2e-api offline-check model-check results web-check smoke

setup: ## Python and web dependencies, database schema, reference data, policy collections
	uv sync
	cd frontend-web && npm ci
	docker compose up -d --wait
	uv run alembic upgrade head
	uv run python -m app.db.seed
	uv run python -m app.rag.knowledge

docker-running: ## stop at once, with a clear message, when Docker is not running
	@docker info >/dev/null 2>&1 || { echo "Start Docker Desktop, then run make $(or $(MAKECMDGOALS),demo-up) again"; exit 1; }

ollama-up: ## start `ollama serve` (models kept loaded, cloud features off) unless it is running
	uv run python -m scripts.demo.ollama_up

demo: docker-running ollama-up ## database containers, then the API (port $(API_PORT)) and the web app (port 5173)
	docker compose up -d --wait
	uv run alembic upgrade head
	@test -d frontend-web/node_modules || (cd frontend-web && npm ci)
	@echo "Dev server http://localhost:5173 (proxies the API on :$(API_PORT)) · model $(MODEL_NAME)"
	@trap 'kill 0' INT TERM EXIT; \
	MODEL_NAME=$(MODEL_NAME) uv run uvicorn app.api.main:app --port $(API_PORT) & \
	(cd frontend-web && npm run dev) & \
	wait

demo-up: docker-running ollama-up ## the demo: the API serves the production build of the web app on http://localhost:$(API_PORT) (D-AUTH-1); API log in data/generated/logs/api.log
	docker compose up -d --wait
	uv run alembic upgrade head
	@test -d frontend-web/node_modules || (cd frontend-web && npm ci)
	cd frontend-web && npm run build
	@mkdir -p data/generated/logs
	@echo "ClaimSense http://localhost:$(API_PORT) · model $(MODEL_NAME) · logins: docs/DEMO.md"
	MODEL_NAME=$(MODEL_NAME) uv run uvicorn app.api.main:app --port $(API_PORT) > data/generated/logs/api.log 2>&1

demo-check: ## OK/FAIL for Postgres, Ollama with the demo model loaded, the API, the web app and the demo logins
	MODEL_NAME=$(MODEL_NAME) uv run python -m scripts.demo.check

e2e-api: ## end-to-end check through the API alone; run right after demo-reset with the API up
	@mkdir -p data/generated/logs
	set -o pipefail; uv run python -m scripts.demo.e2e_api 2>&1 | tee data/generated/logs/e2e-api.log
	uv run python -m scripts.demo.e2e_api --privacy-only --log data/generated/logs/e2e-api.log \
		$(foreach log,$(wildcard data/generated/logs/api.log data/generated/logs/ollama.log $(HOME)/.ollama/logs/server.log),--log $(log))

offline-check: ## make e2e-api while recording every stack process's connections; any outside address fails
	uv run python -m scripts.verify.offline_check

model-check: ## the demo model in Ollama and the model its Modelfile builds, against the evaluated one
	MODEL_NAME=$(MODEL_NAME) uv run python -m scripts.verify.model_check

results: ## regenerate docs/results.md and data/generated/eval/results.json (P6.1)
	uv run python -m scripts.verify.results_report

demo-reset: docker-running ollama-up ## clean database (migrations, seeds, demo authorizations), Qdrant ready, demo model present
	docker compose up -d --wait
	MODEL_NAME=$(MODEL_NAME) uv run python -m scripts.demo.reset

demo-users: ## the demo logins (D-AUTH-1); passwords and SECRET_KEY in .env, written when missing
	uv run alembic upgrade head
	uv run python -m scripts.demo.users

demo-claims: ## rebuild demo/claims/ from the synthetic claim corpus
	uv run python -m scripts.demo.build_claims

web-check: ## what CI runs for the web app: install, lint, typecheck, unit tests, build
	cd frontend-web && npm ci && npm run lint && npm run typecheck && npm test && npm run build

smoke: ## Playwright smoke test against a running `make demo`
	cd frontend-web && npx playwright test
