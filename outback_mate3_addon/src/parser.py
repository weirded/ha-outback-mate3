"""Pure parser for Outback MATE3 UDP streaming frames.

A MATE3 frame looks like:

    [MACHI-MACLO]<ID,TYPE,v2,v3,...><ID,TYPE,v2,v3,...>...

where:
  - ``MACHI`` / ``MACLO`` are 6-hex-char halves of the MATE3's 12-char device ID
  - Each ``<...>`` block is one device; ``TYPE`` = 6 (inverter) or 3 (charge controller)
  - Non-telemetry UDP traffic on the same port (filesystem / HTTP log lines) is
    silently ignored by returning an empty list when the MAC pattern doesn't match.

This module has no Home Assistant dependencies. It is consumed by both the
add-on (which owns the UDP socket) and the integration test suite.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

_LOGGER = logging.getLogger(__name__)

MAC_PATTERN = re.compile(r"\[([0-9A-F]{6})-([0-9A-F]{6})\]")
_FRAME_SPLIT = re.compile(r"]<|><|>")
# A valid device block starts with the port-ID digits followed by a comma —
# e.g. `01,6,...` (port 1) or `10,3,...` (port 10). This rejects empty
# trailing fragments from _FRAME_SPLIT without hard-coding a leading digit
# (which would silently drop any port >= 10).
_DEVICE_BLOCK = re.compile(r"^\d+,\d+")

KIND_INVERTER = "inverter"
KIND_CHARGE_CONTROLLER = "charge_controller"

_INVERTER_MODE = {
    0: "off",
    1: "search",
    2: "inverting",
    3: "charging",
    4: "silent",
    5: "floating",
    6: "equalizing",
    7: "charger-off",
    8: "charger-off",
    9: "selling",
    10: "pass-through",
    11: "slave-on",
    12: "slave-off",
    14: "offsetting",
    90: "inverter-error",
    91: "ags-error",
    92: "comm-error",
}

_AC_MODE = {0: "no-ac", 1: "ac-drop", 2: "ac-use"}

_CHARGE_MODE = {0: "silent", 1: "float", 2: "bulk", 3: "absorb", 4: "eq"}


@dataclass(frozen=True)
class DeviceUpdate:
    """One device's parsed state from a single UDP frame."""

    mac: str
    kind: str
    index: int
    state: dict[str, Any] = field(default_factory=dict)


