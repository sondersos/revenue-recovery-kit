"""
Structured JSON logging configuration for revenue-recovery-kit.

Attaches a JSON handler to the root logger and injects per-request context
(correlation_id, org_id, user_id, route) via a logging.Filter that reads
from ContextVars set by RequestContextMiddleware and the JWT dependency.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from pythonjsonlogger import jsonlogger


class ContextVarFilter(logging.Filter):
    """Inject ContextVar values into every LogRecord before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Import here to avoid any circular-import risk at module level
        from app.observability.correlation import (
            correlation_id,
            org_id,
            user_id,
            route,
        )

        record.correlation_id = correlation_id.get()
        record.org_id = org_id.get()
        record.user_id = user_id.get()
        record.route = route.get()
        return True


class _UTCTimestampFormatter(jsonlogger.JsonFormatter):
    """JsonFormatter subclass that stamps every record with an ISO-8601 UTC timestamp."""

    def add_fields(
        self,
        log_record: dict,
        record: logging.LogRecord,
        message_dict: dict,
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        # Normalise the level key name
        log_record["level"] = record.levelname


def configure_logging(level: str = "INFO") -> None:
    """
    Wire up a JSON stream handler on the root logger.

    Safe to call multiple times — duplicate handlers are suppressed.
    """
    root = logging.getLogger()

    # Avoid adding duplicate handlers on reload / test re-import
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler) and hasattr(handler, "_rrk_json"):
            return

    formatter = _UTCTimestampFormatter(fmt="%(timestamp)s %(level)s %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(ContextVarFilter())
    handler._rrk_json = True  # type: ignore[attr-defined]

    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)
