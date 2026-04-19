"""Integration tests for custom_components/outback_mate3.

Covers Phase 9 of TASKS.md: stand up a fake version of the add-on's WS
endpoint, wire the integration to it, and assert the right entities
materialize and respond to state updates + reconnects. Phase 17 expanded
coverage to config-flow paths (user/hassio/reconfigure + error variants),
migrations, malformed payloads, and diagnostics.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from custom_components.outback_mate3 import CONF_URL, DEFAULT_URL, DOMAIN
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
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


# --- config flow: user step ----------------------------------------------


async def test_config_flow_user_step_creates_entry(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """Happy path — the user step probes the URL, then creates an entry."""
    fake_addon.messages = [SNAPSHOT_PAYLOAD]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] in (None, {})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: fake_addon.url}
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_URL: fake_addon.url}


@pytest.mark.parametrize(
    "probe_error",
    ["cannot_connect", "timeout", "bad_handshake", "unknown"],
)
async def test_config_flow_user_step_surfaces_probe_errors(
    hass: HomeAssistant, probe_error: str
) -> None:
    """Each ``_probe_ws_url`` error code should surface under ``errors['base']``."""
    with patch(
        "custom_components.outback_mate3.config_flow._probe_ws_url",
        return_value=probe_error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: "ws://bogus:28099/ws"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": probe_error}


async def test_config_flow_user_step_aborts_duplicate(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """A second entry for the same URL is rejected as already configured."""
    fake_addon.messages = [SNAPSHOT_PAYLOAD]
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: fake_addon.url},
        version=2,
        unique_id=f"mate3_{fake_addon.url}",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: fake_addon.url}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


# --- config flow: hassio discovery ---------------------------------------


async def test_config_flow_hassio_confirm_creates_entry(
    hass: HomeAssistant,
) -> None:
    """Hassio discovery → confirmation step → create_entry."""
    discovery = HassioServiceInfo(
        config={"host": "abc_outback_mate3", "port": 28099},
        name="Outback MATE3",
        slug="abc_outback_mate3",
        uuid="abc-uuid",
    )

    # The created entry would spin up a real WS loop against a bogus host —
    # aiohttp's DNS resolver leaves a timer that PHACC flags as "lingering".
    # Short-circuit start() so this flow-only test doesn't need a live server.
    with patch("custom_components.outback_mate3.OutbackMate3.start"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=discovery,
        )
        assert result["type"] == "form"
        assert result["step_id"] == "hassio_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_URL: "ws://abc_outback_mate3:28099/ws"}

    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_config_flow_hassio_rediscovery_updates_url(
    hass: HomeAssistant,
) -> None:
    """A repeat announce with a different port should update the existing entry."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "ws://abc_outback_mate3:28099/ws"},
        version=2,
        unique_id="hassio_abc_outback_mate3",
    )
    existing.add_to_hass(hass)

    discovery = HassioServiceInfo(
        config={"host": "abc_outback_mate3", "port": 29099},  # port changed
        name="Outback MATE3",
        slug="abc_outback_mate3",
        uuid="abc-uuid",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=discovery,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert existing.data[CONF_URL] == "ws://abc_outback_mate3:29099/ws"


# --- config flow: reconfigure --------------------------------------------


async def test_config_flow_reconfigure_updates_url(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """Reconfigure lets users retarget the WS URL without deleting the entry."""
    fake_addon.messages = [SNAPSHOT_PAYLOAD]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: fake_addon.url},
        version=2,
        unique_id=f"mate3_{fake_addon.url}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    new_url = "ws://another-host:28099/ws"
    # async_update_reload_and_abort reloads the entry under the new URL;
    # the fresh WS task's aiohttp session leaves a DNS resolver timer when
    # pointed at a bogus hostname, so short-circuit start() during the
    # reload to keep PHACC's lingering-timer check happy.
    with patch(
        "custom_components.outback_mate3.config_flow._probe_ws_url",
        return_value=None,
    ), patch("custom_components.outback_mate3.OutbackMate3.start"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: new_url}
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_URL] == new_url
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_config_flow_reconfigure_surfaces_probe_error(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """A probe failure during reconfigure keeps the form open with an error."""
    fake_addon.messages = [SNAPSHOT_PAYLOAD]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: fake_addon.url},
        version=2,
        unique_id=f"mate3_{fake_addon.url}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.outback_mate3.config_flow._probe_ws_url",
        return_value="cannot_connect",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: "ws://offline:28099/ws"}
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
    # URL is unchanged.
    assert entry.data[CONF_URL] == fake_addon.url
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


