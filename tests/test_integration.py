"""Integration tests for custom_components/outback_mate3.

Covers Phase 9 of TASKS.md: stand up a fake version of the add-on's WS
endpoint, wire the integration to it, and assert the right entities
materialize and respond to state updates + reconnects.
"""
from __future__ import annotations

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from custom_components.outback_mate3 import CONF_URL, DOMAIN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

# PHACC disables sockets by default so accidental internet hits fail loudly.
# These tests rely on a locally-bound aiohttp server, so reenable.
pytestmark = pytest.mark.enable_socket


# --- minimal but realistic snapshot + state_updated payloads ---------------

MAC = "TESTMAC00001"

SNAPSHOT_PAYLOAD = {
    "type": "snapshot",
    "devices": [
        {
            "mac": MAC,
            "kind": "inverter",
            "index": 1,
            "state": {
                "grid_power": 500,
                "l1_grid_power": 250,
                "l2_grid_power": 250,
                "l1_inverter_power": 0,
                "l2_inverter_power": 0,
                "l1_charger_power": 0,
                "l2_charger_power": 0,
                "battery_voltage": 52.5,
                "inverter_mode": "inverting",
                "ac_mode": "ac-use",
                "grid_mode": "grid",
            },
        },
        {
            "mac": MAC,
            "kind": "charge_controller",
            "index": 1,
            "state": {
                "pv_current": 5.0,
                "pv_voltage": 80.0,
                "pv_power": 400,
                "output_current": 7.5,
                "output_power": 390,
                "battery_voltage": 52.5,
                "kwh_today": 1.5,
                "charge_mode": "bulk",
            },
        },
    ],
}

CONFIG_PAYLOAD = {
    "type": "config_snapshot",
    "mac": MAC,
    "config": {
        "system": {"system_type": "Grid Tied", "nominal_voltage": "48"},
        "mate3": {"firmware": "001.004.007"},
        "inverters": [{"firmware": "001.006.070"}],
        "charge_controllers": [{"firmware": "003.003.000", "model_type": "FM"}],
    },
}


# --- scriptable fake add-on ------------------------------------------------


class _FakeAddOn:
    """A tiny aiohttp WS server that replays a scripted sequence to each new client."""

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.connected: list[web.WebSocketResponse] = []
        self.app = web.Application()
        self.app.router.add_get("/ws", self._handle)

    async def _handle(self, request: web.Request) -> web.WebSocketResponse:
        # No heartbeat — the aiohttp heartbeat timer lingers past test
        # teardown and PHACC catches that as a lingering-timer error.
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        for msg in self.messages:
            await ws.send_json(msg)
        self.connected.append(ws)
        try:
            async for _ in ws:
                pass
        finally:
            if ws in self.connected:
                self.connected.remove(ws)
        return ws

    async def broadcast(self, msg: dict) -> None:
        for ws in list(self.connected):
            if not ws.closed:
                await ws.send_json(msg)

    async def close_all(self) -> None:
        for ws in list(self.connected):
            await ws.close()


@pytest.fixture
async def fake_addon(socket_enabled):
    # socket_enabled re-enables the network — PHACC disables it by default.
    fake = _FakeAddOn()
    server = TestServer(fake.app)
    await server.start_server()
    fake.url = f"ws://{server.host}:{server.port}/ws"
    try:
        yield fake
    finally:
        await fake.close_all()
        await server.close()


