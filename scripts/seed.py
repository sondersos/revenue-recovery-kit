"""
Seed script: inserts a fixed detection_run and 3 detections for local dev/testing.
Idempotent — uses INSERT ... ON CONFLICT (id) DO NOTHING.

Usage:
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/revenue_recovery \
        python3 scripts/seed.py
"""

import os

import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]

# Normalise URL: psycopg (v3) uses "postgresql://" or "postgresql+psycopg://"
# but does not understand the "+psycopg" or "+asyncpg" driver suffixes.
_sync_url = DATABASE_URL
for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://"):
    if _sync_url.startswith(prefix):
        _sync_url = "postgresql://" + _sync_url[len(prefix):]
        break

RUN_ID = "00000000-0000-0000-0000-000000000001"
ORG_ID = "00000000-0000-0000-0000-000000000099"
# A dummy subject UUID used for all three seed detections.
SUBJECT_ID = "00000000-0000-0000-0000-000000000010"

DETECTION_RUN_SQL = """
INSERT INTO detection_runs (id, organization_id, status, rule_count, detection_count)
VALUES (%s, %s, 'complete', 4, 3)
ON CONFLICT (id) DO NOTHING;
"""

DETECTION_SQL = """
INSERT INTO detections
    (id, detection_run_id, organization_id, rule_name, severity,
     subject_type, subject_id, amount_usd, days_outstanding, recommended_action)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO NOTHING;
"""

DETECTIONS = [
    (
        "00000000-0000-0000-0000-000000000011",
        RUN_ID,
        ORG_ID,
        "sequence_eligible",
        "LOW",
        "contact",
        SUBJECT_ID,
        None,
        None,
        "Enrol contact in the standard follow-up sequence.",
    ),
    (
        "00000000-0000-0000-0000-000000000012",
        RUN_ID,
        ORG_ID,
        "stale_lead",
        "MEDIUM",
        "contact",
        SUBJECT_ID,
        None,
        14,
        "Re-engage contact with a personalised outreach email.",
    ),
    (
        "00000000-0000-0000-0000-000000000013",
        RUN_ID,
        ORG_ID,
        "stalled_invoice",
        "HIGH",
        "invoice",
        SUBJECT_ID,
        3200.00,
        12,
        "Call the contact directly and request payment within 48 hours.",
    ),
]


def main() -> None:
    with psycopg.connect(_sync_url) as conn:
        with conn.cursor() as cur:
            cur.execute(DETECTION_RUN_SQL, (RUN_ID, ORG_ID))
            for row in DETECTIONS:
                cur.execute(DETECTION_SQL, row)
        conn.commit()
    print("Seed complete.")


if __name__ == "__main__":
    main()
