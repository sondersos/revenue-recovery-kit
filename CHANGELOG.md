# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.0] — 2026-05-15

### Added
- **Structured JSON logging** — every backend log line is a JSON object with `timestamp`, `level`, `message`, `correlation_id`, `org_id`, `latency_ms` and more (ADR-0007, `python-json-logger`)
- **Correlation IDs** — `X-Request-ID` header echoed on every response; UUID4 generated if absent; stored in ContextVars so all downstream services inherit it without threading through signatures
- **`RequestContextMiddleware`** — logs `request.start` / `request.end` / `request.error` events with method, path, status, and latency for every HTTP call
- **6 performance indexes** (migration 0006) — `CREATE INDEX CONCURRENTLY` on `detection_runs`, `insights`, `detections`, `invoices`, `contacts` per ADR-0008
- **Rate limiting** via `slowapi` — 600 req/min default; tighter limits on `POST /v1/detection/run` (60/min), `POST /v1/insights` (30/min), `POST /v1/client-errors` (5/min)
- **`GET /healthz`** — deep health check that probes Postgres (`SELECT 1`) and Anthropic DNS; returns 503 on degradation
- **`POST /v1/client-errors`** — frontend error reporting endpoint; logs at WARNING level with client message and route; no stack in logs
- **`GET /v1/insights/cost-summary`** — aggregates `total_cost_usd`, `generation_count`, `avg_cost_usd`, and per-model breakdown, scoped by JWT org
- **Toast notifications** — `sonner` replaces inline alert divs in `RunScanButton`; `toast.success` shows cost on insight completion; `toast.error` on failure
- **Error boundaries** — `app/global-error.tsx` (full-page) and `app/dashboard/error.tsx` (per-route)
- **Loading skeletons** — `app/dashboard/loading.tsx` shows animated Skeleton cards while the dashboard fetches
- **Empty states** — all components show actionable empty states (InsightCard, TopDetectionsTable) with CTAs
- **`CostPill`** — Server Component in the dashboard footer showing total Claude spend and generation count
- **5 performance budget tests** (`tests/perf/`, tagged `@pytest.mark.perf`) — excluded from default run, opt-in with `pytest -m perf`
- **CI jobs expanded** — lint-backend (ruff + black), test-backend, build-backend, lint-frontend, test-frontend, build-frontend; manual `workflow_dispatch` for perf tests
- **`docs/PERFORMANCE.md`** — performance budgets, EXPLAIN ANALYZE plans, and load-test methodology
- **`docs/adr/0007-observability.md`** — structured logging ADR
- **`docs/adr/0008-performance-budgets.md`** — indexing strategy ADR
- **`CONTRIBUTING.md`** — dev environment setup, branch protection rules, pre-commit hooks, PR checklist
- **README badge row** — CI, license, Python, Node, Postgres badges
- **`scripts/loadtest.sh`** — Apache Bench smoke test for the three hot-path GET endpoints

### Changed
- `GET /healthz` replaces the old inline `/health` handler; `/health` still returns `{"status":"healthy"}` for backward compat
- `docker-compose.yml` API healthcheck now uses `python3 -c "urllib.request.urlopen(...)"` instead of `curl` (not available in `python:3.12-slim`)
- `alembic/env.py` — added `include_object` callback to skip index tracking in autogenerate (indexes managed via explicit migrations)

### Fixed
- **API container healthcheck** — `curl: not found` in `python:3.12-slim`; switched to stdlib `urllib.request`

---

## [0.4.1] — 2026-05-15

### Added
- Migration 0004 — drop duplicate named unique constraints on `contacts` and `invoices`
- Migration 0005 — enable RLS on `contacts`, `invoices`, `sequences`; all 6 user tables now tenant-isolated
- APScheduler concurrency guards in `worker.py` (`max_instances=1`, `misfire_grace_time=10`)
- JWT auto-mint in `scripts/demo.sh` from `SUPABASE_JWT_SECRET`; `scripts/gen_demo_token.py` helper

### Changed
- `alembic/env.py` — `transaction_per_migration=True` (enables per-migration transaction opt-out, prep for migration 0006)
- `.env.example` — `NEXT_PUBLIC_API_URL` renamed to `NEXT_PUBLIC_API_BASE_URL` to match frontend and CI

### Fixed
- `alembic check` failures — missing `sequence` + `detection` module imports in `env.py`
- `RunScanButton.test.tsx` — replaced broken inferred type expression with concrete `Insight` object

---

## [0.4.0] — 2026-05-14

### Added
- Next.js 14 dashboard with Tremor charts
- Supabase Auth end-to-end (httpOnly cookie, middleware redirect)
- JWT verification on FastAPI backend (`PyJWT`, HS256)
- 12+ tests across Vitest, pytest, Playwright

---

## [0.3.0] — 2026-05-13

### Added
- Detection engine (4 rules: `stalled_invoice`, `stale_lead`, `recovery_candidate`, `sequence_eligible`)
- Claude insights generation (`anthropic` SDK, structured JSON prompt, cost tracking)
- Migration 0003 (`detection_runs`, `detections`, `insights` tables + RLS)

---

## [0.2.0] — 2026-05-12

### Added
- Sequence engine + APScheduler background worker
- Resend (email) + Twilio (SMS) adapters
- GHL webhook ingestion with HMAC-SHA256 verification
- Migration 0002 (`sequences` table)

---

## [0.1.0] — 2026-05-11

### Added
- Initial schema (`contacts`, `invoices`) — migration 0001
- FastAPI scaffold with Pydantic v2 + pydantic-settings
- Docker Compose dev environment
- CI placeholder
