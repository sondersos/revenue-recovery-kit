# ADR-0001: Technology Stack

**Date:** 2026-05-14
**Status:** Accepted
**Deciders:** Bayanda

---

## Context

This system needs to satisfy four constraints simultaneously:

1. **Testability.** The original implementation was pure n8n. n8n workflows cannot be unit-tested, cannot be code-reviewed meaningfully, and produce no artefacts a Python or TypeScript engineer can reason about in a PR. Any re-implementation must have a proper test harness.

2. **Portfolio legibility.** The primary audience is a senior engineer or technical hiring manager evaluating this repo as interview evidence. The stack must be immediately recognisable and the code must demonstrate professional engineering discipline — typed interfaces, schema migrations, separation of concerns.

3. **Local development parity.** The full stack must boot on a developer laptop with a single command and produce a working, inspectable system. This rules out architectures that require managed cloud services to function at all.

4. **Incremental build.** The implementation ships across a defined sprint (Days 1–7). The stack must support scaffolding on Day 1 and incremental feature addition on subsequent days without requiring architectural rewrites.

---

## Decision

### Backend language and framework: Python 3.12 + FastAPI

Python is the dominant language for data-adjacent backend work in 2026 and is universally readable by the target audience. FastAPI provides automatic OpenAPI documentation, first-class Pydantic integration, and native async support — all of which matter for a webhook-driven system.

**Rejected alternative — Flask:** Flask requires third-party libraries for async support, OpenAPI generation, and request validation. The resulting boilerplate obscures the domain logic and produces a weaker portfolio artefact. FastAPI's dependency injection model enables cleaner unit tests without patching global state.

### Data validation: Pydantic v2 + pydantic-settings

Pydantic v2 provides fast, typed data parsing for API request/response models and configuration alike. `pydantic-settings` manages environment variables with the same type safety, eliminating a class of runtime configuration errors that are common in dotenv-only setups.

### ORM and migrations: SQLAlchemy 2 + Alembic

SQLAlchemy 2 introduces a fully async-capable ORM with an explicit, composable query API. Alembic provides version-controlled schema migrations that can be code-reviewed, rolled back, and applied deterministically in CI. Together they make the database layer as auditable as the application code.

### Database and auth: Supabase (Postgres 16 + Auth + RLS)

Supabase provides a managed Postgres 16 instance with built-in Auth (JWT) and Row-Level Security. RLS allows multi-tenant isolation at the database level — a requirement for any system that might eventually serve more than one agency. The Supabase client libraries are mature, the local development story via Docker is solid, and Postgres is the most legible database choice for a senior technical audience.

**Rejected alternative — MongoDB:** MongoDB's flexible schema is a liability for financial data, where a missing field in a payment record is a silent bug rather than a schema violation. Postgres with a typed schema makes the domain model explicit and enforces data integrity at the storage layer. Row-Level Security is also significantly more mature in Postgres than in MongoDB's equivalent mechanisms.

### Frontend: Next.js 14 (App Router) + Tremor + TailwindCSS

Next.js 14 with the App Router is the current standard for production React applications and is familiar to the hiring-manager audience. Tremor provides pre-built chart and stat-card components designed specifically for dashboards, reducing the frontend implementation burden so the sprint can focus on backend logic. TailwindCSS provides layout and typography without requiring a global stylesheet.

### Insights layer: Anthropic Claude (Sonnet)

The Anthropic Python SDK provides a typed, well-documented interface to Claude. Claude Sonnet offers a strong balance of capability and cost for this use case: generating short prose summaries and next-action recommendations from structured payment history. The integration is intentionally thin — a single prompt call producing a stored result — so it can be tested with a mock client.

### Alerting: Resend (email) + Twilio (SMS)

Resend is purpose-built for transactional email with a simple HTTP API and a generous developer tier. Twilio is the industry standard for SMS with comprehensive Python SDK support. Separating email and SMS into distinct adapters means each can be mocked independently in unit tests.

### Workflow adapter: n8n

n8n workflow JSON is maintained in `integrations/n8n/` as a first-class citizen of the repo — committed, versioned, and linkable in pull requests. Operators who prefer a visual workflow layer can import these JSON files directly into their n8n instance. The Python backend is authoritative; n8n is an optional adapter, not the core.

**Rejected alternative — pure n8n as the core:** n8n cannot be unit-tested. Workflow logic lives in a visual graph that cannot be meaningfully diffed, code-reviewed, or probed by an interviewer. The original client implementation was pure n8n and produced a working system, but it cannot serve as portfolio evidence of engineering capability. A code-first Python core with an n8n adapter satisfies both the operational requirement and the portfolio requirement.

### Local development: Docker Compose

Docker Compose with three named services (`db`, `api`, `web`) provides a single-command local environment. The `db` service uses a named volume (`postgres_data`) so data persists across restarts. The `api` service depends on `db` with a health-check condition, ensuring the API does not start before Postgres is ready to accept connections.

### CI: GitHub Actions

A skeleton CI workflow is committed on Day 1. Real jobs (lint, type-check, test, build) are added on Day 6 once application code exists to check.

---

## Consequences

### Positive

- Every component boundary (webhook handler, dedup engine, sequence engine, insights layer) is a Python class or function testable with standard `pytest` patterns from Day 1.
- The stack is immediately legible to any senior Python or TypeScript engineer. No exotic dependencies, no vendor-specific DSLs in the hot path.
- Schema migrations are versioned in git. Rolling back a bad migration is `git revert` + `alembic downgrade`.
- The n8n adapter means the system can be operated by a non-developer without surrendering the code-first benefits.

### Trade-offs

- Python 3.12 + FastAPI + Supabase is a more complex local setup than a single-file Flask app. The Docker Compose layer absorbs most of this complexity.
- Tremor + TailwindCSS requires a build step. The web container handles this inside Docker; developers do not need a local Node.js installation.
- Claude API calls in the insights layer are not free. In production the insights endpoint should be rate-limited and the results cached. This is a Day-6 concern.

---

## Decision Summary Table

| Concern | Decision | Rejected alternative |
|---|---|---|
| Backend language | Python 3.12 | Go, Node.js |
| Backend framework | FastAPI | Flask |
| Data validation | Pydantic v2 + pydantic-settings | marshmallow, attrs |
| ORM | SQLAlchemy 2 | Django ORM, raw psycopg |
| Migrations | Alembic | Flyway, manual SQL |
| Database | Postgres 16 (Supabase) | MongoDB |
| Auth + RLS | Supabase Auth | Auth0, custom JWT |
| Frontend | Next.js 14 (App Router) | Remix, SvelteKit |
| UI components | Tremor + TailwindCSS | MUI, Chakra UI |
| Insights | Anthropic Claude Sonnet | OpenAI GPT-4o |
| Email alerting | Resend | SendGrid |
| SMS alerting | Twilio | Vonage |
| Workflow adapter | n8n | Temporal, custom scheduler |
| Core implementation | Code-first Python | Pure n8n |
| Local dev | Docker Compose | Tilt, Skaffold |
| CI | GitHub Actions | CircleCI, Buildkite |
