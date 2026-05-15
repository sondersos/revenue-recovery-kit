# ADR-0003: Detection Rule Engine

**Date:** 2026-05-14
**Status:** Accepted
**Deciders:** Bayanda

---

## Context

The system needs to flag contacts and invoices that represent revenue-recovery opportunities. Rules will evolve as the business learns which patterns predict successful recovery. Non-technical operators may eventually need to tune thresholds (e.g. "stalled after 5 days" vs "7 days"). The detection engine must be auditable — given the same data and rule set, the same detections must be produced every time.

Three requirements follow from this:

1. **Evolvability.** Adding, removing, or modifying a rule must not require editing a monolithic function. Each rule should be an isolated unit that can be reviewed and merged independently.

2. **Testability.** Each rule must be independently testable. A test for the `stalled_invoice` rule must not require the `stale_lead` rule to exist or pass.

3. **Reproducibility.** Given the same database state and the same rule set, a detection run must always produce identical output. Non-deterministic or stateful detection logic is not acceptable.

---

## Decision

### Rule Interface

Each rule is a Python dataclass with the following fields:

| Field | Type | Purpose |
|---|---|---|
| `name` | `str` | Machine-readable slug used as the detection type in stored records |
| `description` | `str` | Human-readable explanation shown in audit logs and the dashboard |
| `severity` | `Literal['LOW', 'MEDIUM', 'HIGH']` | Triage priority surfaced to the operator |
| `subject_type` | `Literal['contact', 'invoice']` | Determines which entity the detection is attached to |
| `find(session, org_id)` | `async` method returning `list[Detection]` | Queries the database and returns zero or more detection records |

The `find()` method receives a SQLAlchemy `AsyncSession` and an `org_id`. It is a pure database read — it must not mutate state, call external APIs, or produce side effects. This constraint makes it safe to call rules in any order and makes each rule independently verifiable against a test database fixture.

### Registry

Rules are registered in `backend/app/services/detection/rules/__init__.py` via a module-level list:

```python
REGISTRY: list[BaseRule] = [
    StalledInvoiceRule(),
    StaleLeadRule(),
    RecoveryCandidateRule(),
    SequenceEligibleRule(),
]
```

Adding a rule means: (a) create a new file in `backend/app/services/detection/rules/`, (b) implement the dataclass and `find()` method, and (c) append an instance to `REGISTRY`. No other file requires modification.

### Engine Behaviour

The engine iterates `REGISTRY` in order, calls `find()` on each rule, collects all returned `Detection` objects, and bulk-inserts them in a single database transaction at the end of the run. The single-transaction guarantee means that a detection run either commits in full or rolls back in full — there are no partial runs visible to the dashboard.

### Initial Rule Set

**Rule 1: `stalled_invoice` — Severity: HIGH**

Invoice issued more than 7 days ago, status `unpaid`, and no contact activity logged in the last 5 days. This is the primary recovery signal: money is owed, time has passed, and no human has touched the account recently. Severity is HIGH because each qualifying record represents a specific dollar amount at immediate risk.

**Rule 2: `stale_lead` — Severity: MEDIUM**

Contact created more than 14 days ago with no invoice ever issued and no recent activity on record. This is a pipeline-leak signal rather than a payment-failure signal — revenue was never converted, not lost after conversion. Severity is MEDIUM because the cost is opportunity cost rather than a confirmed receivable.

**Rule 3: `recovery_candidate` — Severity: HIGH**

Invoice more than 30 days unpaid and the associated contact is not currently enrolled in an active recovery sequence. This is the escalation signal: the stalled invoice has aged past the standard follow-up window and requires deliberate intervention. Severity is HIGH.

**Rule 4: `sequence_eligible` — Severity: LOW**

Contact matches a stalled or stale state and is not already enrolled in an active sequence. This is a pre-action signal used by the sequence engine to identify contacts that should be enrolled next. Severity is LOW because it represents a candidate for automation, not an urgent failure.

---

## Rejected Alternative 1: Imperative Service with Hardcoded If-Blocks

A single service function with chained `if`-conditions is faster to write on Day 3. It requires no registry abstraction and no base class. A developer can read the entire detection logic in one scroll.

This approach is rejected for three reasons. First, as rules multiply, the function becomes unreadable — interleaved conditions for contacts and invoices, with different severity levels and different subject types, cannot be disentangled without rewriting the function. Second, there is no audit trail of which rule triggered a specific detection: a detection row would record only that *something* fired, not *which rule* fired. Third, adding a rule requires editing the monolithic function, which means every PR that adds a rule risks breaking every other rule in the same file. The registry pattern eliminates all three problems at the cost of one additional abstraction layer.

---

## Rejected Alternative 2: External Rule Engine (Drools, OpenL Tablets)

Production-grade rule engines such as Drools and OpenL Tablets provide a graphical UI for non-technical threshold tuning, support complex rule chaining with forward-chaining inference, and have mature audit-log facilities.

This approach is rejected because both Drools and OpenL Tablets require a JVM dependency. Adding a JVM service to a Python/Postgres/Next.js stack introduces significant operational complexity: a fourth container in Docker Compose, a separate deployment artifact, a different language runtime to monitor, and a debugging context switch whenever a rule misbehaves. For four rules, this overhead is disproportionate. The declarative Python dataclass registry achieves the same structural goals — isolation, testability, auditability — within the existing runtime. If the rule count grows beyond ~20 and operators require self-service threshold editing, migration to an external engine is a viable future path; the `REGISTRY` abstraction makes that migration tractable without a rewrite of the engine or the detection schema.

---

## Consequences

### Positive

- Adding a rule requires adding one file and one registry entry. No existing file is modified.
- Detection runs are reproducible: same database state + same `REGISTRY` list → same `Detection` rows emitted every time.
- Each `find()` method takes only a `session` and `org_id`. Unit tests can inject a test session against a local Postgres fixture and assert on the returned list without running the full engine.
- The single-transaction bulk insert means the dashboard never sees a partially-complete detection run.
- Severity levels (`LOW`, `MEDIUM`, `HIGH`) give the dashboard a stable triage axis that does not change as rules are added.

### Trade-offs

- All thresholds (7 days, 5 days, 14 days, 30 days) are currently hardcoded in rule implementations. Externalising them to a database configuration table — so that an operator can tune thresholds without a redeploy — is a Day 5+ concern. The registry structure does not block this: each rule's `find()` method can read from a config table once that table exists.
- Rules execute sequentially in `REGISTRY` order. For the initial four rules and typical dataset sizes this is acceptable. Parallelisation via `asyncio.gather()` is possible but deferred; it would require each rule's `find()` to use its own session or a carefully scoped connection to avoid shared-state conflicts.
- The `find()` interface returns `list[Detection]`. If a rule needs to produce both contact-level and invoice-level detections in one pass, it must declare a `subject_type` of one and emit separate rule instances for the other. This is a minor constraint imposed by the typed interface.

---

## Decision Summary

Use a declarative Python dataclass rule registry. Each rule exposes a `find(session, org_id)` async method. The engine iterates `REGISTRY`, collects all `Detection` results, and bulk-inserts in one transaction. Four initial rules: `stalled_invoice` (HIGH), `stale_lead` (MEDIUM), `recovery_candidate` (HIGH), `sequence_eligible` (LOW). Thresholds are hardcoded for now; externalisation is deferred to Day 5.
