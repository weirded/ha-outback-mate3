"""Pytest config — makes the add-on's src/ importable as the top-level package."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Let tests do `from src.parser import ...`
_ADDON_ROOT = Path(__file__).resolve().parent.parent
if str(_ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(_ADDON_ROOT))

# pycares>=5.0 spawns a daemon thread "_run_safe_shutdown_loop" the first time
# any c-ares channel is destroyed. PHACC's per-test cleanup check (autouse via
# entry-point plugin — applies even to add-on tests that don't use HA) rejects
# any thread outside its allowlist, so the first test to trigger DNS fails
# teardown. Warm the singleton here so the thread exists in `threads_before`
# and is ignored as pre-existing.
# Guarded: no pycares means no pycares thread means nothing to warm up.
try:
    import pycares  # noqa: E402
except ImportError:
    pycares = None  # type: ignore[assignment]

if pycares is not None:
    _warmup_channel = pycares.Channel()
    # close() only exists on pycares>=5.0; older versions are a no-op.
    if hasattr(_warmup_channel, "close"):
        _warmup_channel.close()
    del _warmup_channel


@pytest.fixture(autouse=True)
def _enable_socket():
    """Undo pytest-socket's global block.

    pytest-socket gets pulled in by pytest-homeassistant-custom-component and
    disables sockets for every test in the process. These tests bind real
    aiohttp TestServers, so we need the network.
    """
    try:
        import pytest_socket
    except ImportError:
        return
    pytest_socket.enable_socket()
