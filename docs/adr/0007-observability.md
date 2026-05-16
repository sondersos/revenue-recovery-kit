# ADR 0007 — Observability: Structured JSON Logs with Correlation IDs

**Status:** Accepted  
**Date:** 2026-05-15

## Context

revenue-recovery-kit processes GHL webhooks, calls Claude, dispatches Resend/Twilio, and returns responses to the Next.js dashboard — all without a human in the loop. When something goes wrong in production, there is no SSH access to a running container: the only window into the system is its log output and the response headers it echoes.

We need:

1. The ability to trace a single user action (click "Run Scan" → `POST /v1/detection/run` → detection engine → `POST /v1/insights` → Claude → dashboard refresh) without correlating timestamps by eye.
2. The ability to answer "did this org's request fail?" without grepping through noisy text.
3. The ability to measure cost and latency for the Claude calls that dominate the variable bill.
4. All of the above at **$0/month** — no paid log aggregator.

## Decision

### Log format

All backend logs are JSON, one object per line. Every line includes:

| Field | Type | Always present? |
|---|---|---|
| `timestamp` | ISO 8601 UTC (`2026-05-15T14:32:01.123Z`) | ✅ |
| `level` | `DEBUG \| INFO \| WARNING \| ERROR \| CRITICAL` | ✅ |
| `message` | human-readable summary | ✅ |
| `correlation_id` | UUID4 or echoed `X-Request-ID` | ✅ |
| `route` | URL path | ✅ on request/response lines |
| `method` | HTTP verb | ✅ on request/response lines |
| `status` | HTTP status code | ✅ on response lines |
| `latency_ms` | integer milliseconds | ✅ on response lines |
| `org_id` | JWT `organization_id` claim | when authenticated |
| `user_id` | JWT `sub` claim | when authenticated |
| `detection_run_id` | UUID | when in detection context |
| `insight_id` | UUID | when in insight context |
| `claude_model` | string | on Claude calls |
| `claude_input_tokens` | int | on Claude response |
| `claude_output_tokens` | int | on Claude response |
| `claude_cost_usd` | Decimal (4dp) | on Claude response |

### Correlation ID lifecycle

1. `RequestContextMiddleware` runs **first** in the middleware stack.
2. On entry: reads `X-Request-ID` header; falls back to `uuid4()`.
3. Stores it in a `ContextVar[str]` named `correlation_id`.
4. Echoes it as `X-Request-ID` in **every response** header.
5. All downstream code (services, adapters) reads from the ContextVar — no threading through call signatures.

### Sensitive data policy

| What | Rule |
|---|---|
| JWT tokens | Never log. Log `Bearer ***` presence check only. |
| API keys (Anthropic, Resend, Twilio, GHL) | Never log. |
| Full Claude prompt / response | Never log. Log `prompt_hash` (SHA256 of first 64 bytes, hex prefix 12 chars) and token counts. |
| Email body | Never log. Log `to_email` domain only (everything after `@`). |
| Phone numbers | Never log. Log last-4 digits only. |
| Contact PII | Never log full name in INFO+. DEBUG only, redacted in production. |

### Frontend errors

Client-side JavaScript errors are routed to `POST /v1/client-errors`:

```json
{ "message": "...", "stack": "...", "route": "/dashboard" }
```

The endpoint:
- Rate-limited to **5 requests/min/IP** (slowapi).
- Logs at `WARNING` with prefix `client.error`.
- Returns `204 No Content`.
- Never logs the full stack trace at `ERROR` level (noisy for network timeouts).

### Implementation libraries

| Library | Version | Role |
|---|---|---|
| `python-json-logger` | `2.0.7` | JSON log formatter |
| `contextvars` (stdlib) | — | Correlation ID storage |

## Rejected Alternatives

| Option | Reason rejected |
|---|---|
| **Plain text logs** | Ungreppable at scale. `grep correlation_id` on JSON takes 1 line; on free-form text it's regex archaeology. |
| **Sentry** | Costs money and requires account setup. Free tier is 5k events/month — easy to blow through on load tests. |
| **Datadog / New Relic** | Cost > $0. Overkill for a single-service portfolio project. |
| **OpenTelemetry** | Significant boilerplate (exporters, collectors, spans). The one-service architecture doesn't justify distributed tracing complexity. Reserve for when we add a second service. |
| **Structlog** | More idiomatic Python but requires the team to learn a non-stdlib API. `python-json-logger` wraps stdlib `logging` so all existing `logging.getLogger()` calls continue to work with zero changes. |

## Consequences

**Positive:**
- `docker compose logs api | jq 'select(.correlation_id=="abc")' ` is the primary debug tool. No external account needed.
- Correlation IDs surface in client-side error reports when the frontend includes `X-Request-ID` in its `apiFetch` calls, closing the browser → backend tracing gap.
- Future migration to a paid aggregator is `docker run vector` or `docker run fluentd` away — no code changes required.
- Claude cost tracking is automatic and queryable via `jq`.

**Negative:**
- Log volume roughly doubles vs. plain text (JSON overhead per field name). Acceptable: at 1k requests/day the volume is negligible.
- Developer must remember to pass `extra={}` to all `logger` calls to get fields into the JSON. Enforced by team convention and code review, not a linter.
