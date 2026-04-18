"""MATE3 HTTP config poller.

Fetches ``http://<host>/CONFIG.xml`` (a ~14 KB XML document the MATE3 serves
on its built-in web UI) and extracts a curated set of values that don't
appear in the UDP stream — firmware versions, nameplate, MATE3 network and
data-stream settings, and the configured charger / inverter setpoints.

The function is intentionally forgiving: missing sections produce missing
keys rather than exceptions, since a MATE3 can omit blocks when a feature
isn't enabled. The top-level keys are:

- ``system``            — nameplate, system type, installer contact
- ``mate3``             — MATE3 remote firmware + its own network + data stream config
- ``inverters``         — list of dicts, one per inverter port (in MATE3 port order)
- ``charge_controllers`` — list of dicts, one per charge controller port
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=8)


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    t = (el.text or "").strip()
    return t or None


def _int(el: ET.Element | None) -> int | None:
    t = _text(el)
    if t is None:
        return None
    try:
        return int(t)
    except ValueError:
        return None


def _parse_system(root: ET.Element) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for child_tag, key in [
        ("Sys_Name", "system_name"),
        ("Sys_Title", "system_title"),
        ("Installed_By", "installed_by"),
        ("Installer_Name", "installer_name"),
        ("Installer_Phone", "installer_phone"),
        ("Nominal_Voltage", "nominal_voltage"),
        ("PV_Size_Watts", "pv_size_watts"),
        ("Battery_AH_Capacity", "battery_ah_capacity"),
        ("Generator_KW", "generator_kw"),
        ("Max_Inverter_Output_KW", "max_inverter_output_kw"),
        ("Max_Charger_Output_KW", "max_charger_output_kw"),
    ]:
        v = _text(root.find(child_tag))
        if v is not None and v != "":
            out[key] = v
    system_type = root.find("System")
    if system_type is not None:
        t = system_type.get("Type")
        if t:
            out["system_type"] = t
    return out


def _parse_mate3(root: ET.Element) -> dict[str, Any]:
    remote = root.find("New_Remote")
    if remote is None:
        return {}
    out: dict[str, Any] = {
        "firmware": _text(remote.find("Firmware")),
        "data_stream_mode": _text(remote.find("Data_Stream_Mode")),
        "sd_card_log_mode": _text(remote.find("SD_CARD_Log_Mode")),
        "sd_card_log_interval_s": _int(remote.find("SD_CARD_Log_Interval")),
        "internal_data_log_interval_s": _int(remote.find("Internal_Data_Log_Interval")),
    }
    network = remote.find("Network")
    if network is not None:
        out.update(
            {
                "dhcp": _text(network.find("DHCP")),
                "ip_address": _text(network.find("IP_address")),
                "netmask": _text(network.find("Netmask")),
                "gateway": _text(network.find("Gateway")),
                "http_port": _int(network.find("HTTP_Port")),
                "data_stream_ip": _text(network.find("Data_Stream_IP")),
                "data_stream_port": _int(network.find("Data_Stream_Port")),
            }
        )
    return {k: v for k, v in out.items() if v is not None}


def _parse_inverter(dev: ET.Element) -> dict[str, Any]:
    out: dict[str, Any] = {
        "firmware": _text(dev.find("Firmware")),
        "type": _text(dev.find("Type")),
        "nominal_voltage": _text(dev.find("Voltage")),
        "ac_input_priority": _text(dev.find("AC_Input_Priority")),
    }
    inv = dev.find("Inverter")
    if inv is not None:
        out["inverter_mode"] = inv.get("Mode")
        out["ac_output_voltage"] = _int(inv.find("AC_Output_Voltage"))
        lb = inv.find("Low_battery")
        if lb is not None:
            out["low_battery_cut_out_voltage"] = _int(lb.find("Cut_Out_Voltage"))
            out["low_battery_cut_in_voltage"] = _int(lb.find("Cut_In_Voltage"))
            out["low_battery_delay"] = _int(lb.find("Delay"))
        hb = inv.find("High_battery")
        if hb is not None:
            out["high_battery_cut_out_voltage"] = _int(hb.find("Cut_Out_Voltage"))
            out["high_battery_cut_in_voltage"] = _int(hb.find("Cut_In_Voltage"))
            out["high_battery_delay"] = _int(hb.find("Delay"))
    ch = dev.find("Charger")
    if ch is not None:
        out["charger_mode"] = ch.get("Mode")
        out["charger_absorb_voltage"] = _int(ch.find("Absorb/Voltage"))
        out["charger_absorb_time"] = _int(ch.find("Absorb/Time"))
        out["charger_float_voltage"] = _int(ch.find("Float/Voltage"))
        out["charger_eq_voltage"] = _int(ch.find("EQ/Voltage"))
        out["charger_eq_time"] = _int(ch.find("EQ/Time"))
        out["charger_re_float_voltage"] = _int(ch.find("Re_Float/Voltage"))
        out["charger_re_bulk_voltage"] = _int(ch.find("Re_Bulk/Voltage"))
        out["charger_ac_input_limit"] = _int(ch.find("AC_Charger_Input_Limit"))
    gt = dev.find("Grid_tie")
    if gt is not None:
        out["grid_tie_mode"] = gt.get("Mode")
        out["grid_tie_voltage"] = _int(gt.find("Voltage"))
        out["grid_tie_window"] = _text(gt.find("Window"))
    for ac_tag, prefix in [("AC1_input", "ac1"), ("AC2_input", "ac2")]:
        ac = dev.find(ac_tag)
        if ac is None:
            continue
        out[f"{prefix}_input_type"] = _text(ac.find("Input_type"))
        out[f"{prefix}_input_size"] = _int(ac.find("Input_size"))
        out[f"{prefix}_min_voltage"] = _int(ac.find("Minimum_Input_Voltage"))
        out[f"{prefix}_max_voltage"] = _int(ac.find("Maximum_Input_Voltage"))
    stack = dev.find("Stack")
    if stack is not None:
        out["stack_mode"] = stack.get("Mode")
    return {k: v for k, v in out.items() if v is not None}


def _parse_charge_controller(dev: ET.Element) -> dict[str, Any]:
    model = dev.find("Model")
    if model is None:
        return {}
    out: dict[str, Any] = {
        "model_type": model.get("Type"),
        "firmware": _text(model.find("Firmware")),
        "gt_mode": _text(model.find("GT_Mode")),
    }
    ch = model.find("Charger")
    if ch is not None:
        out["charger_absorb_voltage"] = _int(ch.find("Absorb/Voltage"))
        out["charger_absorb_time"] = _int(ch.find("Absorb/Time"))
        out["charger_absorb_end_amps"] = _int(ch.find("Absorb/End_Amps"))
        out["charger_float_voltage"] = _int(ch.find("Float_Voltage"))
        out["charger_rebulk_voltage"] = _int(ch.find("Rebulk_Voltage"))
        out["charger_eq_voltage"] = _int(ch.find("EQ/Voltage"))
        out["charger_eq_time"] = _int(ch.find("EQ/Time"))
        out["charger_output_limit"] = _int(ch.find("Output_Limit"))
    mppt = model.find("MPPT")
    if mppt is not None:
        out["mppt_mode"] = mppt.get("Mode")
        out["mppt_sweep_mode"] = _text(mppt.find("Sweep_Mode"))
        out["mppt_max_sweep"] = _int(mppt.find("Max_Sweep"))
    return {k: v for k, v in out.items() if v is not None}


def parse_config(xml_bytes: bytes) -> dict[str, Any]:
    """Parse a MATE3 CONFIG.xml document into a curated dict.

    Raises ``ValueError`` if the root element is missing — other missing
    bits are returned as absent keys.
    """
    root = ET.fromstring(xml_bytes)
    if root.tag != "System_Config":
        raise ValueError(f"unexpected root element {root.tag!r}")

    out: dict[str, Any] = {
        "system": _parse_system(root),
        "mate3": _parse_mate3(root),
        "inverters": [],
        "charge_controllers": [],
    }
    # Ports in XML order — the MATE3's port numbering (1-based).
    for port in root.findall("Port"):
        dev = port.find("Device")
        if dev is None:
            continue
        dev_type = dev.get("Type")
        if dev_type == "GS":
            out["inverters"].append(_parse_inverter(dev))
        elif dev_type == "CC":
            out["charge_controllers"].append(_parse_charge_controller(dev))
        # Unknown device types are silently skipped.
    return out


async def fetch_config(host: str, timeout: aiohttp.ClientTimeout | None = None) -> dict[str, Any] | None:
    """Fetch + parse CONFIG.xml from ``host``. Returns ``None`` on failure."""
    url = f"http://{host}/CONFIG.xml"
    try:
        async with aiohttp.ClientSession(timeout=timeout or _HTTP_TIMEOUT) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                body = await resp.read()
    except Exception as exc:  # noqa: BLE001
        _LOGGER.debug("Failed to fetch %s: %s", url, exc)
        return None
    try:
        return parse_config(body)
    except ET.ParseError as exc:
        _LOGGER.warning("Malformed CONFIG.xml from %s: %s", host, exc)
        return None
    except ValueError as exc:
        _LOGGER.warning("Unexpected CONFIG.xml from %s: %s", host, exc)
        return None
