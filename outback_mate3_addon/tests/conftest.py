"""Pytest config — makes the add-on's src/ importable as the top-level package."""
from __future__ import annotations

import sys
from pathlib import Path

# Let tests do `from src.parser import ...`
_ADDON_ROOT = Path(__file__).resolve().parent.parent
if str(_ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(_ADDON_ROOT))
