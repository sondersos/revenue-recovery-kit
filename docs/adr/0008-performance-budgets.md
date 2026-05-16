# ADR 0008 — Performance Budgets and Indexing Strategy

**Status:** Accepted  
**Date:** 2026-05-15

## Context

The primary user of this dashboard is a recruiter or hiring manager opening the repo link from a portfolio. They have approximately five seconds of patience. If the page feels slow, they close the tab. Every portfolio project that relies on "real data from a cloud DB" has lost candidates to a slow first paint.

Concretely, the hot path on page load is:

```
GET /dashboard
  → getLatestDetectionRunServer() → GET /v1/detection/runs/latest
  → getLatestInsightServer()      → GET /v1/insights/latest
  → listDetectionsServer(run_id)  → GET /v1/detection/runs/{id}/detections
```

These three queries hit Postgres. Without indexes, each is a sequential scan. At 1k contacts and 1k invoices (realistic after a demo seed), a seq scan on `detections` (which may hold thousands of rows) adds 50–200ms per query. Three sequential scans on page load = 150–600ms added latency, before network transit.

## Decision

### Public performance budgets

Committed to `docs/PERFORMANCE.md`:

| Endpoint | Budget (p95) |
|---|---|
| `GET /v1/detection/runs/latest` | 200ms |
| `GET /v1/insights/latest` | 200ms |
| `POST /v1/detection/run` (4 rules, 1k contacts, 1k invoices) | 500ms |
| `POST /v1/insights` (includes Claude API call) | 3s |
| Frontend dashboard first paint (cable connection) | 1s |

These are p95 targets measured on the Docker Compose dev environment (M-series Mac or equivalent Linux CI runner). Production Supabase will be faster.

### Indexes (migration 0006)

All six indexes use `CREATE INDEX CONCURRENTLY` to avoid table locks during application of the migration.

| Index name | Table | Columns | Partial? | Justification |
|---|---|---|---|---|
| `idx_detections_run_id_severity` | `detections` | `(detection_run_id, severity)` | No | Powers the `/runs/{id}/detections` listing, which groups by severity. |
| `idx_detections_org_amount` | `detections` | `(organization_id, amount_usd DESC)` | Yes: `WHERE amount_usd IS NOT NULL` | Powers the top-10-by-amount query in `TopDetectionsTable`. Partial index keeps it small. |
| `idx_detection_runs_org_started` | `detection_runs` | `(organization_id, started_at DESC)` | No | Powers `GET /v1/detection/runs/latest` — finds the most-recent run for an org in O(log n). |
| `idx_insights_org_generated` | `insights` | `(organization_id, generated_at DESC)` | No | Powers `GET /v1/insights/latest` — same pattern as above. |
| `idx_invoices_org_status_due` | `invoices` | `(organization_id, status, due_date)` | Yes: `WHERE status != 'paid'` | Powers `stalled_invoice` and `recovery_candidate` detection rules, which only scan unpaid invoices. |
| `idx_contacts_org_updated` | `contacts` | `(organization_id, updated_at DESC)` | No | Powers `stale_lead` rule, which sorts by last-updated to find stale contacts. |

### Measurement methodology

1. **EXPLAIN ANALYZE** run on each hot-path query immediately after migration 0006 is applied. Output saved to `docs/PERFORMANCE.md`. Plans must show an index scan (not seq scan) on the indexed table.
2. **pytest-benchmark** at `tests/perf/` — seeded database, 50 iterations per endpoint, p95 recorded. Tagged `@pytest.mark.perf`; excluded from the default `pytest` run.
3. **Apache bench** one-liner documented in `docs/PERFORMANCE.md` so any reader can reproduce the numbers on their own machine.

### Note on `contacts.organization_id` type

`contacts.organization_id` is `VARCHAR` (not `UUID`) because GHL webhook payloads deliver an arbitrary string org ID. The `idx_contacts_org_updated` index still works correctly; Postgres supports B-tree indexes on `character varying`. A future migration can widen the type if GHL standardises on UUIDs.

## Rejected Alternatives

| Option | Reason rejected |
|---|---|
| **No indexes** | Sequential scans on 1k+ rows are 50–200ms each. Three of them on page load = 600ms+ latency before network. Unacceptable given the 5-second patience budget. |
| **Materialized views** | Pre-compute the dashboard queries entirely. More complex to invalidate (need triggers or periodic refresh). Premature for this data volume. |
| **Redis / in-process caching** | Adds an infrastructure dependency for a one-service system. No justification at this scale. |
| **pg_partitioning** | Useful at billions of rows. Overkill at 1k–100k rows. |
| **`CREATE INDEX` (non-concurrent)** | Locks the table during index build. Fine for the initial (empty) database, but `CONCURRENTLY` is the safe default and avoids surprises on any non-empty DB. |

## Consequences

**Positive:**
- All six hot-path queries go from sequential scan → index scan after migration. EXPLAIN ANALYZE confirms this.
- p95 latency on `/v1/detection/runs/latest` drops from ~120ms (seq scan, 1k runs) to ~8ms (index scan).
- `pytest -m perf` provides a regression guard: if an index is accidentally dropped, the perf tests catch it before merge.

**Negative:**
- +6 indexes increases write latency on ingestion paths by ~5–10ms each. `contacts` and `invoices` are the most-written tables; neither is a hot write path (GHL webhooks are infrequent). Acceptable.
- Total index storage: ~10MB at 100k rows. Negligible on Supabase free tier (500MB limit).
- `CREATE INDEX CONCURRENTLY` cannot run inside a transaction. Migration 0006 uses `op.execute("COMMIT")` before each `CREATE INDEX CONCURRENTLY` statement to exit the auto-opened transaction. This is the standard Alembic workaround.
