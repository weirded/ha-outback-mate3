# CONFIG.xml coverage audit

Generated against `outback_mate3_addon/tests/fixtures/config.xml`, captured from a live MATE3 running firmware 001.004.007 with 2 Radian-class inverters (GS) and 2 FLEXmax charge controllers (FM).

**Counts on this system:**

- 368 total XML leaves (attributes + text nodes)
- System-level: 154 leaves — 24 captured, 20 deliberately skipped, **110 not yet captured** (listed below)
- Per-port: 214 leaves across 4 ports; all useful per-device fields already land in the existing per-inverter / per-CC sensor tables. Remaining per-port unexposed leaves are attribute containers (e.g. `Mini_Grid`, `Grid_Zero` when the feature is disabled) — nothing to add there.

---

## System-level values not yet captured

Everything below lives under `System_Config/New_Remote/` unless otherwise noted.

### `AC_Coupled_Control`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/AC_Coupled_Control/AUX_Output` | `1` | ✅ worth surfacing | Which AUX output drives the AC-coupled grid-tie gate |

### `AC_Coupled_Control@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/AC_Coupled_Control@Mode` | `Disabled` | ✅ worth surfacing | AC-coupling enabled? |

### `Advance_Generator_Start` — large, defer

**50 leaves** spanning Must_Run / Quiet_Time / Generator_Exercise / Load_Start / SOC_Start / Two_Min_/Two_Hour_/Twenty_Four_Hour_Voltage_Start + FNDC Full_Charge. AGS has ~50 leaves (time-of-day, SOC, V-based start triggers, gen exercise, etc.). Capture as a block when AGS is actually enabled.

### `Advance_Generator_Start@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Advance_Generator_Start@Mode` | `Disabled` | — | container / internal |

### `CC_Float_Coordination`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/CC_Float_Coordination` | (empty) | — | container / internal |

### `CC_Float_Coordination@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/CC_Float_Coordination@Mode` | `Enabled` | ✅ worth surfacing | Tells CCs to coordinate float voltage with inverter |

### `FNDC_Charge_Term_Control`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/FNDC_Charge_Term_Control` | (empty) | — | container / internal |

### `FNDC_Charge_Term_Control@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/FNDC_Charge_Term_Control@Mode` | `Disabled` | ✅ worth surfacing | FlexNet DC SOC-based charge termination |

### `FNDC_Sell_Control`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/FNDC_Sell_Control` | (empty) | — | container / internal |

### `FNDC_Sell_Control@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/FNDC_Sell_Control@Mode` | `Disabled` | ✅ worth surfacing | FlexNet DC SOC-based sell control |

### `Global_Charge_Controller_Output_Control`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Global_Charge_Controller_Output_Control/Max_Charge_Rate` | `300` | ✅ worth surfacing | Global CC max A |

### `Global_Charge_Controller_Output_Control@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Global_Charge_Controller_Output_Control@Mode` | `Disabled` | ✅ worth surfacing | Global CC current cap enabled |

### `Grid_Mode_Schedule_1`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Grid_Mode_Schedule_1/Enable_Hour` | `7` | ✅ worth surfacing | Grid mode schedule 1 hour |
| `New_Remote/Grid_Mode_Schedule_1/Enable_Min` | `0` | ✅ worth surfacing | Grid mode schedule 1 minute |

### `Grid_Mode_Schedule_1@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Grid_Mode_Schedule_1@Mode` | `Grid Tied` | ✅ worth surfacing | Grid mode at time 1 (Grid Tied / GridZero / etc.) |

### `Grid_Mode_Schedule_2`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Grid_Mode_Schedule_2/Enable_Hour` | `19` | ✅ worth surfacing | Grid mode schedule 2 hour |
| `New_Remote/Grid_Mode_Schedule_2/Enable_Min` | `0` | ✅ worth surfacing | Grid mode schedule 2 minute |

### `Grid_Mode_Schedule_2@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Grid_Mode_Schedule_2@Mode` | `GridZero` | ✅ worth surfacing | Grid mode at time 2 |

### `Grid_Mode_Schedule_3`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Grid_Mode_Schedule_3/Enable_Hour` | `0` | ✅ worth surfacing | Grid mode schedule 3 hour |
| `New_Remote/Grid_Mode_Schedule_3/Enable_Min` | `0` | ✅ worth surfacing | Grid mode schedule 3 minute |

### `Grid_Mode_Schedule_3@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Grid_Mode_Schedule_3@Mode` | `---------` | ✅ worth surfacing | Grid mode at time 3 |

### `High_Battery_Transfer`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/High_Battery_Transfer/High_Voltage_Disconnect/Delay` | `60` | ✅ worth surfacing | HVT disconnect delay |
| `New_Remote/High_Battery_Transfer/High_Voltage_Disconnect/Voltage` | `520` | ✅ worth surfacing | HVT disconnect voltage |
| `New_Remote/High_Battery_Transfer/Low_Voltage_Connect/Delay` | `60` | ✅ worth surfacing | HVT reconnect delay |
| `New_Remote/High_Battery_Transfer/Low_Voltage_Connect/Voltage` | `480` | ✅ worth surfacing | HVT reconnect voltage |
| `New_Remote/High_Battery_Transfer/SOC_Connect_Percentage` | `60` | ✅ worth surfacing | HVT reconnect SOC |
| `New_Remote/High_Battery_Transfer/SOC_Disconnect_Percentage` | `90` | ✅ worth surfacing | HVT disconnect SOC |