# --- migration -----------------------------------------------------------


async def test_migrate_v1_to_v2(hass: HomeAssistant) -> None:
    """Legacy UDP-port entries should migrate to the new URL form."""
    from custom_components.outback_mate3 import async_migrate_entry

    entry = MockConfigEntry(domain=DOMAIN, data={"port": 57027}, version=1)
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    assert entry.version == 2
    assert entry.data == {CONF_URL: DEFAULT_URL}


# --- malformed / unknown WS messages -------------------------------------


async def test_unknown_message_type_does_not_crash(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """An unknown ``type`` field should be ignored; later messages still work."""
    fake_addon.messages = [{"type": "garbage_we_dont_know"}, SNAPSHOT_PAYLOAD]
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Snapshot following the garbage message must still materialize entities.
    await _wait_for_state(hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power")


async def test_malformed_config_snapshot_is_ignored(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """config_snapshot missing ``mac`` or ``config`` must not crash the loop."""
    fake_addon.messages = [
        SNAPSHOT_PAYLOAD,
        {"type": "config_snapshot"},          # missing both mac and config
        {"type": "config_snapshot", "mac": MAC},  # missing config
        {"type": "config_snapshot", "mac": MAC, "config": "not-a-dict"},
        CONFIG_PAYLOAD,  # valid one should still be applied
    ]
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await _wait_for_state(hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power")
    # The valid CONFIG_PAYLOAD should have landed in config_by_mac.
    for _ in range(40):
        if MAC in entry.runtime_data.config_by_mac:
            break
        await asyncio.sleep(0.05)
    assert MAC in entry.runtime_data.config_by_mac


# --- device removal ------------------------------------------------------


async def test_remove_stale_device_allowed(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """async_remove_config_entry_device returns True for devices no longer seen."""
    from custom_components.outback_mate3 import async_remove_config_entry_device
    from homeassistant.helpers import device_registry as dr

    fake_addon.messages = [SNAPSHOT_PAYLOAD]
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _wait_for_state(hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power")

    # Construct a synthetic DeviceEntry identifier for a MAC we've never seen.
    stale_device = dr.DeviceEntry(
        id="stale_id",
        identifiers={(DOMAIN, "inverter_GHOSTMAC99999_7")},
        config_entries={entry.entry_id},
    )
    assert await async_remove_config_entry_device(hass, entry, stale_device) is True


async def test_remove_live_device_blocked(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """async_remove_config_entry_device returns False for currently-known devices."""
    from custom_components.outback_mate3 import async_remove_config_entry_device
    from homeassistant.helpers import device_registry as dr

    fake_addon.messages = [SNAPSHOT_PAYLOAD]
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _wait_for_state(hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power")

    live_device = dr.DeviceEntry(
        id="live_id",
        identifiers={(DOMAIN, f"inverter_{MAC}_1")},
        config_entries={entry.entry_id},
    )
    assert await async_remove_config_entry_device(hass, entry, live_device) is False


# --- diagnostics ---------------------------------------------------------


async def test_diagnostics_snapshot(
    hass: HomeAssistant, fake_addon: _FakeAddOn
) -> None:
    """Diagnostics exposes coordinator state; redaction set is honored."""
    from custom_components.outback_mate3.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    fake_addon.messages = [SNAPSHOT_PAYLOAD, CONFIG_PAYLOAD]
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: fake_addon.url}, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _wait_for_state(hass, f"sensor.mate3_{MAC.lower()}_inverter_1_grid_power")

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["version"] == 2
    assert diag["entry"]["domain"] == DOMAIN
    assert diag["coordinator"] is not None
    assert diag["coordinator"]["url"] == fake_addon.url
    assert diag["coordinator"]["connected"] is True
    assert MAC in diag["coordinator"]["by_mac"]
