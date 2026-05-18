from contextvars import ContextVar

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
org_id: ContextVar[str | None] = ContextVar("org_id", default=None)
user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
route: ContextVar[str | None] = ContextVar("route", default=None)