async def _wait_for_state(hass: HomeAssistant, entity_id: str, timeout: float = 5.0):
    """Poll the state machine until an entity appears, or fail."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        state = hass.states.get(entity_id)
        if state is not None and state.state not in (None, "unknown"):
            return state
        await asyncio.sleep(0.05)
    raise AssertionError(f"{entity_id} never populated within {timeout}s")


# --- tests ----------------------------------------------------------------


async def test_snapshot_creates_udp_entities(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """A snapshot payload should materialize sensor entities for each device."""
    fake_addon.messages = [SNAPSHOT_PAYLOAD]

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_state = await _wait_for_state(
        hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power"
    )
    assert float(inv_state.state) == 500

    cc_state = await _wait_for_state(
        hass, f"sensor.mate3_{MAC.lower()}_charge_controller_1_pv_power"
    )
    assert float(cc_state.state) == 400


async def test_state_updated_refreshes_entities(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    fake_addon.messages = [SNAPSHOT_PAYLOAD]
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await _wait_for_state(hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power")

    # Now push a state_updated with a different grid_power.
    updated = {
        **SNAPSHOT_PAYLOAD["devices"][0],
        "type": "state_updated",
        "state": {**SNAPSHOT_PAYLOAD["devices"][0]["state"], "grid_power": -300},
    }
    await fake_addon.broadcast(updated)
    # Give the client a moment to apply.
    eid = f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power"
    st = None
    for _ in range(40):
        st = hass.states.get(eid)
        if st and st.state == "-300":
            break
        await asyncio.sleep(0.05)
    assert st is not None, f"{eid} vanished before state update was applied"
    assert st.state == "-300", f"expected -300, last seen {st.state!r}"


async def test_config_snapshot_only_creates_diagnostics_after_poll(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """Config-derived diagnostic entities appear only after first config_snapshot.

    Config sensors are disabled-by-default (15.14), so they don't show up in
    `hass.states` unless explicitly enabled. We assert on the entity registry
    instead — that's where "entity exists but disabled" shows up.
    """
    from homeassistant.helpers import entity_registry as er

    fake_addon.messages = [SNAPSHOT_PAYLOAD]  # no config_snapshot yet
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await _wait_for_state(hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power")

    registry = er.async_get(hass)
    firmware_eid = "sensor.mate3_system_mate3_firmware"
    # Without a config_snapshot, the firmware diagnostic entity isn't registered.
    assert registry.async_get(firmware_eid) is None

    # Send one. After it lands, the entity should be registered (disabled,
    # but present — the gating from 15.13 is what we're verifying).
    await fake_addon.broadcast(CONFIG_PAYLOAD)
    for _ in range(40):
        entry = registry.async_get(firmware_eid)
        if entry is not None:
            break
        await asyncio.sleep(0.05)
    assert entry is not None, "firmware diagnostic entity never registered"
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, (
        f"expected disabled-by-default config sensor, got disabled_by={entry.disabled_by}"
    )


async def test_receiving_data_binary_sensor_flips_on_snapshot(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """The connectivity binary sensor turns on once UDP-derived data arrives."""
    fake_addon.messages = [SNAPSHOT_PAYLOAD]
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # After the snapshot lands, the binary sensor should read "on". Initial
    # state right after setup is "off" (no UDP yet), so poll until it flips.
    for _ in range(100):
        st = hass.states.get("binary_sensor.mate3_system_receiving_data")
        if st is not None and st.state == "on":
            break
        await asyncio.sleep(0.05)
    assert st is not None and st.state == "on", (
        f"binary sensor never flipped to on; last state={st and st.state}"
    )


async def test_receiving_data_binary_sensor_is_off_without_udp(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """With only a config_snapshot (no UDP devices), the sensor stays off."""
    # Empty devices list = no UDP-derived payloads applied yet, even after
    # the WS connection is fully up and a config_snapshot has arrived.
    fake_addon.messages = [{"type": "snapshot", "devices": []}, CONFIG_PAYLOAD]
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Give the WS loop a moment to process both messages.
    for _ in range(20):
        st = hass.states.get("binary_sensor.mate3_system_receiving_data")
        if st is not None:
            break
        await asyncio.sleep(0.05)
    assert st is not None
    assert st.state == "off"


async def test_reconnects_after_addon_drops_ws(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """Killing the add-on's sockets should trigger reconnect + new snapshot."""
    fake_addon.messages = [SNAPSHOT_PAYLOAD]
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _wait_for_state(hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power")

    # Kill existing client connections; the integration should reconnect
    # and pick up the canned snapshot again.
    await fake_addon.close_all()

    # Tweak the snapshot so we can verify the NEW state lands (not stale data).
    new_snap = {
        **SNAPSHOT_PAYLOAD,
        "devices": [
            {
                **SNAPSHOT_PAYLOAD["devices"][0],
                "state": {
                    **SNAPSHOT_PAYLOAD["devices"][0]["state"],
                    "grid_power": 999,
                },
            },
            SNAPSHOT_PAYLOAD["devices"][1],
        ],
    }
    fake_addon.messages = [new_snap]

    eid = f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power"
    st = None
    for _ in range(100):  # up to ~5 s — backoff is 1 s
        st = hass.states.get(eid)
        if st and st.state == "999":
            break
        await asyncio.sleep(0.05)
    assert st is not None, f"{eid} never re-appeared after reconnect"
    assert st.state == "999", f"expected 999 after reconnect, last seen {st.state!r}"
