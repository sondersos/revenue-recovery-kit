"""
Shared pytest configuration for the revenue-recovery-kit test suite.
"""
import sys
import os
import pytest

# Ensure both 'backend' and 'backend/integrations' are on sys.path so that
# `app.*` and `integrations.*` imports resolve without a package install step.
_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
_INTEGRATIONS = os.path.join(_BACKEND, "integrations")

for _p in (_BACKEND, _INTEGRATIONS):
    _abs = os.path.abspath(_p)
    if _abs not in sys.path:
        sys.path.insert(0, _abs)


def pytest_configure(config):
    """Register custom marks to suppress PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", "unit: pure unit test — no real I/O or database")
