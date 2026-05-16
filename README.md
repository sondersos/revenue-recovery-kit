# revenue-recovery-kit

[![CI](https://github.com/sondersos/revenue-recovery-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/sondersos/revenue-recovery-kit/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-20-blue)](https://nodejs.org/)
[![Postgres](https://img.shields.io/badge/postgres-16-blue)](https://www.postgresql.org/)

An open-source, code-first revenue-recovery automation layer built on top of Go High Level (GHL).
The system that inspired this repo recovered approximately **$45,000** in a single engagement for a service agency by automatically re-sequencing overdue invoices, retrying failed recurring charges, and deduplicating a corrupted CRM contact list. This repo is a generalized, testable re-implementation of that work — clean Python, typed end-to-end, and ready to fork.

## What this is / what this is not

| This is | This is not |
|---|---|
| A code-first, version-controlled revenue-recovery backend | A no-code n8n-only solution |
| A FastAPI service you can unit-test and code-review | A white-label product for your clients |
| A learning artifact showing real production patterns | Production-ready on Day 1 (see roadmap) |
| Designed for service agencies tracking their own AR | Designed to be resold to end clients |

## The problem in one sentence

Service agencies lose four to six figures annually to invoices that never get a second nudge, failed recurring charges that nobody retried, and duplicate contacts that break every automation — see [docs/PROBLEM.md](docs/PROBLEM.md) for the full breakdown.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI + Pydantic v2 + pydantic-settings |
| ORM / migrations | SQLAlchemy 2 + Alembic |
| Database + Auth | Supabase (Postgres 16 + Auth + Row-Level Security) |
| Frontend | Next.js 14 (App Router) + Tremor + TailwindCSS |
| Insights | Anthropic Claude (Sonnet) via `anthropic` Python SDK |
| Email alerts | Resend |
| SMS alerts | Twilio |
| Workflow adapter | n8n (workflow JSON in `integrations/n8n/`) |
| Local dev | Docker Compose |

## Quick start

### Prerequisites

- Docker Desktop ≥ 25
- Git

### Run locally

```bash
git clone https://github.com/sondersos/revenue-recovery-kit.git
cd revenue-recovery-kit

# Copy and populate environment variables
cp .env.example .env
# Edit .env — add Supabase credentials, Anthropic key, etc.

# Boot the stack
docker compose up -d

# Apply migrations
make migrate

# Verify the API is healthy
curl http://localhost:8000/healthz
# → {"status":"ok","checks":{"db":"ok","anthropic":"ok"}}

# Open the dashboard
open http://localhost:3000
```

### Demo (no Supabase account needed)

```bash
# Seed the local DB with fixture data
make seed

# Run the end-to-end demo (generates a real Claude insight if ANTHROPIC_API_KEY is set)
make demo
```

## Performance

All hot-path queries run against 6 composite indexes (migration 0006). On a Docker Compose dev environment with a seeded 1k-contact, 1k-invoice database:

| Endpoint | p95 budget | measured |
|---|---|---|
| `GET /v1/detection/runs/latest` | 200ms | ~8ms |
| `GET /v1/insights/latest` | 200ms | ~6ms |
| `POST /v1/detection/run` (1k contacts) | 500ms | ~80ms |

See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for full EXPLAIN ANALYZE plans and load-test methodology.

## Observability

All backend logs are structured JSON (one object per line). Every request gets a correlation ID — either from the `X-Request-ID` header or generated as UUID4.

```bash
# Tail logs and filter by correlation ID
docker compose logs api -f | jq 'select(.correlation_id=="abc-123")'

# Watch Claude cost in real time
docker compose logs api -f | jq 'select(.message=="claude.response") | {cost: .claude_cost_usd, tokens: .claude_output_tokens}'
```

See [docs/adr/0007-observability.md](docs/adr/0007-observability.md) for the full observability design.

## Accessibility

The dashboard targets WCAG 2.1 AA. axe-core runs in CI against the login and dashboard pages. All interactive elements have visible `:focus-visible` rings and proper ARIA labels.

See [app/accessibility/page.tsx](frontend/app/accessibility/page.tsx) for the accessibility statement.

## Repo layout

```
revenue-recovery-kit/
├── backend/
│   ├── app/
│   │   ├── integrations/      # Anthropic, GHL, Resend, Twilio adapters
│   │   ├── middleware/        # RequestContextMiddleware, rate limiting
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── observability/     # Structured logging, correlation IDs
│   │   ├── routers/           # FastAPI route handlers
│   │   └── services/          # Detection engine, insights service, dedup
│   ├── alembic/               # Database migrations (0001–0006)
│   ├── tests/                 # pytest suite (63+ tests)
│   └── requirements.txt
├── frontend/
│   ├── app/                   # Next.js 14 App Router pages
│   ├── components/            # UI components (Server + Client)
│   ├── lib/                   # API clients, Supabase helpers, types
│   └── tests/                 # Vitest unit tests
├── docs/
│   ├── adr/                   # Architecture Decision Records (0001–0008)
│   ├── ARCHITECTURE.md
│   ├── PERFORMANCE.md
│   └── PROBLEM.md
├── scripts/
│   ├── demo.sh                # End-to-end demo with auto JWT mint
│   └── gen_demo_token.py      # JWT generator for demo/testing
├── .github/workflows/ci.yml   # CI: lint + test + build (7 jobs)
├── docker-compose.yml
└── Makefile
```

## Documentation

| Document | Description |
|---|---|
| [docs/PROBLEM.md](docs/PROBLEM.md) | The revenue-loss problem this system solves |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and data-flow diagrams |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Performance budgets, EXPLAIN ANALYZE plans, load-test results |
| [docs/adr/](docs/adr/) | All 8 Architecture Decision Records |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev environment setup and contribution guide |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev environment setup, branch protection rules, and pre-commit hook configuration.

## License

MIT — see [LICENSE](LICENSE).
