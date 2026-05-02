# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

### Backend
```bash
# Local dev server (requires py313 venv: source ~/py313/bin/activate)
make dev                    # uvicorn on :8000 with --reload

# Tests (in-memory SQLite, no PG needed)
make test                   # cd backend && python -m pytest tests/ -v
cd backend && python -m pytest tests/test_tick_buffer.py -v   # single test file
cd backend && python -m pytest tests/test_tick_buffer.py::TestTickBuffer::test_add -v  # single test

# DB migrations
make migrate                # alembic upgrade head

# Deps live in backend/requirements.txt, installed in ~/py313 venv
```

### Frontend
```bash
make serve-frontend         # ng serve with proxy to localhost:8000
cd frontend && npm run test           # vitest run (single pass)
cd frontend && npm run test:watch     # vitest watch mode
make frontend-specs         # same as npm run test
```

### K8s / Deployment
```bash
make up                     # Tilt local K8s dev (microk8s, namespace: stock-radar)
make down                   # tear down Tilt
make tf-apply               # Terraform DB provisioning
make deploy-engine          # rsync backend to VPS + restart
```

## Architecture

### Backend (`backend/app/`)
- **Framework**: FastAPI + SQLAlchemy 2.0 + APScheduler + structlog
- **Entry point**: `app/main.py` — monolithic lifespan wires all services; runtime role (`all`|`web`|`worker`) controls which background jobs start
- **Config**: `app/core/config.py` — single `Settings` class via pydantic-settings, all config from env vars
- **Database**: PostgreSQL, schema `stock_radar` (all models use `__table_args__ = {"schema": "stock_radar"}`). Alembic in `backend/alembic/`

#### Key subsystems
- **Broker abstraction** (`app/broker/interface.py`): `BrokerInterface` ABC → `MockBroker` (dev) / `IBKRBroker` (prod via ib_insync)
- **Data pipeline** (`app/data/`): Polygon.io clients (REST/WebSocket), tick persistence, aggregate services, universe loader (S3 flatfiles)
- **Engine** (`app/engine/`): The trading pipeline — `TickBuffer` → `BreakoutEngine` / `L1FeatureEngine` → `SecretCandidateScorer` → `L2PromotionQueue` → `StateMachine` → `SignalDetector` → `TradeExecutor` (with `BuyAgent`/`SellAgent`, `EntryFormula`/`ExitFormula`, `ExecutionGate`)
- **Aggregate pipeline** (`app/engine/aggregate_*`): `AggregateTriggerEngine` → `AggregateValidationEngine` → `AggregateDecisionEngine`, refreshed by `AggregateRuntimeService`
- **Risk** (`app/risk/risk_manager.py`): Position sizing, daily loss limits
- **ML** (`app/ml/`): `BreakoutClassifier` (scikit-learn), `MLScorer`, `ModelTrainer` with periodic retraining
- **API** (`app/api/routes.py`): REST endpoints under `/api`, auth via JWT + API key (`app/core/auth.py`)
- **WebSocket** (`app/api/websocket.py`, `app/api/ws_manager.py`): Real-time signal/trade/L2 streaming, channels: `signals`, `trades`, `l1`, `l2`
- **Metrics**: Prometheus via `prometheus-fastapi-instrumentator`, custom metrics in `app/core/metrics.py`

### Frontend (`frontend/`)
- **Framework**: Angular 21 + NgRx + Material 3, zoneless change detection
- **Style**: SCSS, standalone components, OnPush strategy, `inject()`, signal `input()`/`output()`, `@if`/`@for` syntax
- **State**: NgRx with `+state/` folder convention per feature (actions, reducer, effects, state, providers)
- **Features**: dashboard, universe, trades, signals, analytics, settings, secret-sauce, state-monitor, aggregate-data, polygon-data
- **Testing**: Vitest (not Karma/Jasmine)
- **Proxy**: `proxy.conf.json` forwards `/api` → `localhost:8000`

### Infrastructure
- **K8s**: microk8s, Helm chart in `helm/stock-radar/` (subcharts for api, frontend, prometheus, grafana, redis)
- **Tilt**: `Tiltfile` for local K8s dev loop with hot reload
- **Terraform**: `terraform/database/` provisions PG database/schema/roles
- **Docker**: `Dockerfile_dev` (hot reload) and `Dockerfile_prod` for both backend and frontend
- **VPS**: `deploy/` dir with systemd services for ibgateway + trading-engine

## Conventions

- All SQLAlchemy models: `__table_args__ = {"schema": "stock_radar"}`
- Tests use in-memory SQLite with `ATTACH DATABASE` for schema translation (see `backend/tests/conftest.py`)
- Backend logging: structlog with dot-separated event keys (e.g., `scheduler.universe_refreshed`)
- Frontend NgRx: feature-scoped `+state/` directories, providers file for store registration
- PG connection: env vars `PGUSER`, `PGHOST`, `PGPORT`, `PGPASSWORD`, `PGDATABASE` (port 5434 locally)
