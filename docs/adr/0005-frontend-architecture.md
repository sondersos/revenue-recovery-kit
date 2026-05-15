# ADR-0005: Frontend Architecture — Next.js 14 App Router with Server Components

**Date:** 2026-05-15
**Status:** Accepted
**Deciders:** Bayanda

---

## Context

The dashboard is a single-page application used by agency owners to:
- View the latest Claude insight headline
- See three KPI metrics (at-risk $, high-severity count, last scan time)
- Trigger a detection + insight run via one button
- Browse a breakdown chart and a top-detections table

The primary constraints are:

1. **Fast first paint.** The dashboard is the centerpiece of the LinkedIn demo recording. A blank screen while JavaScript hydrates is unacceptable.
2. **Recruiters inspect the repo.** Architecture choices must be conventional and defensible in an interview.
3. **Low interactivity.** The only stateful interactions are a single "Run scan" button with a loading state, and a login form. Everything else is read-only.
4. **Tremor for charts.** Tremor 3 is built on Recharts and ships production-quality chart components in a few lines of JSX.

---

## Decision

### Router

**Next.js 14 App Router.** Pages Router is deprecated for new projects in Next.js 14. App Router is the canonical choice for 2024 and beyond.

### Component model

**Server Components by default.** Every component is a Server Component unless it requires one of:
- Browser-only APIs (`window`, `document`, event handlers)
- React state (`useState`, `useReducer`)
- React effects (`useEffect`)

The only Client Components (`"use client"`) in the initial build are:
| Component | Reason |
|---|---|
| `RunScanButton` | `onClick`, `useState` for loading/error |
| `LoginForm` | Form state + Supabase browser client |
| `DetectionsByRuleChart` | Tremor BarChart is client-only (Recharts) |
| `LogoutButton` | `onClick` + Supabase browser client |

### Data fetching

Server Components call the FastAPI backend using `fetch()` with the JWT extracted from the Supabase session cookie via `@supabase/ssr`. No `useEffect` data fetching. No SWR or React Query. `router.refresh()` after a mutation re-runs the Server Component fetch.

### State management

None. URL search params + Server Component re-renders handle all state transitions. A "Run scan" click updates the page by calling `router.refresh()` after the API round-trip completes.

### Styling

TailwindCSS 3 only. No CSS-in-JS, no styled-components, no CSS Modules. Tremor components are styled via Tailwind tokens.

### Charts

Tremor 3. Provides `BarChart`, `Card`, `Metric`, `Text`, and `Badge` components that are consistent with Tailwind tokens and require no additional chart configuration.

---

## Rejected Alternatives

### Pages Router

Deprecated for new projects in Next.js 14. Choosing Pages Router in 2024 signals unfamiliarity with the current framework; it would be the first thing a technical interviewer notices.

### SPA with client-side data fetching (`useEffect` + fetch)

Slower first paint: the browser must download the JS bundle, execute it, then make a network round-trip before the user sees data. Server Components eliminate this round-trip entirely for the initial render. Harder for recruiters to read: client-side data fetching buries the data access pattern inside component state, whereas a Server Component that `await`s data at the top is immediately readable.

### Redux / Zustand

Zero global state is needed for a single dashboard page. Adding a state library for one boolean (loading) would be over-engineering.

### Chart.js / D3

Lower-level than needed. Tremor's `BarChart` produces a production-quality chart in three lines of JSX; Chart.js or D3 would require 40–80 lines of configuration for the same output. Tremor also stays visually consistent with the rest of the Tailwind-based UI.

---

## Consequences

### Positive

- First paint of the dashboard is ~300ms on localhost (no hydration wait for the data).
- Bundle size is small: no client-side state library, no chart configuration code, most components are zero-JS Server Components.
- Adding interactivity later means moving individual components from server to client — the "happy path" in App Router.
- Code is readable for technical interviewers: Server Components read like synchronous data access, which is easier to follow than a chain of `useEffect` + `setState`.

### Trade-offs

- Tremor chart components require `"use client"` wrappers; chart data must be serialised and passed as props from the Server Component.
- `router.refresh()` re-fetches all Server Component data; there is no fine-grained cache invalidation. For this dashboard (one page, infrequent mutations) this is acceptable.
- Testing Server Components requires React's `renderToString` or an integration test setup; Vitest + RTL cover Client Components only.
