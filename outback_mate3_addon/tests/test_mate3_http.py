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
    assert inv["low_battery_cut_out_voltage"] == 480
    assert inv["low_battery_cut_in_voltage"] == 508
    assert inv["high_battery_cut_out_voltage"] == 560


def test_inverter_charger_setpoints(config):
    inv = config["inverters"][0]
    assert inv["charger_mode"] == "Auto"
    assert inv["charger_absorb_voltage"] == 552
    assert inv["charger_float_voltage"] == 532


def test_inverter_grid_tie(config):
    inv = config["inverters"][0]
    assert inv["grid_tie_mode"] == "Enabled"
    assert inv["grid_tie_window"] == "IEEE"
    assert inv["ac_input_priority"] == "Grid"


def test_inverter_ac_inputs(config):
    inv = config["inverters"][0]
    assert inv["ac1_input_type"] == "Grid Tied"
    assert inv["ac1_input_size"] == 2000
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
    assert cc["charger_absorb_voltage"] == 554
    assert cc["charger_float_voltage"] == 535
    assert cc["charger_output_limit"] == 800


def test_cc_mppt(config):
    cc = config["charge_controllers"][0]
    assert cc["mppt_mode"] == "Auto"
    assert cc["mppt_sweep_mode"] == "Half"


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