def parse_frame(data: bytes, remote_ip: str) -> list[DeviceUpdate]:
    """Parse one MATE3 UDP datagram. Returns updates for each device in the frame.

    Returns an empty list when the payload isn't a telemetry frame (for example,
    MATE3 broadcasts filesystem/HTTP log lines on the same port).
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        _LOGGER.debug("Non-UTF-8 payload from %s; ignoring", remote_ip)
        return []

    match = MAC_PATTERN.match(text)
    if not match:
        return []

    mac = match.group(1) + match.group(2)
    _, *blocks = _FRAME_SPLIT.split(text)
    blocks = [b for b in blocks if _DEVICE_BLOCK.match(b)]

    per_type_count: dict[int, int] = {}
    updates: list[DeviceUpdate] = []

    for block in blocks:
        values = block.split(",")
        if len(values) < 2:
            continue
        try:
            device_type = int(values[1])
        except ValueError:
            _LOGGER.debug("Unparseable device block from %s: %r", remote_ip, block)
            continue

        index = per_type_count.get(device_type, 0) + 1
        per_type_count[device_type] = index

        try:
            if device_type == 6:
                state = _parse_inverter(values)
                updates.append(DeviceUpdate(mac, KIND_INVERTER, index, state))
            elif device_type == 3:
                state = _parse_charge_controller(values)
                updates.append(DeviceUpdate(mac, KIND_CHARGE_CONTROLLER, index, state))
            else:
                _LOGGER.debug("Unknown device type %d from %s", device_type, remote_ip)
        except (IndexError, ValueError) as exc:
            _LOGGER.warning("Failed to parse device block %r: %s", block, exc)
            continue

    return updates


def _parse_inverter(values: list[str]) -> dict[str, Any]:
    # AC factor scales raw voltages from 120V to 240V-style hardware.
    ac_factor = 2.0 if float(values[6]) > 150.0 else 1.0

    l1_inverter_current = float(values[2])
    l1_charger_current = float(values[3])
    l1_buy_current = float(values[4])
    l1_sell_current = float(values[5])
    l1_ac_input_voltage = float(values[6]) * ac_factor
    l1_ac_output_voltage = float(values[8]) * ac_factor

    l2_inverter_current = float(values[2 + 7])
    l2_charger_current = float(values[3 + 7])
    l2_buy_current = float(values[4 + 7])
    l2_sell_current = float(values[5 + 7])
    l2_ac_input_voltage = float(values[6 + 7]) * ac_factor
    l2_ac_output_voltage = float(values[8 + 7]) * ac_factor

    # Positive grid power = buying (consumption), negative = selling (production).
    l1_grid_power = (l1_buy_current * l1_ac_input_voltage) - (
        l1_sell_current * l1_ac_output_voltage
    )
    l2_grid_power = (l2_buy_current * l2_ac_input_voltage) - (
        l2_sell_current * l2_ac_output_voltage
    )

    l1_inverter_power = l1_inverter_current * l1_ac_output_voltage
    l1_charger_power = l1_charger_current * l1_ac_input_voltage
    l2_inverter_power = l2_inverter_current * l2_ac_output_voltage
    l2_charger_power = l2_charger_current * l2_ac_input_voltage

    state: dict[str, Any] = {
        "l1_inverter_current": l1_inverter_current,
        "l1_charger_current": l1_charger_current,
        "l1_buy_current": l1_buy_current,
        "l1_sell_current": l1_sell_current,
        "l1_ac_input_voltage": l1_ac_input_voltage,
        "l1_ac_output_voltage": l1_ac_output_voltage,
        "l1_grid_power": l1_grid_power,
        "l1_inverter_power": l1_inverter_power,
        "l1_charger_power": l1_charger_power,
        "l2_inverter_current": l2_inverter_current,
        "l2_charger_current": l2_charger_current,
        "l2_buy_current": l2_buy_current,
        "l2_sell_current": l2_sell_current,
        "l2_ac_input_voltage": l2_ac_input_voltage,
        "l2_ac_output_voltage": l2_ac_output_voltage,
        "l2_grid_power": l2_grid_power,
        "l2_inverter_power": l2_inverter_power,
        "l2_charger_power": l2_charger_power,
        "grid_power": l1_grid_power + l2_grid_power,
        "inverter_power": l1_inverter_power + l2_inverter_power,
        "charger_power": l1_charger_power + l2_charger_power,
        "inverter_current": l1_inverter_current + l2_inverter_current,
        "charger_current": l1_charger_current + l2_charger_current,
        "total_ac_input_voltage": l1_ac_input_voltage + l2_ac_input_voltage,
        "total_ac_output_voltage": l1_ac_output_voltage + l2_ac_output_voltage,
        "battery_voltage": float(values[12]),
    }

    state["inverter_mode"] = _INVERTER_MODE.get(int(values[16]), "unknown")
    state["ac_mode"] = _AC_MODE.get(int(values[18]), "unknown")
    # Bit 6 of the mode byte distinguishes grid from generator.
    state["grid_mode"] = "grid" if (int(values[20]) & (1 << 6)) else "generator"

    return state


def _parse_charge_controller(values: list[str]) -> dict[str, Any]:
    pv_current = float(values[4])
    pv_voltage = float(values[5])
    output_current = float(values[3])
    # Battery voltage is sent as integer tenths of a volt.
    battery_voltage = float(values[11]) / 10.0

    return {
        "pv_current": pv_current,
        "pv_voltage": pv_voltage,
        "output_current": output_current,
        "output_power": output_current * battery_voltage,
        "pv_power": pv_current * pv_voltage,
        "battery_voltage": battery_voltage,
        "kwh_today": float(values[13]),
        "charge_mode": _CHARGE_MODE.get(int(values[10]), "unknown"),
    }
