.PHONY: dev stop logs logs-backend logs-worker logs-redis ps health clean build test

# ── One-command startup ──────────────────────────────────────────────
dev: ## Start all services (db, redis, backend, worker, frontend, prometheus, grafana)
	docker compose up --build -d
	@echo ""
	@echo "FairHire-AI is starting..."
	@echo "  Backend API:   http://localhost:8000"
	@echo "  Swagger UI:    http://localhost:8000/docs"
	@echo "  Frontend:      http://localhost:3000"
	@echo "  Prometheus:    http://localhost:9090"
	@echo "  Grafana:       http://localhost:3001  (admin/admin)"
	@echo ""
	@echo "Run 'make health' to verify all services are up."

# ── Build ────────────────────────────────────────────────────────────
build: ## Build all images without starting
	docker compose build

# ── Stop & cleanup ───────────────────────────────────────────────────
stop: ## Stop all services
	docker compose down

clean: ## Stop all services and remove volumes
	docker compose down -v

# ── Logs ─────────────────────────────────────────────────────────────
logs: ## Tail logs for all services
	docker compose logs -f

logs-backend: ## Tail backend logs
	docker compose logs -f backend

logs-worker: ## Tail worker logs
	docker compose logs -f worker

logs-redis: ## Tail redis logs
	docker compose logs -f redis

# ── Status ───────────────────────────────────────────────────────────
ps: ## Show running services
	docker compose ps

health: ## Run healthcheck script against the running stack
	python scripts/healthcheck.py

# ── Testing ──────────────────────────────────────────────────────────
test: ## Run backend tests locally (requires virtualenv)
	cd backend && python -m pytest tests/ -v

# ── Help ─────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
