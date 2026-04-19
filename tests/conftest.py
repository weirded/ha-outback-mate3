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

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):
    """Opt every test in this repo into custom-component discovery."""
    yield
