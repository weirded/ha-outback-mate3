"""MATE3 HTTP-config entity schema.

Describes the diagnostic entities the integration should materialize from
the ``config_snapshot`` dict (produced by the periodic MATE3 CONFIG.xml
poll). Companion to :mod:`src.schema` which describes UDP-derived *live*
entities.

Rationale
---------
The config snapshot has a fixed shape:

    {
      "system": {...},
      "mate3":  {...},
      "inverters":         [ {..}, {..}, ... ],  # MATE3 port order
      "charge_controllers":[ {..}, {..}, ... ],
    }

Each :class:`ConfigEntitySpec` tells the integration how to turn one
config value into a Home Assistant diagnostic sensor:

* System specs carry a ``section`` (``"system"`` or ``"mate3"``) naming
  which sub-dict to read from. ``source_key`` names the dict key.
* Inverter / charge-controller specs read from the per-port dict
  (``config["inverters"][i-1]`` / ``config["charge_controllers"][i-1]``);
  ``section`` is ``None``.

The spec is HA-agnostic: ``device_class`` / ``unit`` are plain strings
matching HA's wire constants. The integration maps them back to
:class:`~homeassistant.components.sensor.SensorDeviceClass` etc.

Composite values (e.g. ``data_stream_target`` = ``"<ip>:<port>"``) are
precomputed by :mod:`src.mate3_http` into the snapshot so the spec stays
declarative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# HA wire-compatible device classes (plain strings — keep add-on HA-free).
_DC_VOLTAGE = "voltage"
_DC_CURRENT = "current"
_DC_POWER = "power"

_U_A = "A"
_U_V = "V"
_U_W = "W"


@dataclass(frozen=True)
class ConfigEntitySpec:
    """One CONFIG.xml-derived entity the integration should materialize."""

    key: str
    name: str
    device_class: str | None = None
    unit: str | None = None
    is_firmware: bool = False
    translation_key: str | None = None
    # System entries only: which sub-dict of the snapshot to read from.
    section: str | None = None
    # Name of the key inside that sub-dict; defaults to ``key`` when None.
    source_key: str | None = None

    @property
    def effective_source_key(self) -> str:
        return self.source_key or self.key

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "device_class": self.device_class,
            "unit": self.unit,
            "is_firmware": self.is_firmware,
            "translation_key": self.translation_key or self.key,
            "section": self.section,
            "source_key": self.effective_source_key,
        }


def _sys(key: str, name: str, **kw: Any) -> ConfigEntitySpec:
    return ConfigEntitySpec(key=key, name=name, section="system", **kw)


def _m3(key: str, name: str, **kw: Any) -> ConfigEntitySpec:
    return ConfigEntitySpec(key=key, name=name, section="mate3", **kw)


def _volt_sys(key: str, name: str) -> ConfigEntitySpec:
    return _sys(key, name, device_class=_DC_VOLTAGE, unit=_U_V)


def _volt_m3(key: str, name: str) -> ConfigEntitySpec:
    return _m3(key, name, device_class=_DC_VOLTAGE, unit=_U_V)


def _amp_m3(key: str, name: str) -> ConfigEntitySpec:
    return _m3(key, name, device_class=_DC_CURRENT, unit=_U_A)


# --- System-level config entities -------------------------------------------
#
# Mix of `system`-block and `mate3`-block entries. The `data_stream_target`
# composite is precomputed by `mate3_http.extract_config` into the `mate3`
# block, so it's a regular spec here (no getter lambdas).

SYSTEM_CONFIG_ENTITIES: list[ConfigEntitySpec] = [
    _m3("mate3_firmware", "MATE3 Firmware", source_key="firmware", is_firmware=True),
    _m3("data_stream_target", "Data Stream Target"),
    _m3("data_stream_mode", "Data Stream Mode"),
    _m3("sd_card_log_mode", "SD Card Log Mode"),
    _m3("mate3_ip_address", "MATE3 IP Address", source_key="ip_address"),
    _m3("mate3_dhcp", "MATE3 DHCP", source_key="dhcp"),
    _m3("mate3_gateway", "MATE3 Gateway", source_key="gateway"),
    _sys("system_type", "System Type"),
    _sys("nominal_voltage", "Nominal Voltage", device_class=_DC_VOLTAGE, unit=_U_V),
    _sys("battery_ah_capacity", "Battery Ah Capacity", unit="Ah"),
    _sys("pv_size_watts", "PV Size", device_class=_DC_POWER, unit=_U_W),
    _sys("generator_kw", "Generator Rating", unit="kW"),
    _sys("max_inverter_output_kw", "Max Inverter Output", unit="kW"),
    _sys("max_charger_output_kw", "Max Charger Output", unit="kW"),
    # Low SOC thresholds
    _m3("low_soc_warning_percentage", "Low SOC Warning", unit="%"),
    _m3("low_soc_error_percentage", "Low SOC Error", unit="%"),
    # Coordination
    _m3("cc_float_coordination_mode", "CC Float Coordination"),
    _m3("multi_phase_coordination_mode", "Multi-Phase Coordination"),
    # AC coupling
    _m3("ac_coupled_control_mode", "AC Coupled Control"),
    _m3("ac_coupled_control_aux_output", "AC Coupled AUX Output"),
    # Global CC output cap
    _m3("global_cc_control_mode", "Global CC Output Control"),
    _amp_m3("global_cc_max_charge_rate", "Global CC Max Charge Rate"),
    # SunSpec / Modbus / Time zone
    _m3("sunspec_mode", "SunSpec Server"),
    _m3("sunspec_port", "SunSpec Port"),
    _m3("time_zone_raw", "MATE3 Time Zone (raw)"),
    # FNDC
    _m3("fndc_charge_term_mode", "FNDC Charge Term Control"),
    _m3("fndc_sell_mode", "FNDC Sell Control"),
    # Grid Mode Schedules 1/2/3
    _m3("grid_mode_schedule_1_mode", "Grid Mode Schedule 1"),
    _m3("grid_mode_schedule_1_enable_hour", "Grid Mode Schedule 1 Hour"),
    _m3("grid_mode_schedule_1_enable_min", "Grid Mode Schedule 1 Minute"),
    _m3("grid_mode_schedule_2_mode", "Grid Mode Schedule 2"),
    _m3("grid_mode_schedule_2_enable_hour", "Grid Mode Schedule 2 Hour"),
    _m3("grid_mode_schedule_2_enable_min", "Grid Mode Schedule 2 Minute"),
    _m3("grid_mode_schedule_3_mode", "Grid Mode Schedule 3"),
    _m3("grid_mode_schedule_3_enable_hour", "Grid Mode Schedule 3 Hour"),
    _m3("grid_mode_schedule_3_enable_min", "Grid Mode Schedule 3 Minute"),
    # High Battery Transfer
    _m3("hvt_mode", "HVT Mode"),
    _volt_m3("hvt_disconnect_voltage", "HVT Disconnect Voltage"),
    _m3("hvt_disconnect_delay", "HVT Disconnect Delay"),
    _volt_m3("hvt_reconnect_voltage", "HVT Reconnect Voltage"),
    _m3("hvt_reconnect_delay", "HVT Reconnect Delay"),
    _m3("hvt_soc_connect_pct", "HVT Reconnect SOC", unit="%"),
    _m3("hvt_soc_disconnect_pct", "HVT Disconnect SOC", unit="%"),
    # Load Grid Transfer (load shedding)
    _m3("lgt_mode", "Load-Grid Transfer"),
    _m3("lgt_load_threshold_kw", "Load-Grid Threshold", unit="kW"),
    _m3("lgt_connect_delay", "Load-Grid Connect Delay"),
    _m3("lgt_disconnect_delay", "Load-Grid Disconnect Delay"),
    _volt_m3("lgt_low_battery_connect_voltage", "Load-Grid Low Battery Connect"),
    _volt_m3("lgt_high_battery_disconnect_voltage", "Load-Grid High Battery Disconnect"),
    # Advanced Generator Start (AGS)
    _m3("ags_mode", "AGS"),
    _m3("ags_control", "AGS Control"),
    _m3("ags_generator_type", "AGS Generator Type"),
    _m3("ags_port", "AGS Port"),
    _m3("ags_cooldown_time", "AGS Cooldown Time"),
    _m3("ags_warmup_time", "AGS Warmup Time"),
    _m3("ags_fault_time", "AGS Fault Time"),
    _m3("ags_ac_input_reconnect_delay", "AGS AC Input Reconnect Delay"),
    _m3("ags_dc_generator_absorb_time", "AGS DC Generator Absorb Time"),
    _volt_m3("ags_dc_generator_absorb_voltage", "AGS DC Generator Absorb Voltage"),
    _m3("ags_fndc_full_charge_mode", "AGS FNDC Full Charge"),
    _m3("ags_fndc_full_charge_interval", "AGS FNDC Full Charge Interval", unit="d"),
    # Generator Exercise
    _m3("ags_generator_exercise_mode", "AGS Generator Exercise"),
    _m3("ags_generator_exercise_day", "AGS Generator Exercise Day"),
    _m3("ags_generator_exercise_interval", "AGS Generator Exercise Interval"),
    _m3("ags_generator_exercise_period", "AGS Generator Exercise Period"),
    _m3("ags_generator_exercise_sell_during", "AGS Sell During Exercise"),
    _m3("ags_generator_exercise_start_hour", "AGS Generator Exercise Start Hour"),
    _m3("ags_generator_exercise_start_min", "AGS Generator Exercise Start Min"),
    # Load Start
    _m3("ags_load_start_mode", "AGS Load Start"),
    _m3("ags_load_start_start_delay", "AGS Load Start Start Delay"),
    _m3("ags_load_start_stop_delay", "AGS Load Start Stop Delay"),
    # Load_KW is kW in CONFIG.xml — naming and unit follow that.
    _m3("ags_load_start_start_load_kw", "AGS Load Start Start Load", unit="kW"),
    _m3("ags_load_start_stop_load_kw", "AGS Load Start Stop Load", unit="kW"),
    # Must Run schedule (one-shot if set; otherwise disabled)
    _m3("ags_must_run_mode", "AGS Must Run"),
    _m3("ags_must_run_weekday_start_hour", "AGS Must Run Weekday Start Hour"),
    _m3("ags_must_run_weekday_start_min", "AGS Must Run Weekday Start Min"),
    _m3("ags_must_run_weekday_stop_hour", "AGS Must Run Weekday Stop Hour"),
    _m3("ags_must_run_weekday_stop_min", "AGS Must Run Weekday Stop Min"),
    _m3("ags_must_run_weekend_start_hour", "AGS Must Run Weekend Start Hour"),
    _m3("ags_must_run_weekend_start_min", "AGS Must Run Weekend Start Min"),
    _m3("ags_must_run_weekend_stop_hour", "AGS Must Run Weekend Stop Hour"),
    _m3("ags_must_run_weekend_stop_min", "AGS Must Run Weekend Stop Min"),
    # Quiet Time (generator lockout window)
    _m3("ags_quiet_time_mode", "AGS Quiet Time"),
    _m3("ags_quiet_time_weekday_start_hour", "AGS Quiet Time Weekday Start Hour"),
    _m3("ags_quiet_time_weekday_start_min", "AGS Quiet Time Weekday Start Min"),
    _m3("ags_quiet_time_weekday_stop_hour", "AGS Quiet Time Weekday Stop Hour"),
    _m3("ags_quiet_time_weekday_stop_min", "AGS Quiet Time Weekday Stop Min"),
    _m3("ags_quiet_time_weekend_start_hour", "AGS Quiet Time Weekend Start Hour"),
    _m3("ags_quiet_time_weekend_start_min", "AGS Quiet Time Weekend Start Min"),
    _m3("ags_quiet_time_weekend_stop_hour", "AGS Quiet Time Weekend Stop Hour"),
    _m3("ags_quiet_time_weekend_stop_min", "AGS Quiet Time Weekend Stop Min"),
    # SOC start/stop
    _m3("ags_soc_start_mode", "AGS SOC Start"),
    _m3("ags_soc_start_start_percentage", "AGS SOC Start %", unit="%"),
    _m3("ags_soc_start_stop_percentage", "AGS SOC Stop %", unit="%"),
    # Voltage starts
    _m3("ags_two_min_voltage_start_mode", "AGS 2-Min Voltage Start"),
    _volt_m3("ags_two_min_voltage_start_voltage", "AGS 2-Min Voltage"),
    _m3("ags_two_hour_voltage_start_mode", "AGS 2-Hour Voltage Start"),
    _volt_m3("ags_two_hour_voltage_start_voltage", "AGS 2-Hour Voltage"),
    _m3("ags_twenty_four_hour_voltage_start_mode", "AGS 24-Hour Voltage Start"),
    _volt_m3("ags_twenty_four_hour_voltage_start_voltage", "AGS 24-Hour Voltage"),
]


# Programmatically append the 19 Grid_Use entries × 3 profiles = 57 specs.
for _prefix, _label in (
    ("grid_use", "Grid Use"),
    ("grid_use_p2", "Grid Use P2"),
    ("grid_use_p3", "Grid Use P3"),
):
    SYSTEM_CONFIG_ENTITIES.append(_m3(f"{_prefix}_mode", f"{_label} Mode"))
    for _day in ("weekday", "weekend"):
        for _stage in ("drop", "use"):
            for _unit_key, _unit_label in (("hour", "Hour"), ("min", "Min")):
                _key = f"{_prefix}_{_day}_{_stage}_{_unit_key}"
                _name = f"{_label} {_day.capitalize()} {_stage.capitalize()} {_unit_label}"
                SYSTEM_CONFIG_ENTITIES.append(_m3(_key, _name))


# --- Per-inverter config entities -------------------------------------------
#
# Read from `config["inverters"][i-1][source_key]`. Where `source_key` isn't
# supplied, it defaults to `key`. `configured_type` / `configured_inverter_mode`
# are renamed at the integration side to avoid collision with live UDP fields
# of the same name on the inverter device.


def _inv(key: str, name: str, **kw: Any) -> ConfigEntitySpec:
    return ConfigEntitySpec(key=key, name=name, **kw)


def _volt_inv(key: str, name: str) -> ConfigEntitySpec:
    return _inv(key, name, device_class=_DC_VOLTAGE, unit=_U_V)


def _amp_inv(key: str, name: str) -> ConfigEntitySpec:
    return _inv(key, name, device_class=_DC_CURRENT, unit=_U_A)


INVERTER_CONFIG_ENTITIES: list[ConfigEntitySpec] = [
    _inv("firmware", "Firmware", is_firmware=True),
    _inv("configured_type", "Configured Type", source_key="type"),
    _inv("configured_inverter_mode", "Configured Inverter Mode", source_key="inverter_mode"),
    _volt_inv("ac_output_voltage", "AC Output Voltage Setpoint"),
    _volt_inv("low_battery_cut_out_voltage", "Low Battery Cut-Out"),
    _volt_inv("low_battery_cut_in_voltage", "Low Battery Cut-In"),
    _volt_inv("high_battery_cut_out_voltage", "High Battery Cut-Out"),
    _volt_inv("high_battery_cut_in_voltage", "High Battery Cut-In"),
    _inv("charger_mode", "Charger Mode"),
    _volt_inv("charger_absorb_voltage", "Charger Absorb Voltage"),
    _inv("charger_absorb_time", "Charger Absorb Time", unit="min"),
    _volt_inv("charger_float_voltage", "Charger Float Voltage"),
    _volt_inv("charger_eq_voltage", "Charger EQ Voltage"),
    _volt_inv("charger_re_float_voltage", "Charger Re-Float Voltage"),
    _volt_inv("charger_re_bulk_voltage", "Charger Re-Bulk Voltage"),
    _inv("grid_tie_mode", "Grid Tie Mode"),
    _volt_inv("grid_tie_voltage", "Grid Tie Voltage"),
    _inv("grid_tie_window", "Grid Tie Window"),
    _inv("ac_input_priority", "AC Input Priority"),
    _inv("ac1_input_type", "AC1 Input Type"),
    _volt_inv("ac1_min_voltage", "AC1 Min Voltage"),
    _volt_inv("ac1_max_voltage", "AC1 Max Voltage"),
    _inv("ac2_input_type", "AC2 Input Type"),
    _volt_inv("ac2_min_voltage", "AC2 Min Voltage"),
    _volt_inv("ac2_max_voltage", "AC2 Max Voltage"),
    _inv("stack_mode", "Stack Mode"),
    _inv("stack_master_power_save_level", "Stack Master Power-Save Level"),
    _inv("stack_slave_power_save_level", "Stack Slave Power-Save Level"),
    # Search
    _inv("search_pulse_length", "Search Pulse Length"),
    _amp_inv("search_ac_load_threshold_amps", "Search AC Load Threshold"),
    _inv("search_pulse_spacing", "Search Pulse Spacing"),
    # AC coupling
    _inv("ac_coupled_mode", "AC Coupled Mode"),
    # Charger extras
    _inv("charger_float_time", "Charger Float Time", unit="h"),
    # Mini Grid / Grid Zero
    _volt_inv("mini_grid_lbx_voltage", "Mini-Grid LBX Voltage"),
    _inv("mini_grid_lbx_delay", "Mini-Grid LBX Delay"),
    _volt_inv("grid_zero_voltage", "Grid Zero Min Voltage"),
    _amp_inv("grid_zero_max_amps", "Grid Zero Max Amps"),
    # AC1 / AC2 extras
    _amp_inv("ac1_input_size_amps", "AC1 Input Size"),
    _inv("ac1_transfer_delay", "AC1 Transfer Delay"),
    _inv("ac1_connect_delay", "AC1 Connect Delay"),
    _amp_inv("ac2_input_size_amps", "AC2 Input Size"),
    _inv("ac2_transfer_delay", "AC2 Transfer Delay"),
    _inv("ac2_connect_delay", "AC2 Connect Delay"),
    # AUX 12V output
    _inv("aux_output_mode", "AUX Output Mode"),
    _inv("aux_output_operation_mode", "AUX Operation Mode"),
    _inv("aux_output_on_delay", "AUX On Delay"),
    _inv("aux_output_off_delay", "AUX Off Delay"),
    _volt_inv("aux_output_high_setpoint_voltage", "AUX High Setpoint Voltage"),
    _volt_inv("aux_output_low_setpoint_voltage", "AUX Low Setpoint Voltage"),
    _amp_inv("aux_output_high_setpoint_ac_amps", "AUX High Setpoint AC Amps"),
    _amp_inv("aux_output_low_setpoint_ac_amps", "AUX Low Setpoint AC Amps"),
    # Relay
    _inv("relay_mode", "Relay Mode"),
    _inv("relay_operation_mode", "Relay Operation Mode"),
    _inv("relay_on_delay", "Relay On Delay"),
    _inv("relay_off_delay", "Relay Off Delay"),
    _volt_inv("relay_high_setpoint_voltage", "Relay High Setpoint Voltage"),
    _volt_inv("relay_low_setpoint_voltage", "Relay Low Setpoint Voltage"),
    _amp_inv("relay_high_setpoint_ac_amps", "Relay High Setpoint AC Amps"),
    _amp_inv("relay_low_setpoint_ac_amps", "Relay Low Setpoint AC Amps"),
]


# --- Per-charge-controller config entities ----------------------------------


def _cc(key: str, name: str, **kw: Any) -> ConfigEntitySpec:
    return ConfigEntitySpec(key=key, name=name, **kw)


def _volt_cc(key: str, name: str) -> ConfigEntitySpec:
    return _cc(key, name, device_class=_DC_VOLTAGE, unit=_U_V)


def _amp_cc(key: str, name: str) -> ConfigEntitySpec:
    return _cc(key, name, device_class=_DC_CURRENT, unit=_U_A)


CC_CONFIG_ENTITIES: list[ConfigEntitySpec] = [
    _cc("firmware", "Firmware", is_firmware=True),
    _cc("model_type", "Model"),
    _cc("gt_mode", "Grid Tie Mode"),
    _volt_cc("charger_absorb_voltage", "Absorb Voltage"),
    _cc("charger_absorb_time", "Absorb Time", unit="min"),
    _amp_cc("charger_absorb_end_amps", "Absorb End Amps"),
    _volt_cc("charger_float_voltage", "Float Voltage"),
    _volt_cc("charger_rebulk_voltage", "Re-Bulk Voltage"),
    _volt_cc("charger_eq_voltage", "EQ Voltage"),
    _cc("charger_eq_time", "EQ Time", unit="min"),
    _amp_cc("charger_output_limit", "Output Current Limit"),
    _cc("mppt_mode", "MPPT Mode"),
    _cc("mppt_sweep_mode", "MPPT Sweep Mode"),
    _cc("mppt_max_sweep", "MPPT Max Sweep"),
    _cc("mppt_upick_percentage", "MPPT Upick %", unit="%"),
    _cc("mppt_restart_mode", "MPPT Restart Mode"),
    # Charger extras
    _cc("charger_eq_auto_interval_days", "EQ Auto Interval", unit="d"),
    # Wakeup / Snooze
    _cc("wakeup_interval", "Wakeup Interval"),
    _volt_cc("wakeup_voc_change", "Wakeup VOC Change"),
    _amp_cc("snooze_amps", "Snooze Amps"),
    # Remote Temp Sensor
    _cc("rts_mode", "RTS Mode"),
    _volt_cc("rts_maximum_voltage", "RTS Max Voltage"),
    _volt_cc("rts_minimum_voltage", "RTS Min Voltage"),
    # AUX output
    _cc("aux_mode", "AUX Mode"),
    _cc("aux_operation_mode", "AUX Operation Mode"),
    _cc("aux_polarity", "AUX Polarity"),
    _volt_cc("aux_error_low_batt_voltage", "AUX Error Low Battery Voltage"),
    _volt_cc("aux_low_batt_disconnect_voltage", "AUX Low-Batt Disconnect Voltage"),
    _cc("aux_low_batt_disconnect_delay", "AUX Low-Batt Disconnect Delay"),
    _volt_cc("aux_low_batt_reconnect_voltage", "AUX Low-Batt Reconnect Voltage"),
    _volt_cc("aux_vent_fan_voltage", "AUX Vent Fan Voltage"),
    _cc("aux_diversion_hold_time", "AUX Diversion Hold Time"),
    _cc("aux_diversion_delay", "AUX Diversion Delay"),
    _volt_cc("aux_diversion_relative_voltage", "AUX Diversion Relative Voltage"),
    _volt_cc("aux_diversion_hysteresis_voltage", "AUX Diversion Hysteresis Voltage"),
    _volt_cc("aux_pv_trigger_voltage", "AUX PV Trigger Voltage"),
    _cc("aux_pv_trigger_hold_time", "AUX PV Trigger Hold Time"),
    _volt_cc("aux_nite_light_threshold_voltage", "AUX Nite Light Threshold Voltage"),
    _cc("aux_nite_light_on_hyst_time", "AUX Nite Light On Hyst Time"),
    _cc("aux_nite_light_off_hyst_time", "AUX Nite Light Off Hyst Time"),
    _cc("aux_nite_light_on_hours", "AUX Nite Light On Hours", unit="h"),
]


def build_config_schema() -> dict[str, list[dict[str, Any]]]:
    """JSON-ready config-entity schema, keyed by device kind."""
    return {
        "system": [s.to_dict() for s in SYSTEM_CONFIG_ENTITIES],
        "inverter": [s.to_dict() for s in INVERTER_CONFIG_ENTITIES],
        "charge_controller": [s.to_dict() for s in CC_CONFIG_ENTITIES],
    }
