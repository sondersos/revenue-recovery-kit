# Performance

## Budgets

All p95 targets are measured in the Docker Compose dev environment (Apple M-series or equivalent Linux CI runner). Production Supabase will be faster due to connection pooling and co-location.

| Endpoint | p95 budget | Measured (dev DB) | Notes |
|---|---|---|---|
| `GET /v1/detection/runs/latest` | 200ms | < 5ms | 204 on empty DB |
| `GET /v1/insights/latest` | 200ms | < 5ms | 204 on empty DB |
| `GET /v1/insights/cost-summary` | 100ms | < 5ms | aggregation on empty DB |
| `POST /v1/detection/run` (4 rules) | 500ms | p95 ≈ 80ms | empty DB; scales with row count |
| `POST /v1/insights` | 3s | N/A | dominated by Claude API RTT |
| Frontend dashboard first paint | 1s | N/A | Next.js SSR + Supabase session |

Numbers captured via `pytest tests/perf/ -m perf -q -s` (50 iterations for GET endpoints, 20 for POST).

## Indexes (migration 0006)

Six composite indexes added via `CREATE INDEX CONCURRENTLY`. The CONCURRENTLY keyword avoids table locks during index builds on live databases.

| Index | Table | Columns | Partial? | Powers |
|---|---|---|---|---|
| `idx_detection_runs_org_started` | `detection_runs` | `(organization_id, started_at DESC)` | No | `GET /v1/detection/runs/latest` |
| `idx_insights_org_generated` | `insights` | `(organization_id, generated_at DESC)` | No | `GET /v1/insights/latest` |
| `idx_detections_run_amount` | `detections` | `(detection_run_id, amount_usd DESC NULLS LAST)` | No | `/runs/{id}/detections` sorted list |
| `idx_detections_org_amount` | `detections` | `(organization_id, amount_usd DESC)` | Yes (`amount_usd IS NOT NULL`) | Top-10 by amount query |
| `idx_invoices_status_created` | `invoices` | `(status, created_at)` | Yes (`status != 'paid'`) | `stalled_invoice` + `recovery_candidate` rules |
| `idx_contacts_updated` | `contacts` | `(updated_at DESC)` | No | `stale_lead` rule |

## EXPLAIN ANALYZE plans

Plans captured on the dev database (56 detection_run rows, 0 insight rows). The planner uses Seq Scan at this scale — index scans kick in at ~200+ matching rows. Both plans confirm sub-millisecond execution time.

### GET /v1/detection/runs/latest

```
Limit  (cost=1.71..1.72 rows=1 width=97) (actual time=0.060..0.061 rows=1 loops=1)
  -> Sort  (cost=1.71..1.72 rows=1 width=97) (actual time=0.060..0.060 rows=1 loops=1)
        Sort Key: started_at DESC
        Sort Method: quicksort  Memory: 25kB
        -> Seq Scan on detection_runs  (cost=0.00..1.70 rows=1 width=97)
                                       (actual time=0.028..0.029 rows=1 loops=1)
              Filter: (organization_id = '<org_uuid>'::uuid)
              Rows Removed by Filter: 55
Planning Time: 1.023 ms
Execution Time: 0.132 ms
```

**Interpretation:** Planner chooses Seq Scan correctly for 56 rows (index overhead exceeds sequential cost). At 200+ rows, `idx_detection_runs_org_started` reduces this to an Index Scan with O(log n) cost.

### GET /v1/insights/latest

```
Limit  (cost=0.15..6.17 rows=1 width=174) (actual time=0.023..0.023 rows=0 loops=1)
  -> Index Scan using idx_insights_org_generated on insights
                         (cost=0.15..12.18 rows=2 width=174)
                         (actual time=0.022..0.022 rows=0 loops=1)
       Index Cond: (organization_id = '<org_uuid>'::uuid)
Planning Time: 0.497 ms
Execution Time: 0.051 ms
```

**Interpretation:** `idx_insights_org_generated` is used from the first row. This query will not regress as the insights table grows.

## How we measured

### Unit-level perf (pytest-benchmark-style)

```bash
# From inside the repo
docker compose exec api python -m pytest tests/perf/ -m perf -q -s
```

This runs the endpoint 50× (GET) or 20× (POST) via `httpx.AsyncClient` against the in-process FastAPI app and computes p95.

### Load smoke test (Apache bench)

First generate a demo JWT:

```bash
export TOKEN=$(python3 scripts/gen_demo_token.py)
```

Then:

```bash
# Requires: apt install apache2-utils  OR  brew install ab
ab -n 1000 -c 20 \
   -H "Authorization: Bearer $TOKEN" \
   http://localhost:8000/v1/detection/runs/latest
```

Record p50, p95, p99 from the `ab` output and compare against the budget table above.

### Reproducing on a seeded database

```bash
# Seed 1k contacts + 1k invoices
make seed

# Re-run perf tests against the seeded DB
docker compose exec api python -m pytest tests/perf/ -m perf -q -s
```

With seeded data, the planner will switch from Seq Scan to `idx_detection_runs_org_started` for queries that match 200+ rows in the org.
