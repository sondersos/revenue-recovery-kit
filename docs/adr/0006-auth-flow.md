# ADR-0006: Authentication — Supabase Auth with JWT Pass-Through to FastAPI

**Date:** 2026-05-15
**Status:** Accepted
**Deciders:** Bayanda

---

## Context

The dashboard must be protected: only authenticated users belonging to a specific organisation should see or trigger recovery operations. Two constraints drive the design:

1. **Multi-tenant isolation.** Every database row is scoped to an `organization_id`. The API must enforce this at the application layer; the database enforces it at the RLS layer. Trusting the frontend to supply the correct `organization_id` is not acceptable for a public repo.
2. **No custom auth system.** Building JWT issuance, session management, and password reset from scratch for a portfolio project is out of scope. The chosen solution must be operationally trivial.

---

## Decision

### Identity provider

**Supabase Auth.** Handles signup, login, password reset, OAuth providers, session management, and token rotation. The free tier covers 50 K monthly active users. No additional vendor beyond Supabase (already required for the database).

### Session storage

**httpOnly cookie via `@supabase/ssr`.** The `@supabase/ssr` package provides helpers for Next.js App Router that store the Supabase session in an httpOnly cookie automatically. This prevents XSS from stealing the session token.

### Next.js middleware

`middleware.ts` runs on every request matching:
```
/((?!_next/static|_next/image|favicon.ico|login|api).*)
```

On every matched request:
1. Call `updateSession` from `lib/supabase/middleware.ts` to refresh the cookie if the token is close to expiry.
2. If `user` is `null` and the path starts with `/dashboard`, redirect to `/login?next=<encoded-path>`.
3. If `user` is non-null and the path is `/login`, redirect to `/dashboard`.

### API call authentication

Every fetch from a Server Component or Client Component to the FastAPI backend includes:
```
Authorization: Bearer <supabase_access_token>
```

The `apiFetch` helper in `lib/api.ts` retrieves the token from the current Supabase session and attaches it. Server Components use `lib/supabase/server.ts`; Client Components use `lib/supabase/client.ts`.

### FastAPI JWT verification

`backend/app/auth/jwt.py` provides:

```python
def decode_supabase_jwt(token: str) -> dict:
    """Verify signature with SUPABASE_JWT_SECRET (HS256), validate exp."""

async def get_current_user(authorization: str = Header(...)) -> CurrentUser:
    """Parse Bearer token, call decode_supabase_jwt, return CurrentUser."""
```

`CurrentUser` carries `user_id`, `organization_id` (from `app_metadata`), and `email`.

All protected routes use `Depends(get_current_user)`. Webhook routes (`/webhooks/*`) use HMAC verification instead and are explicitly excluded from this dependency.

### Query scoping

Every protected query filters by `current_user.organization_id`. The hardcoded `_DEFAULT_ORG_ID` placeholder used in Day 3 development is replaced.

### Defense-in-depth

Two independent isolation layers:
1. Application layer: `current_user.organization_id` injected via `Depends(get_current_user)`.
2. Database layer: RLS policies on `detection_runs`, `detections`, `insights`, `contacts`, `invoices` (already in place from Day 2–3 migrations).

---

## Rejected Alternatives

### Custom JWT system

Requires: key generation and rotation, secure storage of signing keys, expiry and refresh logic, password hashing, password-reset emails, and account enumeration prevention. All of this is solved and battle-tested in Supabase Auth. The implementation cost for a portfolio project is not justified.

### Clerk / Auth0

Clerk and Auth0 provide a superset of what is needed (SSO, MFA, enterprise connectors) with additional vendor lock-in. They also require a separate paid plan for production volumes. Supabase is already the database vendor; staying with one vendor reduces operational complexity.

### Session cookies without JWT (server-side sessions)

Requires a session store (Redis or database-backed) shared between the Next.js server and the FastAPI server. Cross-origin session sharing between `:3000` and `:8000` requires additional configuration and introduces a shared-state dependency between two otherwise decoupled services. JWTs are stateless and work cleanly across origins with a single shared secret.

### localStorage for token storage

`localStorage` is accessible to JavaScript running in the page, making it vulnerable to XSS. `httpOnly` cookies are not accessible to JavaScript and provide meaningful XSS mitigation. `@supabase/ssr` uses httpOnly cookies by default.

---

## Consequences

### Positive

- Auth is operational in a single afternoon: Supabase project creation, `@supabase/ssr` integration, JWT verification in FastAPI.
- Token rotation is handled by Supabase and `@supabase/ssr` transparently.
- Revoking a user's access is immediate: delete the user in the Supabase Auth dashboard; the next API call returns 401.
- Two layers of org isolation reduce the blast radius of any single bug.

### Trade-offs

- Requires a live Supabase project for auth in any environment (local dev, staging, production). There is no local-only auth mode.
- The `SUPABASE_JWT_SECRET` must be available to the FastAPI container. It must never be logged or exposed in error responses.
- E2E tests that require an authenticated session must either use a real Supabase test project or mock the JWT verification dependency.
- `organization_id` must be present in `app_metadata` for every user. New user provisioning must set this field, or all queries return 0 rows.
