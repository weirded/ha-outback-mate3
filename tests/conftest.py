"""Pytest config for integration tests.

Makes the repo root importable so ``from custom_components.outback_mate3 ...``
works, and opts in to pytest-homeassistant-custom-component's fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# pycares>=5.0 spawns a daemon thread "_run_safe_shutdown_loop" the first time
# any c-ares channel is destroyed. PHACC's per-test cleanup check rejects any
# thread outside its allowlist, and since the thread is lazily created during
# HA setup, the first test to use DNS fails teardown. Warm the singleton here
# so the thread exists in `threads_before` and is ignored as pre-existing.
import pycares  # noqa: E402

_warmup_channel = pycares.Channel()
# close() only exists on pycares>=5.0 (which is what triggers the daemon thread
# we're warming up for). On older pycares the warmup is a no-op.
if hasattr(_warmup_channel, "close"):
    _warmup_channel.close()
del _warmup_channel

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):
    """Opt every test in this repo into custom-component discovery."""
    yield
