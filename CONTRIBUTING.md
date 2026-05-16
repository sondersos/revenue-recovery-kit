# Contributing to revenue-recovery-kit

## Dev environment setup

### Prerequisites

- Docker Desktop ≥ 25
- Python 3.12 (for running `scripts/gen_demo_token.py` locally)
- Node.js 20 (for frontend development)
- Git

### First-time setup

```bash
git clone https://github.com/sondersos/revenue-recovery-kit.git
cd revenue-recovery-kit

# Populate environment variables
cp .env.example .env
# Required: SUPABASE_JWT_SECRET (any 32+ char string for local dev)
# Optional: ANTHROPIC_API_KEY, RESEND_API_KEY, TWILIO_* (needed for real sends)

# Start the full stack
make up

# Apply database migrations
make migrate

# Verify everything is healthy
curl http://localhost:8000/healthz
curl http://localhost:3000/api/health
```

### Running tests

```bash
# Backend (runs inside the api container)
make test-be
# → python -m pytest tests/ -q

# Frontend (runs on host)
make test-fe
# → npm test -- --run

# Both at once
make test

# Performance tests (opt-in, requires seeded data)
docker compose exec api python -m pytest tests/perf/ -m perf -q
```

### Database migrations

```bash
# Apply pending migrations
make migrate

# Create a new migration
docker compose exec api alembic revision --autogenerate -m "describe the change"

# Verify no schema drift
docker compose exec api alembic check
```

### Demo

```bash
# Seed fixture data and run the end-to-end pipeline
make seed
make demo

# To include a real Claude insight, set your key first:
ANTHROPIC_API_KEY=sk-ant-... make demo
```

## Branch protection

`main` is protected:

- PRs require **1 approval** before merge.
- All CI jobs must be green (lint-backend, test-backend, build-backend, lint-frontend, test-frontend, build-frontend).
- Direct pushes to `main` are not allowed (except for the repository owner during initial setup).

## Pre-commit hooks

Install [lefthook](https://github.com/evilmartians/lefthook) or [pre-commit](https://pre-commit.com/) to catch lint failures before they reach CI.

### lefthook (recommended)

```bash
brew install lefthook  # or: npm install -g @evilmartians/lefthook
lefthook install
```

The `lefthook.yml` in the root configures:
- `ruff check` + `black --check` on staged Python files
- `eslint` + TypeScript check on staged TypeScript files

### Manual lint

```bash
# Backend
cd backend && ruff check . && black --check .

# Frontend
cd frontend && npm run lint && npx tsc --noEmit
```

## Pull request checklist

- [ ] Tests added or updated for all application logic changes
- [ ] `alembic check` passes clean (no schema drift)
- [ ] `docker compose exec api python -m pytest tests/ -q` passes
- [ ] `cd frontend && npm test -- --run` passes
- [ ] `cd frontend && npm run build` succeeds with no TypeScript errors
- [ ] No `console.log` in committed frontend code
- [ ] No `session.commit()` inside service files (only at router/worker boundary)
- [ ] No secrets committed (check with `git diff --stat HEAD`)

## Code conventions

| Convention | Rule |
|---|---|
| Transaction boundary | `session.commit()` only at router, worker, or webhook handler. Never in service files. |
| Logging | Structured JSON via `logging.getLogger(__name__)` + `extra={}`. Never log JWTs, API keys, or full prompts. |
| Correlation IDs | Read from `app.observability.correlation` ContextVars — never thread through call signatures. |
| Auth | All non-public endpoints must have `Depends(get_current_user)`. |
| HMAC | Use `hmac.compare_digest` (not `==`) for signature verification. |
