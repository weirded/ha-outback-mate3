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


def _volt_tenths(el: ET.Element | None) -> float | None:
    """Battery / DC voltages in CONFIG.xml are stored as tenths of a volt.

    Example: ``<Voltage>552</Voltage>`` for an absorb setpoint means 55.2 V.
    AC voltages (120 V, 240 V line-side values) are stored directly and
    should use :func:`_int` instead.
    """
    v = _int(el)
    return v / 10.0 if v is not None else None


def _amp_tenths(el: ET.Element | None) -> float | None:
    """Most current values in CONFIG.xml are stored as tenths of an amp.

    Example: ``<Output_Limit>800</Output_Limit>`` on a FLEXmax 80 means
    80.0 A (the max the unit can push, not 800 A).
    """
    v = _int(el)
    return v / 10.0 if v is not None else None


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

    # --- system-wide setpoints / coordination / transfer thresholds ---

    # Low SOC thresholds
    out["low_soc_warning_percentage"] = _int(remote.find("Low_SOC_Warning_Percentage"))
    out["low_soc_error_percentage"] = _int(remote.find("Low_SOC_Error_Percentage"))

    # Coordination modes
    ccf = remote.find("CC_Float_Coordination")
    if ccf is not None:
        out["cc_float_coordination_mode"] = ccf.get("Mode")
    mpc = remote.find("Multi_Phase_Coordination")
    if mpc is not None:
        out["multi_phase_coordination_mode"] = mpc.get("Mode")

    # AC Coupled Control
    acc = remote.find("AC_Coupled_Control")
    if acc is not None:
        out["ac_coupled_control_mode"] = acc.get("Mode")
        out["ac_coupled_control_aux_output"] = _int(acc.find("AUX_Output"))

    # Global CC output cap
    gcc = remote.find("Global_Charge_Controller_Output_Control")
    if gcc is not None:
        out["global_cc_control_mode"] = gcc.get("Mode")
        out["global_cc_max_charge_rate"] = _amp_tenths(gcc.find("Max_Charge_Rate"))

    # SunSpec / Time zone
    nopts = remote.find("Network_Options")
    if nopts is not None:
        out["sunspec_mode"] = _text(nopts.find("SunSpec"))
        out["sunspec_port"] = _int(nopts.find("SunSpec_Port"))
        out["time_zone_raw"] = _int(nopts.find("Time_Zone"))

    # FNDC (FlexNet DC) integration
    fndc_ct = remote.find("FNDC_Charge_Term_Control")
    if fndc_ct is not None:
        out["fndc_charge_term_mode"] = fndc_ct.get("Mode")
    fndc_sell = remote.find("FNDC_Sell_Control")
    if fndc_sell is not None:
        out["fndc_sell_mode"] = fndc_sell.get("Mode")

    # Grid Mode Schedules 1, 2, 3
    for n in (1, 2, 3):
        gms = remote.find(f"Grid_Mode_Schedule_{n}")
        if gms is None:
            continue
        out[f"grid_mode_schedule_{n}_mode"] = gms.get("Mode")
        out[f"grid_mode_schedule_{n}_enable_hour"] = _int(gms.find("Enable_Hour"))
        out[f"grid_mode_schedule_{n}_enable_min"] = _int(gms.find("Enable_Min"))

    # High Battery Transfer (HVT / LVC / SOC)
    hvt = remote.find("High_Battery_Transfer")
    if hvt is not None:
        out["hvt_mode"] = hvt.get("Mode")
        hvd = hvt.find("High_Voltage_Disconnect")
        if hvd is not None:
            out["hvt_disconnect_voltage"] = _volt_tenths(hvd.find("Voltage"))
            out["hvt_disconnect_delay"] = _int(hvd.find("Delay"))
        lvc = hvt.find("Low_Voltage_Connect")
        if lvc is not None:
            out["hvt_reconnect_voltage"] = _volt_tenths(lvc.find("Voltage"))
            out["hvt_reconnect_delay"] = _int(lvc.find("Delay"))
        out["hvt_soc_connect_pct"] = _int(hvt.find("SOC_Connect_Percentage"))
        out["hvt_soc_disconnect_pct"] = _int(hvt.find("SOC_Disconnect_Percentage"))

    # Load Grid Transfer (load shedding)
    lgt = remote.find("Load_Grid_Transfer")
    if lgt is not None:
        out["lgt_mode"] = lgt.get("Mode")
        out["lgt_load_threshold_kw"] = _int(lgt.find("Load_Threshold_KW"))
        out["lgt_connect_delay"] = _int(lgt.find("Load_Connect_Delay"))
        out["lgt_disconnect_delay"] = _int(lgt.find("Load_Disconnect_Delay"))
        out["lgt_low_battery_connect_voltage"] = _volt_tenths(lgt.find("Low_Battery_Connect"))
        out["lgt_high_battery_disconnect_voltage"] = _volt_tenths(lgt.find("High_Battery_Disconnect"))

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
        out["ac_coupled_mode"] = _text(inv.find("AC_Coupled_Mode"))
        search = inv.find("Search")
        if search is not None:
            out["search_pulse_length"] = _int(search.find("Pulse_Length"))
            out["search_ac_load_threshold_amps"] = _amp_tenths(search.find("Amps"))
            out["search_pulse_spacing"] = _int(search.find("Spacing"))
        lb = inv.find("Low_battery")
        if lb is not None:
            out["low_battery_cut_out_voltage"] = _volt_tenths(lb.find("Cut_Out_Voltage"))
            out["low_battery_cut_in_voltage"] = _volt_tenths(lb.find("Cut_In_Voltage"))
            out["low_battery_delay"] = _int(lb.find("Delay"))
        hb = inv.find("High_battery")
        if hb is not None:
            out["high_battery_cut_out_voltage"] = _volt_tenths(hb.find("Cut_Out_Voltage"))
            out["high_battery_cut_in_voltage"] = _volt_tenths(hb.find("Cut_In_Voltage"))
            out["high_battery_delay"] = _int(hb.find("Delay"))
    ch = dev.find("Charger")
    if ch is not None:
        out["charger_mode"] = ch.get("Mode")
        out["charger_absorb_voltage"] = _volt_tenths(ch.find("Absorb/Voltage"))
        out["charger_absorb_time"] = _int(ch.find("Absorb/Time"))
        out["charger_float_voltage"] = _volt_tenths(ch.find("Float/Voltage"))
        out["charger_float_time"] = _int(ch.find("Float/Time"))
        out["charger_eq_voltage"] = _volt_tenths(ch.find("EQ/Voltage"))
        out["charger_eq_time"] = _int(ch.find("EQ/Time"))
        out["charger_re_float_voltage"] = _volt_tenths(ch.find("Re_Float/Voltage"))
        out["charger_re_bulk_voltage"] = _volt_tenths(ch.find("Re_Bulk/Voltage"))
        out["charger_ac_input_limit"] = _amp_tenths(ch.find("AC_Charger_Input_Limit"))
    gt = dev.find("Grid_tie")
    if gt is not None:
        out["grid_tie_mode"] = gt.get("Mode")
        out["grid_tie_voltage"] = _volt_tenths(gt.find("Voltage"))
        out["grid_tie_window"] = _text(gt.find("Window"))
    mg = dev.find("Mini_Grid")
    if mg is not None:
        out["mini_grid_lbx_voltage"] = _volt_tenths(mg.find("LBX_Voltage"))
        out["mini_grid_lbx_delay"] = _int(mg.find("LBX_Delay"))
    gz = dev.find("Grid_Zero")
    if gz is not None:
        out["grid_zero_voltage"] = _volt_tenths(gz.find("Voltage"))
        out["grid_zero_max_amps"] = _amp_tenths(gz.find("Max_Amps"))
    for ac_tag, prefix in [("AC1_input", "ac1"), ("AC2_input", "ac2")]:
        ac = dev.find(ac_tag)
        if ac is None:
            continue
        out[f"{prefix}_input_type"] = _text(ac.find("Input_type"))
        out[f"{prefix}_input_size_amps"] = _amp_tenths(ac.find("Input_size"))
        out[f"{prefix}_transfer_delay"] = _int(ac.find("Transfer_Delay"))
        out[f"{prefix}_connect_delay"] = _int(ac.find("Connect_Delay"))
        out[f"{prefix}_min_voltage"] = _int(ac.find("Minimum_Input_Voltage"))
        out[f"{prefix}_max_voltage"] = _int(ac.find("Maximum_Input_Voltage"))
    stack = dev.find("Stack")
    if stack is not None:
        out["stack_mode"] = stack.get("Mode")
        out["stack_master_power_save_level"] = _int(stack.find("Master_Power_Save_Level"))
        out["stack_slave_power_save_level"] = _int(stack.find("Slave_Power_Save_Level"))
    # AUX 12V output + Relay share identical sub-structure on the Radian/GS.
    for xml_tag, prefix in [("AUX_Output", "aux_output"), ("Relay", "relay")]:
        el = dev.find(xml_tag)
        if el is None:
            continue
        out[f"{prefix}_mode"] = el.get("Mode")
        out[f"{prefix}_operation_mode"] = _text(el.find("Operation_Mode"))
        out[f"{prefix}_on_delay"] = _int(el.find("On_Delay"))
        out[f"{prefix}_off_delay"] = _int(el.find("Off_Delay"))
        out[f"{prefix}_high_setpoint_voltage"] = _volt_tenths(el.find("High_Setpoint_Voltage"))
        out[f"{prefix}_low_setpoint_voltage"] = _volt_tenths(el.find("Low_Setpoint_Voltage"))
        out[f"{prefix}_high_setpoint_ac_amps"] = _amp_tenths(el.find("High_Setpoint_AC_Amps"))
        out[f"{prefix}_low_setpoint_ac_amps"] = _amp_tenths(el.find("Low_Setpoint_AC_Amps"))
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
        out["charger_absorb_voltage"] = _volt_tenths(ch.find("Absorb/Voltage"))
        out["charger_absorb_time"] = _int(ch.find("Absorb/Time"))
        out["charger_absorb_end_amps"] = _amp_tenths(ch.find("Absorb/End_Amps"))
        out["charger_float_voltage"] = _volt_tenths(ch.find("Float_Voltage"))
        out["charger_rebulk_voltage"] = _volt_tenths(ch.find("Rebulk_Voltage"))
        out["charger_eq_voltage"] = _volt_tenths(ch.find("EQ/Voltage"))
        out["charger_eq_time"] = _int(ch.find("EQ/Time"))
        out["charger_eq_auto_interval_days"] = _int(ch.find("EQ/Auto_Interval"))
        out["charger_output_limit"] = _amp_tenths(ch.find("Output_Limit"))
    wake = model.find("Wakeup")
    if wake is not None:
        out["wakeup_interval"] = _int(wake.find("Interval"))
        out["wakeup_voc_change"] = _volt_tenths(wake.find("VOC_Change"))
    out["snooze_amps"] = _amp_tenths(model.find("Snooze_Amps"))
    mppt = model.find("MPPT")
    if mppt is not None:
        out["mppt_mode"] = mppt.get("Mode")
        out["mppt_sweep_mode"] = _text(mppt.find("Sweep_Mode"))
        out["mppt_max_sweep"] = _int(mppt.find("Max_Sweep"))
        out["mppt_upick_percentage"] = _int(mppt.find("Upick_Percentage"))
        out["mppt_restart_mode"] = _int(mppt.find("Restart_Mode"))
    rts = model.find("Remote_Temp_Sensor_Comp")
    if rts is not None:
        out["rts_mode"] = rts.get("Mode")
        out["rts_maximum_voltage"] = _volt_tenths(rts.find("Maximum_RTS_Voltage"))
        out["rts_minimum_voltage"] = _volt_tenths(rts.find("Minimum_RTS_Voltage"))
    aux = model.find("AUX_Output")
    if aux is not None:
        out["aux_mode"] = aux.get("Mode")
        out["aux_operation_mode"] = _text(aux.find("Operation_Mode"))
        out["aux_polarity"] = _text(aux.find("Polarity"))
        out["aux_error_low_batt_voltage"] = _volt_tenths(aux.find("AUX_Error_Low_Batt_Voltage"))
        disc = aux.find("AUX_Low_Batt_Disconnect")
        if disc is not None:
            out["aux_low_batt_disconnect_voltage"] = _volt_tenths(disc.find("Disconnect_Voltage"))
            out["aux_low_batt_disconnect_delay"] = _int(disc.find("Disconnect_Delay"))
            out["aux_low_batt_reconnect_voltage"] = _volt_tenths(disc.find("Reconnect_Voltage"))
        out["aux_vent_fan_voltage"] = _volt_tenths(aux.find("AUX_Vent_Fan_Voltage"))
        div = aux.find("AUX_Diversion")
        if div is not None:
            out["aux_diversion_hold_time"] = _int(div.find("Hold_Time"))
            out["aux_diversion_delay"] = _int(div.find("Delay"))
            out["aux_diversion_relative_voltage"] = _volt_tenths(div.find("Relative_Voltage"))
            out["aux_diversion_hysteresis_voltage"] = _volt_tenths(div.find("Hysteresis_Voltage"))
        pvt = aux.find("AUX_PV_Trigger")
        if pvt is not None:
            out["aux_pv_trigger_voltage"] = _volt_tenths(pvt.find("Trigger_Voltage"))
            out["aux_pv_trigger_hold_time"] = _int(pvt.find("Hold_Time"))
        nite = aux.find("AUX_Nite_Light")
        if nite is not None:
            out["aux_nite_light_threshold_voltage"] = _volt_tenths(nite.find("Threshold_Voltage"))
            out["aux_nite_light_on_hyst_time"] = _int(nite.find("On_Hyst_Time"))
            out["aux_nite_light_off_hyst_time"] = _int(nite.find("Off_Hyst_Time"))
            out["aux_nite_light_on_hours"] = _int(nite.find("On_Hours"))
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
