# FairHire-AI

AI-powered resume intelligence and hiring bias analysis platform. Built as a portfolio-grade, production-style system demonstrating engineering rigor, scalability, and modern Python/TypeScript best practices.

## Architecture

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│  Frontend   │────▶│  Backend   │────▶│ PostgreSQL │
│  Next.js    │     │  FastAPI   │     │            │
│  :3000      │     │  :8000     │     │  :5432     │
└────────────┘     └─────┬──────┘     └────────────┘
                         │
                    ┌────┴─────┐
                    │  Redis   │
                    │  :6379   │
                    └────┬─────┘
                         │
                   ┌─────┴──────┐
                   │  RQ Worker │
                   │  (async    │
                   │   analysis)│
                   └────────────┘

Observability:
  Prometheus  :9090   ──▶  Grafana  :3001
```

**Backend:** FastAPI, SQLAlchemy (async), PostgreSQL, Redis, RQ, sentence-transformers, structlog
**Frontend:** Next.js 14, React 18, TypeScript
**Infrastructure:** Docker Compose, Prometheus, Grafana

## Quick Start

### Prerequisites

- Docker and Docker Compose v2+
- Make (optional but recommended)

### One-command startup

```bash
make dev
```

This builds and starts all seven services in the background:

| Service    | URL                          | Purpose                        |
|------------|------------------------------|--------------------------------|
| Backend    | http://localhost:8000        | FastAPI REST API               |
| Swagger UI | http://localhost:8000/docs   | Interactive API documentation  |
| Frontend   | http://localhost:3000        | Next.js application            |
| Redis      | localhost:6379               | Cache + job queue broker       |
| PostgreSQL | localhost:5432               | Primary datastore              |
| Prometheus | http://localhost:9090        | Metrics collection             |
| Grafana    | http://localhost:3001        | Dashboards (admin/admin)       |

### Verify the stack

```bash
make health
```

Runs `scripts/healthcheck.py` which checks TCP connectivity (Postgres, Redis) and HTTP reachability (backend, frontend, Prometheus, Grafana) with automatic retries.

### Without Make

```bash
docker compose up --build -d
python scripts/healthcheck.py
```

## Makefile Reference

| Command         | Description                                     |
|-----------------|-------------------------------------------------|
| `make dev`      | Build and start all services                    |
| `make stop`     | Stop all services                               |
| `make clean`    | Stop all services and remove volumes            |
| `make build`    | Build images without starting                   |
| `make logs`     | Tail logs for all services                      |
| `make logs-backend` | Tail backend logs only                      |
| `make logs-worker`  | Tail worker logs only                        |
| `make logs-redis`   | Tail Redis logs only                         |
| `make ps`       | Show running containers                         |
| `make health`   | Run healthcheck against running stack           |
| `make test`     | Run backend tests locally (requires virtualenv) |

## Configuration

All backend settings are driven by environment variables. Defaults are defined in `backend/app/core/config.py` and can be overridden via `backend/.env`.

See `backend/.env.example` for documentation of all available settings.

### Key settings

| Variable                  | Default                    | Description                           |
|---------------------------|----------------------------|---------------------------------------|
| `DATABASE_URL`            | `postgresql+asyncpg://...` | Async PostgreSQL connection string    |
| `REDIS_URL`               | `redis://redis:6379/0`     | Redis connection string               |
| `SECRET_KEY`              | (change in production)     | JWT signing secret                    |
| `EMBEDDING_MODEL_NAME`    | `all-MiniLM-L6-v2`        | sentence-transformers model           |
| `QUEUE_NAME`              | `fairhire:analysis`        | RQ queue name                         |
| `LOG_FORMAT`              | `json`                     | `json` or `console`                   |

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/             # Route handlers
│   │   ├── core/            # Config, logging, security
│   │   ├── db/              # Database session and base
│   │   ├── middleware/       # Request logging middleware
│   │   ├── models/          # SQLAlchemy models
│   │   ├── queue/           # Async Redis connection manager
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Business logic (analysis, embeddings, etc.)
│   │   ├── storage/         # File uploads
│   │   └── workers/         # RQ worker, job handlers, queue helpers
│   ├── tests/               # pytest test suite
│   ├── Dockerfile           # Backend API image
│   ├── Dockerfile.worker    # RQ worker image
│   └── requirements.txt
├── frontend/
│   ├── src/                 # Next.js pages and components
│   ├── Dockerfile
│   └── package.json
├── infra/
│   └── prometheus.yml       # Prometheus scrape config
├── scripts/
│   └── healthcheck.py       # Stack healthcheck script
├── docker-compose.yml
├── Makefile
└── README.md
```

## Development

### Running tests

```bash
# Inside the backend directory (with virtualenv activated)
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v

# Or via Make
make test
```

### Viewing logs

```bash
# All services
make logs

# Specific service
make logs-backend
make logs-worker
```

### Rebuilding after code changes

Backend and worker containers mount `./backend/app` as a volume, so code changes to Python files are reflected immediately (uvicorn auto-reloads for the backend). For dependency changes:

```bash
make dev  # re-builds images
```

## Roadmap

- **Phase 1:** Foundation & Infrastructure ✅
- **Phase 2-3:** Embeddings, Async Queue, Observability ✅ (current)
- **Phase 4:** Multi-Tenant SaaS, RBAC, Organizations (planned)