### `High_Battery_Transfer@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/High_Battery_Transfer@Mode` | `Disabled` | ✅ worth surfacing | HVT enabled? |

### `Load_Grid_Transfer`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Load_Grid_Transfer/High_Battery_Disconnect` | `560` | ✅ worth surfacing | LGT disconnect battery V |
| `New_Remote/Load_Grid_Transfer/Load_Connect_Delay` | `5` | ✅ worth surfacing | connect delay |
| `New_Remote/Load_Grid_Transfer/Load_Disconnect_Delay` | `10` | ✅ worth surfacing | disconnect delay |
| `New_Remote/Load_Grid_Transfer/Load_Threshold_KW` | `1` | ✅ worth surfacing | Load-transfer threshold |
| `New_Remote/Load_Grid_Transfer/Low_Battery_Connect` | `484` | ✅ worth surfacing | LGT connect battery V |

### `Load_Grid_Transfer@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Load_Grid_Transfer@Mode` | `Disabled` | ✅ worth surfacing | Load-to-grid transfer enabled |

### `Low_SOC_Error_Percentage`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Low_SOC_Error_Percentage` | `50` | ✅ worth surfacing | Battery SOC error threshold — useful for alerts |

### `Low_SOC_Warning_Percentage`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Low_SOC_Warning_Percentage` | `60` | ✅ worth surfacing | Battery SOC warning threshold — useful for alerts |

### `Multi_Phase_Coordination`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Multi_Phase_Coordination` | (empty) | — | container / internal |

### `Multi_Phase_Coordination@Mode`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Multi_Phase_Coordination@Mode` | `Disabled` | ✅ worth surfacing | Multi-phase stacking coord |

### `Network_Options`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `New_Remote/Network_Options/SunSpec` | `Disabled` | ✅ worth surfacing | SunSpec Modbus TCP server enabled |
| `New_Remote/Network_Options/SunSpec_Port` | `502` | ✅ worth surfacing | SunSpec Modbus TCP port (502) |
| `New_Remote/Network_Options/Time_Zone` | `64736` | ✅ worth surfacing | MATE3 configured TZ offset (raw) |

### `System`

| XML path | Value | Candidate | Why |
|---|---|---|---|
| `System` | (empty) | — | container / internal |

### `Grid_Use` + `Grid_Use_P2` + `Grid_Use_P3` — defer

**19 leaves.** Weekday/weekend drop/use hour schedules for three profiles. Grid_Use/_P2/_P3 weekday/weekend drop-hour schedules — mostly zeros unless user configures time-of-use.

---

## Deliberately skipped (don't surface in HA)

| XML path | Rationale |
|---|---|
| `Installer_Notes` |  |
| `New_Remote/Button_Beep` | MATE3 UI pref |
| `New_Remote/Display/Backlight/Blue` | MATE3 display/UI prefs — not relevant in HA |
| `New_Remote/Display/Backlight/Brightness` | MATE3 display/UI prefs — not relevant in HA |
| `New_Remote/Display/Backlight/Contrast` | MATE3 display/UI prefs — not relevant in HA |
| `New_Remote/Display/Backlight/Green` | MATE3 display/UI prefs — not relevant in HA |
| `New_Remote/Display/Backlight/Mode` | MATE3 display/UI prefs — not relevant in HA |
| `New_Remote/Display/Backlight/Red` | MATE3 display/UI prefs — not relevant in HA |
| `New_Remote/Display/Backlight/Timeout` | MATE3 display/UI prefs — not relevant in HA |
| `New_Remote/Display/Contrast` | MATE3 display/UI prefs — not relevant in HA |
| `New_Remote/Network/DNS_1` | DNS config — minor diagnostic value |
| `New_Remote/Network/DNS_2` | DNS config — minor diagnostic value |
| `New_Remote/Network/FTP_Port` | rarely used service port |
| `New_Remote/Network/Telnet_Port` | rarely used service port |
| `New_Remote/Network_Options/Internet_Time` | MATE3 NTP enable toggle |
| `New_Remote/Network_Options/OPTICS_Auto_Reboot_Interval` | Outback cloud setting |
| `New_Remote/Network_Options/OPTICSre` | Outback cloud opt-in |
| `New_Remote/Serial_Baud` | MATE3 serial port baud — not relevant in HA |
| `New_Remote/Wheel_Click` | MATE3 UI pref |
| `Time_Stamp` |  |
| `Time_Stamp` | changes every fetch — noise |
| `Installer_Notes` | free-form, rarely populated |

---

## Per-port coverage

Every useful field on GS inverters and FM charge controllers already lands as a sensor (see `_INVERTER_CONFIG_SENSORS` and `_CC_CONFIG_SENSORS` in `custom_components/outback_mate3/sensor.py`). The remaining un-surfaced per-port leaves belong to optional sub-blocks that are currently disabled in this system (Mini_Grid, Grid_Zero, AC_Coupled_Mode). When a user enables one of those features, the parser populates the associated keys on the next poll — no code changes needed for those to appear.

