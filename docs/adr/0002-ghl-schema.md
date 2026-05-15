# ADR-0002: GoHighLevel Data Schema and Ingestion Contracts

**Date:** 2026-05-14
**Status:** Accepted
**Deciders:** Bayanda

---

## Context

The system ingests contact and invoice data from GoHighLevel (GHL) via inbound webhooks. Before writing a single migration, four design questions must be answered and locked down:

1. **What fields do we store, and what is the dedup key for each entity?** GHL can fire the same webhook event multiple times (retries, network hiccups). Idempotent upserts require a stable, unique key per entity that is not under application control.

2. **How do we detect overdue invoices and failed payments without polling GHL continuously?** Detection logic must be expressible as pure SQL so it can be tested offline and run on a schedule without a GHL connection.

3. **How do we verify that an inbound webhook is genuinely from GHL and not a spoofed request?** The verification mechanism must be timing-safe and must reject bad requests before any payload parsing occurs.

4. **What upsert strategy is safe under concurrent webhook delivery?** GHL may deliver two webhooks for the same contact within milliseconds of each other. The chosen strategy must be atomic and must not break foreign-key references.

All five decisions below must be settled before Day 2 schema migrations are written. Changing them after migrations exist requires a coordinated migration + application code + test rewrite.

---

## Decision

### 1. Contact Schema

**Table:** `contacts`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PRIMARY KEY, default `gen_random_uuid()` |
| `ghl_contact_id` | VARCHAR | NOT NULL, UNIQUE |
| `email` | VARCHAR | NULLABLE |
| `phone` | VARCHAR | NULLABLE |
| `full_name` | VARCHAR | NULLABLE |
| `organization_id` | UUID | NULLABLE, FK → `organizations.id` |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` |

**Dedup key:** `ghl_contact_id` (the opaque string identifier GHL assigns to each contact record within a location).

**Rationale for `ghl_contact_id` over email or phone:**

GHL is the system of record. Its contact identifier is immutable and unique within a GHL location — two different contacts in the same location will never share a `ghl_contact_id`. Email and phone are not reliable dedup keys for three reasons: (a) GHL explicitly allows a single location to hold multiple contact records with the same email address (e.g. a husband and wife sharing a family email); (b) email addresses change over a contact's lifetime, meaning a stable dedup key must survive an email update without creating a duplicate row; (c) phone numbers are frequently shared across household members or re-assigned by carriers. Keying on `ghl_contact_id` means the dedup decision is delegated to GHL, which is the authoritative source, rather than re-implemented in application code where the edge cases would inevitably be wrong.

**Rejected alternative — email as dedup key:**

Using `email` as the `UNIQUE` constraint means that two GHL contacts sharing an email address would collide on upsert — the second upsert would silently overwrite the first, losing data for one of the two contacts. GHL's data model explicitly supports multiple records per email, so this approach would produce systematic data loss for any agency with family or joint accounts.

---

### 2. Invoice Schema

**Table:** `invoices`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PRIMARY KEY, default `gen_random_uuid()` |
| `ghl_invoice_id` | VARCHAR | NOT NULL, UNIQUE |
| `contact_id` | UUID | NOT NULL, FK → `contacts.id` ON DELETE CASCADE |
| `amount` | NUMERIC(10, 2) | NOT NULL |
| `status` | VARCHAR | NOT NULL — enum: `draft`, `sent`, `overdue`, `paid`, `void` |
| `payment_status` | VARCHAR | NOT NULL — enum: `pending`, `succeeded`, `failed`, `refunded` |
| `due_date` | DATE | NULLABLE |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` |

**Dedup key:** `ghl_invoice_id` (the opaque string identifier GHL assigns to each invoice).

**Rationale for `ON DELETE CASCADE` on `contact_id`:** If a contact is deleted (e.g. merged or removed in GHL), the associated invoices have no owner and no recovery value. Cascading the delete keeps the database consistent without requiring a separate cleanup job.

**`status` vs `payment_status` — two separate columns:** GHL models invoice lifecycle (`draft → sent → overdue → paid`) and payment transaction outcome (`pending → succeeded / failed / refunded`) as independent state machines. Collapsing them into a single column would require a combinatorial enum and would make the detection queries in section 3 unreadable.

**Rejected alternative — `(amount, contact_id)` as composite dedup key:**

A contact can legitimately owe the same dollar amount on two separate invoices — for example, two monthly retainer invoices for the same fee. A composite key of `(amount, contact_id)` would cause the second invoice to collide with the first on upsert, silently dropping a real debt from the system. `ghl_invoice_id` is already unique per GHL location, so it is the correct and sufficient dedup key.

---

### 3. Detection Rule Definitions

Detection runs on a scheduled basis against the local Postgres database. No GHL API call is required at detection time.

**Rule: `overdue`**

```sql
invoice.due_date < CURRENT_DATE
AND invoice.status != 'paid'
```

An invoice is overdue if its due date has passed and GHL has not yet marked it paid. The `void` status is intentionally not excluded — a voided overdue invoice is still a signal that something went wrong and may warrant a record in the audit log, but the alerting layer should filter `void` out before sending a message to the contact.

**Rule: `failed_payment`**

```sql
invoice.payment_status = 'failed'
AND invoice.updated_at > (NOW() - INTERVAL '30 days')
```

A payment failure is actionable only if it is recent. Failures older than 30 days are considered stale: the contact has either resolved the issue through another channel, the debt has been handed to a human collections process, or the invoice has been voided. Automating retry outreach on a 30-day-old failure would produce confusing, out-of-context messages and would undermine trust in the system. The 30-day boundary is the handoff point between automated recovery and human escalation; anything older than 30 days must be reviewed by a human before any further action is taken.

