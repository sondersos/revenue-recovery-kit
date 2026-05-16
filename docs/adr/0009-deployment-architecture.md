# ADR 0009 — Deployment Architecture

**Status:** Accepted  
**Date:** 2026-05-16

## Context

The system needs a live URL accessible from any device for portfolio demos and interviews. Constraints:

- Total monthly cost must be $0 (free-tier only) for an idle portfolio project.
- Backend is a stateless FastAPI container — all state lives in Supabase.
- Frontend is Next.js 14 with Server Components and a few client-side interactive points.
- The local dev stack already uses Docker Compose, so the backend image is already containerized.

## Decision

| Layer | Platform | Rationale |
|---|---|---|
| Frontend | **Vercel** | Native Next.js support, automatic preview deploys from GitHub, generous free tier, zero config for App Router. |
| Backend | **Fly.io** | Native Docker support, free tier covers one always-on small VM (`shared-cpu-1x`, 256 MB RAM), global anycast routing, `fly secrets` for env var management. Healthcheck at `/healthz` drives auto-restart. |
| Database + Auth | **Supabase** | Already decided in ADR 0001 and ADR 0006. The live project (`lxkgpytiualvxjsnslzk.supabase.co`) runs migrations 0001–0006 and holds 1k seeded contacts + invoices. |
| DNS | *.vercel.app + *.fly.dev | No custom domain for now — keeps infra at $0/month. Day 7 (optional) adds a custom domain. |

## Alternatives considered

- **Railway**: simpler DX than Fly.io but the free tier is credit-limited and time-boxed — unsuitable for a persistent demo.
- **Render**: free tier exists but cold starts on the free web service can exceed 30 seconds, which is unacceptable for an interview demo.
- **Fly.io auto-stop machines**: enabled (`min_machines_running = 0`). First request after idle wakes the VM in ~2–3 seconds. Acceptable for portfolio use; documented in README.

## Consequences

- **Cost**: $0/month at idle. Supabase free tier pauses the database after 1 week of inactivity — recovery is one click in the dashboard. Documented in README and CHANGELOG.
- **Latency**: Fly.io → Supabase round-trip adds ~5 ms (same AWS region). Acceptable given our p95 budget of 500 ms for the hot path.
- **Secrets management**: all secrets live in `fly secrets` (backend) and Vercel environment variables (frontend). Nothing is committed to the repo.
- **CORS**: `FRONTEND_ORIGIN` secret on Fly.io must be updated to the Vercel URL after Phase E. The `CORSMiddleware` in `app/main.py` reads this value at startup.
- **JWT flow**: Supabase Auth issues JWTs signed with `SUPABASE_JWT_SECRET`. The Fly.io backend verifies them using the same secret (set via `fly secrets`). `organization_id` is read from `app_metadata` first, then `user_metadata` as a fallback (ADR follows jwt.py implementation).
