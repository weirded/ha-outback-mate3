"""In-memory device state registry.

The registry is the add-on's source of truth: it ingests parsed
:class:`~src.parser.DeviceUpdate` batches and emits typed events
(:class:`DeviceAdded`, :class:`StateUpdated`) describing what changed. It also
produces a :meth:`DeviceRegistry.snapshot` for new WebSocket clients.

Aggregates (system totals, averages) are intentionally NOT computed here. The
HA integration's system-level sensors compute them on demand from the raw
per-device state, so storing them here would just duplicate state.

Per-MAC throttling mirrors the existing integration's 30-second behavior: when
frames arrive more often than ``min_update_interval_s`` for a MAC, extra
frames are dropped entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable

from src.parser import DeviceUpdate

DeviceKey = tuple[str, str, int]  # (mac, kind, index)


@dataclass(frozen=True)
class DeviceAdded:
    mac: str
    kind: str
    index: int
    state: dict[str, Any]


@dataclass(frozen=True)
class StateUpdated:
    mac: str
    kind: str
    index: int
    state: dict[str, Any]


@dataclass(frozen=True)
class ConfigSnapshot:
    """Latest parsed CONFIG.xml for a MATE3, pushed on every successful poll."""

    mac: str
    config: dict[str, Any]


Event = DeviceAdded | StateUpdated | ConfigSnapshot


class DeviceRegistry:
    def __init__(
        self,
        min_update_interval_s: float = 30.0,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._min_interval = min_update_interval_s
        self._clock = clock
        self._devices: dict[DeviceKey, dict[str, Any]] = {}
        self._last_update: dict[str, datetime] = {}
        # Last remote IP per MAC — used by the HTTP config poller to reach
        # the MATE3 without needing extra configuration.
        self._source_ips: dict[str, str] = {}
        # Latest parsed CONFIG.xml per MAC.
        self._last_configs: dict[str, dict[str, Any]] = {}

    def apply(self, updates: Iterable[DeviceUpdate], remote_ip: str | None = None) -> list[Event]:
        """Ingest a frame's worth of updates. Return events describing the change.

        If the frame arrives within ``min_update_interval_s`` of the last accepted
        frame for the same MAC, the entire batch is dropped and ``[]`` is
        returned — matching the existing integration's throttle semantics.
        """
        updates = list(updates)
        if not updates:
            return []

        mac = updates[0].mac
        if any(u.mac != mac for u in updates):
            raise ValueError("All updates in one batch must share the same MAC")

        now = self._clock()
        last = self._last_update.get(mac)
        if last is not None and (now - last).total_seconds() < self._min_interval:
            return []
        self._last_update[mac] = now
        if remote_ip is not None:
            self._source_ips[mac] = remote_ip

        events: list[Event] = []
        for update in updates:
            key: DeviceKey = (update.mac, update.kind, update.index)
            is_new = key not in self._devices
            self._devices[key] = dict(update.state)
            if is_new:
                events.append(
                    DeviceAdded(update.mac, update.kind, update.index, dict(update.state))
                )
            else:
                events.append(
                    StateUpdated(update.mac, update.kind, update.index, dict(update.state))
                )
        return events

    def snapshot(self) -> list[dict[str, Any]]:
        """Return the current state of all known devices for a new WS client."""
        return [
            {"mac": mac, "kind": kind, "index": index, "state": dict(state)}
            for (mac, kind, index), state in self._devices.items()
        ]

    # --- source-IP / config tracking ---------------------------------------

    def source_ip(self, mac: str) -> str | None:
        return self._source_ips.get(mac)

    def known_sources(self) -> list[tuple[str, str]]:
        """All (mac, remote_ip) pairs we've seen so far."""
        return list(self._source_ips.items())

    def set_config(self, mac: str, config: dict[str, Any]) -> bool:
        """Store a parsed CONFIG.xml for a MAC. Returns True if different from the last."""
        prev = self._last_configs.get(mac)
        if prev == config:
            return False
        self._last_configs[mac] = config
        return True

    def config(self, mac: str) -> dict[str, Any] | None:
        return self._last_configs.get(mac)

    def configs(self) -> dict[str, dict[str, Any]]:
        return dict(self._last_configs)

    # --- Introspection helpers (used by tests) ---

    def device(self, mac: str, kind: str, index: int) -> dict[str, Any] | None:
        return self._devices.get((mac, kind, index))

    def __len__(self) -> int:
        return len(self._devices)