---

### 4. Webhook Signature Verification

GHL signs each outbound webhook payload with an HMAC-SHA256 digest. The digest is delivered in the request header `X-GHL-Signature`. The shared secret is stored in the environment variable `GHL_WEBHOOK_SECRET` and is never committed to the repository.

**Verification procedure:**

1. Read `X-GHL-Signature` from the request headers. If the header is absent, return `401` immediately.
2. Compute `HMAC-SHA256(key=GHL_WEBHOOK_SECRET, message=raw_request_body)`.
3. Compare the computed digest to the header value using `hmac.compare_digest` — **not** the `==` operator.
4. If the digests do not match, return `401` immediately — **do not** proceed to JSON parsing or any business logic.

**Why `hmac.compare_digest` and not `==`:** String equality in Python short-circuits on the first mismatched character. An attacker who can make many requests and observe response timing can use this to reconstruct the correct signature one character at a time (timing attack). `hmac.compare_digest` runs in constant time regardless of where the strings diverge, eliminating the timing side-channel.

**Why reject before payload parsing:** Parsing untrusted JSON before verifying authenticity means that a malformed or oversized payload from an unauthenticated source can consume CPU and memory. The signature check is O(1) against the raw bytes; it must be the first gate.

**Rejected alternative — IP allowlist:**

Restricting inbound webhook requests to a known set of GHL IP addresses is a common approach for third-party webhook security. It is not viable here because GHL does not publish a stable, versioned list of egress IP ranges. Any hardcoded allowlist would break silently whenever GHL rotates or expands its infrastructure, producing intermittent 401 errors that are difficult to diagnose and require a code change (and redeploy) to fix. HMAC verification is self-contained and does not depend on GHL's network topology.

---

### 5. Upsert Strategy: `ON CONFLICT DO UPDATE`

When a webhook delivers a contact or invoice record that already exists in the database (identified by the dedup key), the system must update the existing row rather than insert a duplicate.

**Decision:** Use PostgreSQL's `INSERT ... ON CONFLICT (ghl_contact_id) DO UPDATE SET ...` (and the equivalent for `ghl_invoice_id` on the `invoices` table). The upsert is issued as a single SQL statement, making it atomic at the database level.

Example shape for contacts:

```sql
INSERT INTO contacts (ghl_contact_id, email, phone, full_name, updated_at)
VALUES (:ghl_contact_id, :email, :phone, :full_name, now())
ON CONFLICT (ghl_contact_id)
DO UPDATE SET
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    full_name = EXCLUDED.full_name,
    updated_at = now();
```

**Rejected alternative — `DELETE` + `INSERT`:**

Deleting the existing row before inserting the new one is non-atomic: there is a window between the `DELETE` and the `INSERT` during which any concurrent query that JOINs on `contacts.id` will find no matching row, producing incorrect results or application errors. More critically, cascading deletes on `invoices.contact_id` would destroy all invoice records for the contact every time a contact webhook fires — including invoices that have not been re-delivered by GHL in this webhook batch. This would cause systematic data loss under normal operating conditions.

**Rejected alternative — `SELECT` + conditional `UPDATE` or `INSERT` in application code:**

Reading the row first and then deciding whether to `INSERT` or `UPDATE` introduces a time-of-check / time-of-use (TOCTOU) race condition. If two webhooks for the same `ghl_contact_id` arrive within milliseconds of each other — which GHL's retry logic makes likely — both application threads can read "row does not exist," both attempt `INSERT`, and one will fail with a unique constraint violation. Handling that exception and retrying collapses back to the same problem. PostgreSQL's `ON CONFLICT` clause resolves the race inside the database engine, where it can be handled with proper locking semantics.

---

## Consequences

### Positive

- The dedup key for both entities is delegated to GHL, the authoritative source of truth. Application code does not need to implement or maintain its own uniqueness heuristics.
- Detection rules are pure SQL predicates with no external dependencies. They can be unit-tested against a local Postgres instance with no GHL credentials.
- Webhook signature verification rejects unauthenticated requests before any payload parsing, minimising the attack surface.
- The `ON CONFLICT DO UPDATE` upsert is atomic and safe under concurrent delivery — no application-level locking or retry logic is required.
- `ON DELETE CASCADE` on `invoices.contact_id` keeps the database consistent without a separate cleanup job.

### Trade-offs

- The 30-day window for `failed_payment` detection is a fixed policy baked into the SQL rule. Changing it requires a code change and redeploy, not a configuration update. If different agencies require different windows, this must be parameterised in a future ADR.
- Storing `status` and `payment_status` as unconstrained `VARCHAR` columns means that an invalid enum value can be written to the database if the application layer does not validate first. A future migration should add `CHECK` constraints or convert to native Postgres enum types once the enum values are confirmed stable.
- `ON CONFLICT DO UPDATE` always overwrites all mapped fields with the latest webhook payload. If GHL ever sends a partial update webhook that omits fields (e.g. sends `email` but not `phone`), the upsert will null out the omitted fields. The webhook handler must be written to only map fields that are present in the payload.

---

## Decision Summary

GHL's opaque entity identifiers (`ghl_contact_id`, `ghl_invoice_id`) are the dedup keys for all upserts; detection is pure SQL with a 30-day window for stale failures; webhooks are verified with timing-safe HMAC-SHA256 before any payload parsing; and all upserts use PostgreSQL `ON CONFLICT DO UPDATE` for atomicity under concurrent delivery.
