# Detection Rules Reference

Rules live in `backend/app/services/detection/rules/`. Each rule is a Python dataclass with a `find(session, org_id)` async method that queries the database and returns `list[Detection]`. The engine bulk-inserts all detections in one transaction.

## Adding a Rule

1. Create `backend/app/services/detection/rules/<rule_name>.py`
2. Subclass `Rule` from `base.py` and implement `find()`
3. Append an instance to `REGISTRY` in `rules/__init__.py`
4. Add a unit test in `backend/tests/test_detection_rules.py`

## Current Rules

### `stalled_invoice` — Severity: HIGH

**File:** `stalled_invoice.py`  
**Subject:** `invoice`  
**Condition:** `status != 'paid' AND created_at < now() - 7d AND updated_at < now() - 5d`  
**Action:** Send Day-7 overdue reminder via Resend; escalate to SMS after 48 hours.

### `stale_lead` — Severity: MEDIUM

**File:** `stale_lead.py`  
**Subject:** `contact`  
**Condition:** `updated_at < now() - 14d AND no invoices for this contact`  
**Action:** Re-engage with a value-add touchpoint; qualify for invoicing within 7 days.

### `recovery_candidate` — Severity: HIGH

**File:** `recovery_candidate.py`  
**Subject:** `invoice`  
**Condition:** `status != 'paid' AND created_at < now() - 30d AND no pending sequence for contact`  
**Action:** Enqueue recovery sequence immediately; consider founder call for amounts > $1,000.

### `sequence_eligible` — Severity: LOW

**File:** `sequence_eligible.py`  
**Subject:** `contact`  
**Condition:** Contact has stalled invoice OR is a stale lead AND has no pending sequence  
**Action:** Automatically enqueue recovery sequence.

## API

```
POST /v1/detection/run
Body: {"window_days": 30}
Response: DetectionSummary (run_id, status, counts by rule, total_at_risk_usd)

GET /v1/detection/runs/{run_id}
Response: DetectionRunDetail (run metadata + detections grouped by rule_name)

POST /v1/insights
Body: {"detection_run_id": "<uuid>"}
Response: InsightResponse (summary_text, model, token counts, cost_usd)
```
