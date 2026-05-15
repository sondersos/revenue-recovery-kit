# revenue-recovery-kit

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
git clone https://github.com/sondersos/softwaredevelopement.git
cd softwaredevelopement

# Copy and populate environment variables
cp .env.example .env
# Edit .env — add Supabase credentials, Anthropic key, etc.

# Boot the stack
docker compose up -d

# Verify the API is healthy
curl http://localhost:8000/health
# → {"status":"healthy"}

# Open the dashboard
open http://localhost:3000
```

## Repo layout

```
revenue-recovery-kit/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── Dockerfile
│   ├── next.config.js
│   ├── package.json
│   └── tsconfig.json
├── infra/
├── integrations/
│   └── n8n/
├── docs/
│   ├── adr/
│   │   └── 0001-tech-stack.md
│   ├── ARCHITECTURE.md
│   └── PROBLEM.md
├── tests/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .env.example
├── docker-compose.yml
└── README.md
```

## Documentation

| Document | Description |
|---|---|
| [docs/PROBLEM.md](docs/PROBLEM.md) | The revenue-loss problem this system solves |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and data-flow diagrams |
| [docs/adr/0001-tech-stack.md](docs/adr/0001-tech-stack.md) | ADR: why this stack was chosen |

## Contributing

Open a PR against `main`. Please include tests for any application logic.

## License

MIT — see [LICENSE](LICENSE).
