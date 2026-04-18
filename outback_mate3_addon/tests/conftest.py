"""Pytest config — makes the add-on's src/ importable as the top-level package."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Let tests do `from src.parser import ...`
_ADDON_ROOT = Path(__file__).resolve().parent.parent
if str(_ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(_ADDON_ROOT))


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
