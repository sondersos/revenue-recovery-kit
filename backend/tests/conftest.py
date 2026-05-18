"""
Shared pytest configuration for the revenue-recovery-kit test suite.
"""
import sys
import pathlib

# Insert backend/ (one level up from this file) onto sys.path.
# In the container: /app. On the host: .../revenue-recovery-kit/backend/.
# This makes both `app.*` and `integrations.*` importable without installation.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


def pytest_configure(config):
    """Register custom marks to suppress PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", "unit: pure unit test — no real I/O or database")
