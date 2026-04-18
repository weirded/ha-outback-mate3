"""Tests for the MATE3 CONFIG.xml parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.mate3_http import parse_config

FIXTURE = Path(__file__).parent / "fixtures" / "config.xml"


@pytest.fixture(scope="module")
def config():
    return parse_config(FIXTURE.read_bytes())


def test_top_level_sections(config):
    assert set(config) == {"system", "mate3", "inverters", "charge_controllers"}


# --- system nameplate ------------------------------------------------------

def test_system_nameplate(config):
    sys = config["system"]
    assert sys["system_type"] == "Grid Tied"
    assert sys["nominal_voltage"] == "48"
    assert sys["pv_size_watts"] == "1000"
    assert sys["battery_ah_capacity"] == "100"
    assert sys["max_inverter_output_kw"] == "12"
    assert sys["max_charger_output_kw"] == "10"


def test_empty_installer_fields_not_in_output(config):
    # Installer fields are empty strings in XML — should not appear in the dict.
    sys = config["system"]
    assert "installer_name" not in sys
    assert "installer_phone" not in sys
    assert "installed_by" not in sys


# --- mate3 block -----------------------------------------------------------

def test_mate3_firmware_and_stream(config):
    m = config["mate3"]
    assert m["firmware"] == "001.004.007"
    assert m["data_stream_mode"] == "Ethernet"
    assert m["data_stream_ip"] == "192.168.226.135"
    assert m["data_stream_port"] == 57027
    assert m["sd_card_log_mode"] == "Disabled"
    assert m["sd_card_log_interval_s"] == 5


def test_mate3_network_fields(config):
    m = config["mate3"]
    # Whatever the DHCP fallback static config is — just verify fields exist.
    assert m["dhcp"] in {"Enabled", "Disabled"}
    assert "ip_address" in m
    assert "gateway" in m
    assert m["http_port"] == 80


# --- Phase 15: system-wide setpoints and coordination ---------------------

def test_low_soc_thresholds(config):
    m = config["mate3"]
    assert m["low_soc_warning_percentage"] == 60
    assert m["low_soc_error_percentage"] == 50


def test_coordination_modes(config):
    m = config["mate3"]
    assert m["cc_float_coordination_mode"] == "Enabled"
    assert m["multi_phase_coordination_mode"] == "Disabled"


def test_ac_coupled_control(config):
    m = config["mate3"]
    assert m["ac_coupled_control_mode"] == "Disabled"
    assert m["ac_coupled_control_aux_output"] == 1


def test_global_cc_output_control(config):
    m = config["mate3"]
    assert m["global_cc_control_mode"] == "Disabled"
    # 300 in XML tenths = 30.0 A
    assert m["global_cc_max_charge_rate"] == 30.0


def test_sunspec_settings(config):
    m = config["mate3"]
    assert m["sunspec_port"] == 502


def test_fndc_controls(config):
    m = config["mate3"]
    assert m["fndc_charge_term_mode"] == "Disabled"
    assert m["fndc_sell_mode"] == "Disabled"


def test_grid_mode_schedules(config):
    m = config["mate3"]
    assert m["grid_mode_schedule_1_mode"] == "Grid Tied"
    assert m["grid_mode_schedule_1_enable_hour"] == 7
    assert m["grid_mode_schedule_2_mode"] == "GridZero"
    assert m["grid_mode_schedule_2_enable_hour"] == 19


def test_high_battery_transfer(config):
    m = config["mate3"]
    assert m["hvt_mode"] == "Disabled"
    assert m["hvt_disconnect_voltage"] == 52.0
    assert m["hvt_reconnect_voltage"] == 48.0
    assert m["hvt_soc_disconnect_pct"] == 90
    assert m["hvt_soc_connect_pct"] == 60


def test_load_grid_transfer(config):
    m = config["mate3"]
    assert m["lgt_mode"] == "Disabled"
    assert m["lgt_load_threshold_kw"] == 1
    assert m["lgt_low_battery_connect_voltage"] == 48.4
    assert m["lgt_high_battery_disconnect_voltage"] == 56.0


# --- inverters -------------------------------------------------------------

def test_inverter_count(config):
    # Two GS inverters on this system.
    assert len(config["inverters"]) == 2


def test_inverter_firmware_and_type(config):
    inv = config["inverters"][0]
    assert inv["firmware"] == "001.006.070"
    assert inv["type"] == "Split Phase 240V 50/60Hz"
    assert inv["nominal_voltage"] == "48"


def test_inverter_battery_cutoffs(config):
    inv = config["inverters"][0]
    # Battery voltages are stored in CONFIG.xml as tenths; parser normalizes.
    assert inv["low_battery_cut_out_voltage"] == 48.0
    assert inv["low_battery_cut_in_voltage"] == 50.8
    assert inv["high_battery_cut_out_voltage"] == 56.0


def test_inverter_charger_setpoints(config):
    inv = config["inverters"][0]
    assert inv["charger_mode"] == "Auto"
    assert inv["charger_absorb_voltage"] == 55.2
    assert inv["charger_float_voltage"] == 53.2


def test_inverter_grid_tie(config):
    inv = config["inverters"][0]
    assert inv["grid_tie_mode"] == "Enabled"
    assert inv["grid_tie_window"] == "IEEE"
    assert inv["ac_input_priority"] == "Grid"


def test_inverter_ac_inputs(config):
    inv = config["inverters"][0]
    assert inv["ac1_input_type"] == "Grid Tied"
    assert inv["ac1_input_size_amps"] == 200.0
    assert inv["ac2_input_type"] == "Generator"


def test_inverter_stack_mode(config):
    assert config["inverters"][0]["stack_mode"] == "Master"


# --- charge controllers ----------------------------------------------------

def test_cc_count(config):
    assert len(config["charge_controllers"]) == 2


def test_cc_firmware_and_type(config):
    cc = config["charge_controllers"][0]
    assert cc["firmware"] == "003.003.000"
    assert cc["model_type"] == "FM"


def test_cc_setpoints(config):
    cc = config["charge_controllers"][0]
    # Voltages and currents are stored as tenths; parser normalizes.
    assert cc["charger_absorb_voltage"] == 55.4
    assert cc["charger_float_voltage"] == 53.5
    assert cc["charger_output_limit"] == 80.0
    assert cc["charger_absorb_end_amps"] == 10.0


def test_cc_mppt(config):
    cc = config["charge_controllers"][0]
    assert cc["mppt_mode"] == "Auto"
    assert cc["mppt_sweep_mode"] == "Half"


# --- expanded CC coverage (AUX, Wakeup, RTS, MPPT extras) ------------------

def test_cc_wakeup_and_snooze(config):
    cc = config["charge_controllers"][0]
    assert cc["wakeup_interval"] == 5
    assert cc["wakeup_voc_change"] == 6.0
    assert cc["snooze_amps"] == 0.6


def test_cc_rts(config):
    cc = config["charge_controllers"][0]
    assert cc["rts_mode"] == "Wide"
    assert cc["rts_maximum_voltage"] == 55.6
    assert cc["rts_minimum_voltage"] == 48.4


def test_cc_aux_pv_trigger_and_nite_light(config):
    cc = config["charge_controllers"][0]
    assert cc["aux_mode"] == "Vent Fan"
    assert cc["aux_pv_trigger_voltage"] == 140.0
    assert cc["aux_nite_light_threshold_voltage"] == 10.0
    assert cc["aux_nite_light_on_hours"] == 4


# --- expanded inverter coverage (Search, Stack, Mini-Grid, AUX, Relay) -----

def test_inverter_search(config):
    inv = config["inverters"][0]
    assert inv["search_pulse_length"] == 8
    assert inv["search_ac_load_threshold_amps"] == 1.0
    assert inv["search_pulse_spacing"] == 60


def test_inverter_mini_grid_and_grid_zero(config):
    inv = config["inverters"][0]
    assert inv["mini_grid_lbx_voltage"] == 51.2
    assert inv["grid_zero_voltage"] == 51.2
    assert inv["grid_zero_max_amps"] == 120.0


def test_inverter_stack_levels(config):
    inv = config["inverters"][0]
    assert inv["stack_mode"] == "Master"
    assert inv["stack_master_power_save_level"] == 3
    assert inv["stack_slave_power_save_level"] == 1


def test_inverter_aux_output(config):
    inv = config["inverters"][0]
    assert inv["aux_output_mode"] == "Vent Fan"
    assert inv["aux_output_high_setpoint_voltage"] == 56.0
    assert inv["aux_output_high_setpoint_ac_amps"] == 3.0


def test_inverter_relay(config):
    inv = config["inverters"][0]
    assert inv["relay_mode"] == "Gen Alert"
    assert inv["relay_high_setpoint_voltage"] == 56.0


def test_inverter_ac_input_sizes(config):
    inv = config["inverters"][0]
    assert inv["ac1_input_size_amps"] == 200.0
    assert inv["ac2_input_size_amps"] == 25.0


# --- robustness ------------------------------------------------------------

def test_rejects_non_system_config_root():
    with pytest.raises(ValueError):
        parse_config(b"<Something_Else/>")


def test_malformed_xml_raises_parse_error():
    import xml.etree.ElementTree as ET
    with pytest.raises(ET.ParseError):
        parse_config(b"<not really xml")


def test_missing_port_blocks_produces_empty_lists():
    minimal = b"""<?xml version='1.0'?>
<System_Config>
  <Sys_Name>x</Sys_Name>
  <New_Remote><Firmware>9.9.9</Firmware></New_Remote>
</System_Config>"""
    r = parse_config(minimal)
    assert r["inverters"] == []
    assert r["charge_controllers"] == []
    assert r["mate3"]["firmware"] == "9.9.9"
