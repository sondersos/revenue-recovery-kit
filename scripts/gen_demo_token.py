#!/usr/bin/env python3
"""Generate a short-lived JWT for local demo/testing.

Usage:
    python scripts/gen_demo_token.py
    SUPABASE_JWT_SECRET=... python scripts/gen_demo_token.py

Reads SUPABASE_JWT_SECRET from the environment or from .env in the repo root.
Prints a single Bearer token to stdout.
"""
import os
import sys
import time
import uuid
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    _load_dotenv(repo_root / ".env")

    secret = os.environ.get("SUPABASE_JWT_SECRET", "")
    if not secret:
        print(
            "ERROR: SUPABASE_JWT_SECRET is not set. "
            "Copy .env.example to .env and populate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import jwt
    except ImportError:
        print("ERROR: PyJWT is not installed. Run: pip install PyJWT", file=sys.stderr)
        sys.exit(1)

    org_id = os.environ.get("DEMO_ORG_ID", "00000000-0000-0000-0000-000000000001")
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "demo@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "app_metadata": {"organization_id": org_id},
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
