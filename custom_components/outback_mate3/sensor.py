"""Support for Outback MATE3 sensors."""
from __future__ import annotations

import logging
from typing import List

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, OutbackMate3

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Outback MATE3 sensors."""
    mate3: OutbackMate3 = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Setting up sensors for Outback MATE3")
    
    # Store the callback for adding entities later when devices are discovered
    mate3.set_add_entities_callback(async_add_entities)


def create_device_entities(mate3: OutbackMate3, mac_address: str) -> List[SensorEntity]:
    """Create entities for all devices."""
    entities = []

    # Create system sensors first
    _LOGGER.debug("Creating system sensors for MAC %s", mac_address)
    
    # Add power sensors for energy monitoring (as system sensors)
    power_sensors = [
        ("From Grid", "from_grid"),  # Positive for consumption, negative for production
        ("Solar Production", "solar_production"),  # Always positive (production)
        ("From Battery", "from_battery"),  # Positive for discharge, negative for charge
        ("To Loads", "to_loads"),  # Sum of From Grid and From Battery
    ]
    
    for name, key in power_sensors:
        entities.append(
            OutbackSystemSensor(
                mate3=mate3,
                mac_address=mac_address,
                device_id=0,
                sensor_type=key,
                name=name,
                device_class=SensorDeviceClass.POWER,
                unit=UnitOfPower.WATT,
            )
        )

    # Add battery voltage sensor
    entities.append(
        OutbackSystemSensor(
            mate3=mate3,
            mac_address=mac_address,
            device_id=0,
            sensor_type="battery_voltage",
            name="Battery Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            unit=UnitOfElectricPotential.VOLT,
        )
    )

    # Add energy sensor for solar production
    entities.append(
        OutbackSystemSensor(
            mate3=mate3,
            mac_address=mac_address,
            device_id=0,
            sensor_type="solar_production_energy",
            name="Solar Production Energy",
            device_class=SensorDeviceClass.ENERGY,
            unit=UnitOfEnergy.KILO_WATT_HOUR,
        )
    )

    mate3.discovered_devices.add(f"combined_{mac_address}")

    # Add inverter sensors
    for device_id, inverter in mate3.inverters[mac_address].items():
        _LOGGER.debug("Creating sensors for inverter %d from MAC %s", device_id, mac_address)
        entities.extend([
            # Current sensors
            # L1 current sensors
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_inverter_current", "L1 Inverter Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_charger_current", "L1 Charger Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_buy_current", "L1 Buy Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_sell_current", "L1 Sell Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            # L2 current sensors
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_inverter_current", "L2 Inverter Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_charger_current", "L2 Charger Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_buy_current", "L2 Buy Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_sell_current", "L2 Sell Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            # Combined current sensors (L1 + L2)
            OutbackInverterSensor(mate3, mac_address, device_id, "inverter_current", "Total Inverter Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "charger_current", "Total Charger Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            
            # Voltage sensors
            # L1 voltage sensors
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_ac_input_voltage", "L1 AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_ac_output_voltage", "L1 AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            # L2 voltage sensors
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_ac_input_voltage", "L2 AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_ac_output_voltage", "L2 AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            # Combined voltage sensors (L1 + L2)
            OutbackInverterSensor(mate3, mac_address, device_id, "total_ac_input_voltage", "Total AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "total_ac_output_voltage", "Total AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            
            # Power sensors
            # L1 power sensors
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_grid_power", "L1 Grid Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_inverter_power", "L1 Inverter Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_charger_power", "L1 Charger Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            # L2 power sensors
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_grid_power", "L2 Grid Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_inverter_power", "L2 Inverter Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_charger_power", "L2 Charger Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            # Combined power sensors (L1 + L2)
            OutbackInverterSensor(mate3, mac_address, device_id, "grid_power", "Total Grid Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "inverter_power", "Total Inverter Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "charger_power", "Total Charger Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "battery_voltage", "Battery Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "inverter_mode", "Inverter Mode",
                                SensorDeviceClass.ENUM, None),
            OutbackInverterSensor(mate3, mac_address, device_id, "ac_mode", "AC Mode",
                                SensorDeviceClass.ENUM, None),
            OutbackInverterSensor(mate3, mac_address, device_id, "grid_mode", "Grid Mode",
                                SensorDeviceClass.ENUM, None),
        ])

    # Add charge controller sensors
    for device_id, charge_controller in mate3.charge_controllers[mac_address].items():
        _LOGGER.debug("Creating sensors for charge controller %d from MAC %s", device_id, mac_address)
        entities.extend([
            OutbackChargeControllerSensor(mate3, mac_address, device_id, "pv_current", "PV Current",
                                        SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackChargeControllerSensor(mate3, mac_address, device_id, "pv_voltage", "PV Voltage",
                                        SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackChargeControllerSensor(mate3, mac_address, device_id, "pv_power", "PV Power",
                                        SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackChargeControllerSensor(mate3, mac_address, device_id, "output_current", "Output Current",
                                        SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackChargeControllerSensor(mate3, mac_address, device_id, "battery_voltage", "Battery Voltage",
                                        SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackChargeControllerSensor(mate3, mac_address, device_id, "charge_mode", "Charge Mode",
                                        SensorDeviceClass.ENUM, None),
            OutbackChargeControllerSensor(mate3, mac_address, device_id, "output_power", "Output Power",
                                        SensorDeviceClass.POWER, UnitOfPower.WATT),
        ])

    _LOGGER.debug("Created %d entities for MAC %s", len(entities), mac_address)
    return entities


def create_config_entities(mate3: "OutbackMate3", mac_address: str) -> List[SensorEntity]:
    """Diagnostic entities derived from the HTTP CONFIG.xml poll.

    Only called after the first ``config_snapshot`` arrives for a MAC, so the
    integration never shows phantom "unavailable" config entities when the
    MATE3's HTTP endpoint is unreachable.
    """
    config = mate3.config_by_mac.get(mac_address)
    if config is None:
        return []
    entities: List[SensorEntity] = []
    entities.extend(_config_system_sensors(mate3, mac_address))
    # Iterate the config's own port-order lists — this doesn't depend on
    # whether we've seen a UDP frame for each device yet.
    for idx, _ in enumerate(config.get("inverters", []), start=1):
        entities.extend(_config_inverter_sensors(mate3, mac_address, idx))
    for idx, _ in enumerate(config.get("charge_controllers", []), start=1):
        entities.extend(_config_charge_controller_sensors(mate3, mac_address, idx))
    _LOGGER.debug("Created %d config entities for MAC %s", len(entities), mac_address)
    return entities


class OutbackBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Outback sensors."""

    def __init__(
        self,
        mate3: OutbackMate3,
        mac_address: str,
        device_id: int,
        sensor_type: str,
        name: str,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(mate3)
        self._mate3 = mate3
        self._mac_address = mac_address
        self._device_id = device_id
        self._sensor_type = sensor_type
        
        # Create entity_id friendly MAC (replace dots with underscores)
        mac_id = mac_address.replace('.', '_')
        
        # Set entity name and ID
        self._attr_has_entity_name = True
        self._attr_name = name
        
        device_type = self._get_device_type()
        if device_type == "system":
            device_name = "Outback System"
            self.entity_id = f"sensor.mate3_system_{sensor_type}"
        else:
            device_name = f"Outback {device_type.replace('_', ' ').title()} {device_id}"
            self.entity_id = f"sensor.mate3_{mac_id}_{device_type}_{device_id}_{sensor_type}"

        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        # Set unique ID based on device type
        if device_type == "system":
            self._attr_unique_id = f"{DOMAIN}_system_{sensor_type}"
        else:
            self._attr_unique_id = f"{DOMAIN}_{mac_address}_{device_type}_{device_id}_{sensor_type}"
        
        # Set up device info
        if device_type == "system":
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, "system")},
                name=device_name,
                manufacturer="Outback Power",
                model="System",
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{device_type}_{mac_address}_{device_id}")},
                name=device_name,
                manufacturer="Outback Power",
                model=device_type.replace('_', ' ').title(),
            )

    def _get_device_type(self) -> str:
        """Return the type of device."""
        raise NotImplementedError


class OutbackSystemSensor(OutbackBaseSensor):
    """Representation of an Outback system-wide sensor."""

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self._sensor_type == 'from_grid':
            # Sum up L1 and L2 grid power from all inverters
            total_power = 0
            for inv in self._mate3.inverters[self._mac_address].values():
                total_power += inv.get('l1_grid_power', 0) + inv.get('l2_grid_power', 0)
            return round(total_power)
        elif self._sensor_type == 'solar_production':
            # Sum up all charge controller output power
            total_power = 0
            for cc in self._mate3.charge_controllers[self._mac_address].values():
                total_power += cc.get('output_power', 0)
            return round(total_power)
        elif self._sensor_type == 'from_battery':
            # Sum up L1 and L2 inverter/charger power from all inverters
            total_power = 0
            for inv in self._mate3.inverters[self._mac_address].values():
                # Add up both L1 and L2 powers
                inverter_power = inv.get('l1_inverter_power', 0) + inv.get('l2_inverter_power', 0)
                charger_power = inv.get('l1_charger_power', 0) + inv.get('l2_charger_power', 0)
                total_power += inverter_power - charger_power
            return round(total_power)
        elif self._sensor_type == 'to_loads':
            # Sum up From Grid and From Battery
            grid_power = 0
            battery_power = 0
            for inv in self._mate3.inverters[self._mac_address].values():
                # Add up both L1 and L2 grid powers
                grid_power += inv.get('l1_grid_power', 0) + inv.get('l2_grid_power', 0)
                # Add up both L1 and L2 inverter/charger powers
                inverter_power = inv.get('l1_inverter_power', 0) + inv.get('l2_inverter_power', 0)
                charger_power = inv.get('l1_charger_power', 0) + inv.get('l2_charger_power', 0)
                battery_power += inverter_power - charger_power
            return round(grid_power + battery_power)
        elif self._sensor_type == 'solar_production_energy':
            # Sum up daily kWh from all charge controllers
            total_production = 0
            for cc in self._mate3.charge_controllers[self._mac_address].values():
                if 'kwh_today' in cc:
                    total_production += cc['kwh_today']
            return total_production
        elif self._sensor_type == 'battery_voltage':
            # Calculate average battery voltage from charge controllers only
            voltages = []
            for cc in self._mate3.charge_controllers[self._mac_address].values():
                if 'battery_voltage' in cc:
                    voltages.append(cc['battery_voltage'])
            if voltages:
                return sum(voltages) / len(voltages)
        return None

    def _get_device_type(self) -> str:
        """Return the type of device."""
        return "system"


class OutbackInverterSensor(OutbackBaseSensor):
    """Representation of an Outback inverter sensor."""

    def _get_device_type(self) -> str:
        """Get the device type string."""
        return "inverter"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if (self._mac_address in self._mate3.inverters and 
            self._device_id in self._mate3.inverters[self._mac_address]):
            value = self._mate3.inverters[self._mac_address][self._device_id].get(self._sensor_type)
            _LOGGER.debug("Inverter sensor %s for device %d from MAC %s value: %s", 
                         self._sensor_type, self._device_id, self._mac_address, value)
            return value
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (self._mac_address in self._mate3.inverters and 
                self._device_id in self._mate3.inverters[self._mac_address] and
                self._sensor_type in self._mate3.inverters[self._mac_address][self._device_id])


class OutbackChargeControllerSensor(OutbackBaseSensor):
    """Representation of an Outback charge controller sensor."""

    def _get_device_type(self) -> str:
        """Get the device type string."""
        return "charge_controller"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if (self._mac_address in self._mate3.charge_controllers and 
            self._device_id in self._mate3.charge_controllers[self._mac_address]):
            value = self._mate3.charge_controllers[self._mac_address][self._device_id].get(self._sensor_type)
            _LOGGER.debug("Charge controller sensor %s for device %d from MAC %s value: %s", 
                         self._sensor_type, self._device_id, self._mac_address, value)
            return value
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (self._mac_address in self._mate3.charge_controllers and
                self._device_id in self._mate3.charge_controllers[self._mac_address] and
                self._sensor_type in self._mate3.charge_controllers[self._mac_address][self._device_id])


# -----------------------------------------------------------------------------
# Diagnostic sensors derived from the MATE3 HTTP config poll
# -----------------------------------------------------------------------------


class OutbackConfigDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """A string-valued diagnostic sensor read from OutbackMate3.config_by_mac.

    Used for firmware versions, data stream target, SD card log mode — values
    that come from the periodic HTTP CONFIG.xml poll, not the UDP stream.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        mate3: "OutbackMate3",
        mac_address: str,
        device_kind: str,          # "system" | "inverter" | "charge_controller"
        device_id: int,            # 0 for system; 1-based for inverter/cc
        key: str,                  # short identifier for entity_id / unique_id
        name: str,                 # user-visible short name
        config_getter,             # callable(config_dict: dict) -> str | None
        *,
        is_firmware: bool = False, # if True, also populate device_info.sw_version
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        super().__init__(mate3)
        self._mate3 = mate3
        self._mac_address = mac_address
        self._device_kind = device_kind
        self._device_id = device_id
        self._key = key
        self._config_getter = config_getter
        self._is_firmware = is_firmware

        mac_id = mac_address.replace(".", "_")
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

        if device_kind == "system":
            self.entity_id = f"sensor.mate3_system_{key}"
            self._attr_unique_id = f"{DOMAIN}_system_{key}"
            device_info = DeviceInfo(
                identifiers={(DOMAIN, "system")},
                name="Outback System",
                manufacturer="Outback Power",
                model="System",
            )
        else:
            self.entity_id = (
                f"sensor.mate3_{mac_id}_{device_kind}_{device_id}_{key}"
            )
            self._attr_unique_id = (
                f"{DOMAIN}_{mac_address}_{device_kind}_{device_id}_{key}"
            )
            device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{device_kind}_{mac_address}_{device_id}")},
                name=f"Outback {device_kind.replace('_', ' ').title()} {device_id}",
                manufacturer="Outback Power",
                model=device_kind.replace("_", " ").title(),
            )

        # Surface firmware string on the device page too.
        if is_firmware:
            fw = self._read_value()
            if fw is not None:
                device_info["sw_version"] = str(fw)
        self._attr_device_info = device_info

    def _read_value(self):
        config = self._mate3.config_by_mac.get(self._mac_address)
        if config is None:
            return None
        try:
            return self._config_getter(config)
        except (IndexError, KeyError, TypeError):
            return None

    @property
    def native_value(self):
        v = self._read_value()
        if v is None:
            return None
        # Numeric sensors (unit set) should keep their native numeric type so
        # HA formats them correctly and units display. Anything else is
        # rendered as a string.
        if self._attr_native_unit_of_measurement is not None and isinstance(v, (int, float)):
            return v
        return str(v)

    @property
    def available(self) -> bool:
        return self._read_value() is not None


def _sys(key):
    """Getter for a top-level system-block value."""
    return lambda c, k=key: c.get("system", {}).get(k)


def _m3(key):
    """Getter for a top-level mate3-block value."""
    return lambda c, k=key: c.get("mate3", {}).get(k)


def _inv(key):
    """Per-inverter getter; closes over a 1-based index."""
    def f(c, i, k=key):
        inverters = c.get("inverters") or []
        return inverters[i - 1].get(k) if len(inverters) >= i else None
    return f


def _cc(key):
    """Per-charge-controller getter; closes over a 1-based index."""
    def f(c, i, k=key):
        ccs = c.get("charge_controllers") or []
        return ccs[i - 1].get(k) if len(ccs) >= i else None
    return f


# System-level config sensors. Tuples: (key, name, getter, unit, device_class, is_firmware)
_SYSTEM_CONFIG_SENSORS = [
    ("mate3_firmware", "MATE3 Firmware", _m3("firmware"), None, None, True),
    ("data_stream_target", "Data Stream Target",
     lambda c: (
         f"{c['mate3']['data_stream_ip']}:{c['mate3']['data_stream_port']}"
         if c.get("mate3", {}).get("data_stream_ip")
         and c.get("mate3", {}).get("data_stream_port")
         else None
     ), None, None, False),
    ("data_stream_mode", "Data Stream Mode", _m3("data_stream_mode"), None, None, False),
    ("sd_card_log_mode", "SD Card Log Mode", _m3("sd_card_log_mode"), None, None, False),
    ("mate3_ip_address", "MATE3 IP Address", _m3("ip_address"), None, None, False),
    ("mate3_dhcp", "MATE3 DHCP", _m3("dhcp"), None, None, False),
    ("mate3_gateway", "MATE3 Gateway", _m3("gateway"), None, None, False),
    ("system_type", "System Type", _sys("system_type"), None, None, False),
    ("nominal_voltage", "Nominal Voltage", _sys("nominal_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("battery_ah_capacity", "Battery Ah Capacity", _sys("battery_ah_capacity"),
     "Ah", None, False),
    ("pv_size_watts", "PV Size", _sys("pv_size_watts"),
     UnitOfPower.WATT, SensorDeviceClass.POWER, False),
    ("generator_kw", "Generator Rating", _sys("generator_kw"), "kW", None, False),
    ("max_inverter_output_kw", "Max Inverter Output", _sys("max_inverter_output_kw"), "kW", None, False),
    ("max_charger_output_kw", "Max Charger Output", _sys("max_charger_output_kw"), "kW", None, False),

    # --- Phase 15: system-wide setpoints & coordination (via MATE3 block) ---

    # Low SOC thresholds
    ("low_soc_warning_percentage", "Low SOC Warning", _m3("low_soc_warning_percentage"), "%", None, False),
    ("low_soc_error_percentage", "Low SOC Error", _m3("low_soc_error_percentage"), "%", None, False),

    # Coordination
    ("cc_float_coordination_mode", "CC Float Coordination",
     _m3("cc_float_coordination_mode"), None, None, False),
    ("multi_phase_coordination_mode", "Multi-Phase Coordination",
     _m3("multi_phase_coordination_mode"), None, None, False),

    # AC coupling
    ("ac_coupled_control_mode", "AC Coupled Control",
     _m3("ac_coupled_control_mode"), None, None, False),
    ("ac_coupled_control_aux_output", "AC Coupled AUX Output",
     _m3("ac_coupled_control_aux_output"), None, None, False),

    # Global CC output cap
    ("global_cc_control_mode", "Global CC Output Control",
     _m3("global_cc_control_mode"), None, None, False),
    ("global_cc_max_charge_rate", "Global CC Max Charge Rate",
     _m3("global_cc_max_charge_rate"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),

    # SunSpec / Modbus / Time zone
    ("sunspec_mode", "SunSpec Server", _m3("sunspec_mode"), None, None, False),
    ("sunspec_port", "SunSpec Port", _m3("sunspec_port"), None, None, False),
    ("time_zone_raw", "MATE3 Time Zone (raw)", _m3("time_zone_raw"), None, None, False),

    # FNDC
    ("fndc_charge_term_mode", "FNDC Charge Term Control",
     _m3("fndc_charge_term_mode"), None, None, False),
    ("fndc_sell_mode", "FNDC Sell Control", _m3("fndc_sell_mode"), None, None, False),

    # Grid Mode Schedules 1/2/3
    ("grid_mode_schedule_1_mode", "Grid Mode Schedule 1",
     _m3("grid_mode_schedule_1_mode"), None, None, False),
    ("grid_mode_schedule_1_enable_hour", "Grid Mode Schedule 1 Hour",
     _m3("grid_mode_schedule_1_enable_hour"), None, None, False),
    ("grid_mode_schedule_1_enable_min", "Grid Mode Schedule 1 Minute",
     _m3("grid_mode_schedule_1_enable_min"), None, None, False),
    ("grid_mode_schedule_2_mode", "Grid Mode Schedule 2",
     _m3("grid_mode_schedule_2_mode"), None, None, False),
    ("grid_mode_schedule_2_enable_hour", "Grid Mode Schedule 2 Hour",
     _m3("grid_mode_schedule_2_enable_hour"), None, None, False),
    ("grid_mode_schedule_2_enable_min", "Grid Mode Schedule 2 Minute",
     _m3("grid_mode_schedule_2_enable_min"), None, None, False),
    ("grid_mode_schedule_3_mode", "Grid Mode Schedule 3",
     _m3("grid_mode_schedule_3_mode"), None, None, False),
    ("grid_mode_schedule_3_enable_hour", "Grid Mode Schedule 3 Hour",
     _m3("grid_mode_schedule_3_enable_hour"), None, None, False),
    ("grid_mode_schedule_3_enable_min", "Grid Mode Schedule 3 Minute",
     _m3("grid_mode_schedule_3_enable_min"), None, None, False),

    # High Battery Transfer
    ("hvt_mode", "HVT Mode", _m3("hvt_mode"), None, None, False),
    ("hvt_disconnect_voltage", "HVT Disconnect Voltage", _m3("hvt_disconnect_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("hvt_disconnect_delay", "HVT Disconnect Delay", _m3("hvt_disconnect_delay"), None, None, False),
    ("hvt_reconnect_voltage", "HVT Reconnect Voltage", _m3("hvt_reconnect_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("hvt_reconnect_delay", "HVT Reconnect Delay", _m3("hvt_reconnect_delay"), None, None, False),
    ("hvt_soc_connect_pct", "HVT Reconnect SOC", _m3("hvt_soc_connect_pct"), "%", None, False),
    ("hvt_soc_disconnect_pct", "HVT Disconnect SOC", _m3("hvt_soc_disconnect_pct"), "%", None, False),

    # Load Grid Transfer (load shedding)
    ("lgt_mode", "Load-Grid Transfer", _m3("lgt_mode"), None, None, False),
    ("lgt_load_threshold_kw", "Load-Grid Threshold", _m3("lgt_load_threshold_kw"), "kW", None, False),
    ("lgt_connect_delay", "Load-Grid Connect Delay", _m3("lgt_connect_delay"), None, None, False),
    ("lgt_disconnect_delay", "Load-Grid Disconnect Delay", _m3("lgt_disconnect_delay"), None, None, False),
    ("lgt_low_battery_connect_voltage", "Load-Grid Low Battery Connect",
     _m3("lgt_low_battery_connect_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("lgt_high_battery_disconnect_voltage", "Load-Grid High Battery Disconnect",
     _m3("lgt_high_battery_disconnect_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),

    # --- Phase 15.10: Advanced Generator Start (AGS) ---
    ("ags_mode", "AGS", _m3("ags_mode"), None, None, False),
    ("ags_control", "AGS Control", _m3("ags_control"), None, None, False),
    ("ags_generator_type", "AGS Generator Type", _m3("ags_generator_type"), None, None, False),
    ("ags_port", "AGS Port", _m3("ags_port"), None, None, False),
    ("ags_cooldown_time", "AGS Cooldown Time", _m3("ags_cooldown_time"), None, None, False),
    ("ags_warmup_time", "AGS Warmup Time", _m3("ags_warmup_time"), None, None, False),
    ("ags_fault_time", "AGS Fault Time", _m3("ags_fault_time"), None, None, False),
    ("ags_ac_input_reconnect_delay", "AGS AC Input Reconnect Delay",
     _m3("ags_ac_input_reconnect_delay"), None, None, False),
    ("ags_dc_generator_absorb_time", "AGS DC Generator Absorb Time",
     _m3("ags_dc_generator_absorb_time"), None, None, False),
    ("ags_dc_generator_absorb_voltage", "AGS DC Generator Absorb Voltage",
     _m3("ags_dc_generator_absorb_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("ags_fndc_full_charge_mode", "AGS FNDC Full Charge",
     _m3("ags_fndc_full_charge_mode"), None, None, False),
    ("ags_fndc_full_charge_interval", "AGS FNDC Full Charge Interval",
     _m3("ags_fndc_full_charge_interval"), "d", None, False),
    # Generator Exercise
    ("ags_generator_exercise_mode", "AGS Generator Exercise",
     _m3("ags_generator_exercise_mode"), None, None, False),
    ("ags_generator_exercise_day", "AGS Generator Exercise Day",
     _m3("ags_generator_exercise_day"), None, None, False),
    ("ags_generator_exercise_interval", "AGS Generator Exercise Interval",
     _m3("ags_generator_exercise_interval"), None, None, False),
    ("ags_generator_exercise_period", "AGS Generator Exercise Period",
     _m3("ags_generator_exercise_period"), None, None, False),
    ("ags_generator_exercise_sell_during", "AGS Sell During Exercise",
     _m3("ags_generator_exercise_sell_during"), None, None, False),
    ("ags_generator_exercise_start_hour", "AGS Generator Exercise Start Hour",
     _m3("ags_generator_exercise_start_hour"), None, None, False),
    ("ags_generator_exercise_start_min", "AGS Generator Exercise Start Min",
     _m3("ags_generator_exercise_start_min"), None, None, False),
    # Load Start
    ("ags_load_start_mode", "AGS Load Start", _m3("ags_load_start_mode"), None, None, False),
    ("ags_load_start_start_delay", "AGS Load Start Start Delay",
     _m3("ags_load_start_start_delay"), None, None, False),
    ("ags_load_start_start_load_kw", "AGS Load Start Start Load",
     _m3("ags_load_start_start_load_kw"), "kW", None, False),
    ("ags_load_start_stop_delay", "AGS Load Start Stop Delay",
     _m3("ags_load_start_stop_delay"), None, None, False),
    ("ags_load_start_stop_load_kw", "AGS Load Start Stop Load",
     _m3("ags_load_start_stop_load_kw"), "kW", None, False),
    # Must Run
    ("ags_must_run_mode", "AGS Must Run", _m3("ags_must_run_mode"), None, None, False),
    ("ags_must_run_weekday_start_hour", "AGS Must Run Weekday Start Hour",
     _m3("ags_must_run_weekday_start_hour"), None, None, False),
    ("ags_must_run_weekday_start_min", "AGS Must Run Weekday Start Min",
     _m3("ags_must_run_weekday_start_min"), None, None, False),
    ("ags_must_run_weekday_stop_hour", "AGS Must Run Weekday Stop Hour",
     _m3("ags_must_run_weekday_stop_hour"), None, None, False),
    ("ags_must_run_weekday_stop_min", "AGS Must Run Weekday Stop Min",
     _m3("ags_must_run_weekday_stop_min"), None, None, False),
    ("ags_must_run_weekend_start_hour", "AGS Must Run Weekend Start Hour",
     _m3("ags_must_run_weekend_start_hour"), None, None, False),
    ("ags_must_run_weekend_start_min", "AGS Must Run Weekend Start Min",
     _m3("ags_must_run_weekend_start_min"), None, None, False),
    ("ags_must_run_weekend_stop_hour", "AGS Must Run Weekend Stop Hour",
     _m3("ags_must_run_weekend_stop_hour"), None, None, False),
    ("ags_must_run_weekend_stop_min", "AGS Must Run Weekend Stop Min",
     _m3("ags_must_run_weekend_stop_min"), None, None, False),
    # Quiet Time
    ("ags_quiet_time_mode", "AGS Quiet Time", _m3("ags_quiet_time_mode"), None, None, False),
    ("ags_quiet_time_weekday_start_hour", "AGS Quiet Time Weekday Start Hour",
     _m3("ags_quiet_time_weekday_start_hour"), None, None, False),
    ("ags_quiet_time_weekday_start_min", "AGS Quiet Time Weekday Start Min",
     _m3("ags_quiet_time_weekday_start_min"), None, None, False),
    ("ags_quiet_time_weekday_stop_hour", "AGS Quiet Time Weekday Stop Hour",
     _m3("ags_quiet_time_weekday_stop_hour"), None, None, False),
    ("ags_quiet_time_weekday_stop_min", "AGS Quiet Time Weekday Stop Min",
     _m3("ags_quiet_time_weekday_stop_min"), None, None, False),
    ("ags_quiet_time_weekend_start_hour", "AGS Quiet Time Weekend Start Hour",
     _m3("ags_quiet_time_weekend_start_hour"), None, None, False),
    ("ags_quiet_time_weekend_start_min", "AGS Quiet Time Weekend Start Min",
     _m3("ags_quiet_time_weekend_start_min"), None, None, False),
    ("ags_quiet_time_weekend_stop_hour", "AGS Quiet Time Weekend Stop Hour",
     _m3("ags_quiet_time_weekend_stop_hour"), None, None, False),
    ("ags_quiet_time_weekend_stop_min", "AGS Quiet Time Weekend Stop Min",
     _m3("ags_quiet_time_weekend_stop_min"), None, None, False),
    # SOC Start
    ("ags_soc_start_mode", "AGS SOC Start", _m3("ags_soc_start_mode"), None, None, False),
    ("ags_soc_start_start_percentage", "AGS SOC Start %",
     _m3("ags_soc_start_start_percentage"), "%", None, False),
    ("ags_soc_start_stop_percentage", "AGS SOC Stop %",
     _m3("ags_soc_start_stop_percentage"), "%", None, False),
    # Voltage starts
    ("ags_two_min_voltage_start_mode", "AGS 2-Min Voltage Start",
     _m3("ags_two_min_voltage_start_mode"), None, None, False),
    ("ags_two_min_voltage_start_voltage", "AGS 2-Min Voltage",
     _m3("ags_two_min_voltage_start_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("ags_two_hour_voltage_start_mode", "AGS 2-Hour Voltage Start",
     _m3("ags_two_hour_voltage_start_mode"), None, None, False),
    ("ags_two_hour_voltage_start_voltage", "AGS 2-Hour Voltage",
     _m3("ags_two_hour_voltage_start_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("ags_twenty_four_hour_voltage_start_mode", "AGS 24-Hour Voltage Start",
     _m3("ags_twenty_four_hour_voltage_start_mode"), None, None, False),
    ("ags_twenty_four_hour_voltage_start_voltage", "AGS 24-Hour Voltage",
     _m3("ags_twenty_four_hour_voltage_start_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),

    # --- Phase 15.11: Grid Use time-of-use (three profiles) ---
]
# Generate the 19 Grid_Use sensors programmatically to avoid tedious repetition.
for _prefix, _label in [("grid_use", "Grid Use"), ("grid_use_p2", "Grid Use P2"), ("grid_use_p3", "Grid Use P3")]:
    _SYSTEM_CONFIG_SENSORS.append(
        (f"{_prefix}_mode", f"{_label} Mode", _m3(f"{_prefix}_mode"), None, None, False)
    )
    for _day in ("weekday", "weekend"):
        for _stage in ("drop", "use"):
            for _unit, _unit_label in [("hour", "Hour"), ("min", "Min")]:
                _key = f"{_prefix}_{_day}_{_stage}_{_unit}"
                _name = f"{_label} {_day.capitalize()} {_stage.capitalize()} {_unit_label}"
                _SYSTEM_CONFIG_SENSORS.append(
                    (_key, _name, _m3(_key), None, None, False)
                )


# Per-inverter config sensors. Getter is called with (config, index).
_INVERTER_CONFIG_SENSORS = [
    ("firmware", "Firmware", _inv("firmware"), None, None, True),
    ("configured_type", "Configured Type", _inv("type"), None, None, False),
    ("configured_inverter_mode", "Configured Inverter Mode", _inv("inverter_mode"), None, None, False),
    ("ac_output_voltage", "AC Output Voltage Setpoint", _inv("ac_output_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("low_battery_cut_out_voltage", "Low Battery Cut-Out", _inv("low_battery_cut_out_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("low_battery_cut_in_voltage", "Low Battery Cut-In", _inv("low_battery_cut_in_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("high_battery_cut_out_voltage", "High Battery Cut-Out", _inv("high_battery_cut_out_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("high_battery_cut_in_voltage", "High Battery Cut-In", _inv("high_battery_cut_in_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_mode", "Charger Mode", _inv("charger_mode"), None, None, False),
    ("charger_absorb_voltage", "Charger Absorb Voltage", _inv("charger_absorb_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_absorb_time", "Charger Absorb Time", _inv("charger_absorb_time"), "min", None, False),
    ("charger_float_voltage", "Charger Float Voltage", _inv("charger_float_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_eq_voltage", "Charger EQ Voltage", _inv("charger_eq_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_re_float_voltage", "Charger Re-Float Voltage", _inv("charger_re_float_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_re_bulk_voltage", "Charger Re-Bulk Voltage", _inv("charger_re_bulk_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("grid_tie_mode", "Grid Tie Mode", _inv("grid_tie_mode"), None, None, False),
    ("grid_tie_voltage", "Grid Tie Voltage", _inv("grid_tie_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("grid_tie_window", "Grid Tie Window", _inv("grid_tie_window"), None, None, False),
    ("ac_input_priority", "AC Input Priority", _inv("ac_input_priority"), None, None, False),
    ("ac1_input_type", "AC1 Input Type", _inv("ac1_input_type"), None, None, False),
    ("ac1_min_voltage", "AC1 Min Voltage", _inv("ac1_min_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("ac1_max_voltage", "AC1 Max Voltage", _inv("ac1_max_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("ac2_input_type", "AC2 Input Type", _inv("ac2_input_type"), None, None, False),
    ("ac2_min_voltage", "AC2 Min Voltage", _inv("ac2_min_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("ac2_max_voltage", "AC2 Max Voltage", _inv("ac2_max_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("stack_mode", "Stack Mode", _inv("stack_mode"), None, None, False),
    ("stack_master_power_save_level", "Stack Master Power-Save Level",
     _inv("stack_master_power_save_level"), None, None, False),
    ("stack_slave_power_save_level", "Stack Slave Power-Save Level",
     _inv("stack_slave_power_save_level"), None, None, False),
    # --- Search ---
    ("search_pulse_length", "Search Pulse Length", _inv("search_pulse_length"), None, None, False),
    ("search_ac_load_threshold_amps", "Search AC Load Threshold",
     _inv("search_ac_load_threshold_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    ("search_pulse_spacing", "Search Pulse Spacing", _inv("search_pulse_spacing"), None, None, False),
    # --- AC coupling ---
    ("ac_coupled_mode", "AC Coupled Mode", _inv("ac_coupled_mode"), None, None, False),
    # --- Charger extras ---
    ("charger_float_time", "Charger Float Time", _inv("charger_float_time"), "h", None, False),
    # --- Mini Grid / Grid Zero ---
    ("mini_grid_lbx_voltage", "Mini-Grid LBX Voltage", _inv("mini_grid_lbx_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("mini_grid_lbx_delay", "Mini-Grid LBX Delay", _inv("mini_grid_lbx_delay"), None, None, False),
    ("grid_zero_voltage", "Grid Zero Min Voltage", _inv("grid_zero_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("grid_zero_max_amps", "Grid Zero Max Amps", _inv("grid_zero_max_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    # --- AC1 / AC2 extras ---
    ("ac1_input_size_amps", "AC1 Input Size", _inv("ac1_input_size_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    ("ac1_transfer_delay", "AC1 Transfer Delay", _inv("ac1_transfer_delay"), None, None, False),
    ("ac1_connect_delay", "AC1 Connect Delay", _inv("ac1_connect_delay"), None, None, False),
    ("ac2_input_size_amps", "AC2 Input Size", _inv("ac2_input_size_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    ("ac2_transfer_delay", "AC2 Transfer Delay", _inv("ac2_transfer_delay"), None, None, False),
    ("ac2_connect_delay", "AC2 Connect Delay", _inv("ac2_connect_delay"), None, None, False),
    # --- AUX 12V Output ---
    ("aux_output_mode", "AUX Output Mode", _inv("aux_output_mode"), None, None, False),
    ("aux_output_operation_mode", "AUX Operation Mode", _inv("aux_output_operation_mode"), None, None, False),
    ("aux_output_on_delay", "AUX On Delay", _inv("aux_output_on_delay"), None, None, False),
    ("aux_output_off_delay", "AUX Off Delay", _inv("aux_output_off_delay"), None, None, False),
    ("aux_output_high_setpoint_voltage", "AUX High Setpoint Voltage",
     _inv("aux_output_high_setpoint_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_output_low_setpoint_voltage", "AUX Low Setpoint Voltage",
     _inv("aux_output_low_setpoint_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_output_high_setpoint_ac_amps", "AUX High Setpoint AC Amps",
     _inv("aux_output_high_setpoint_ac_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    ("aux_output_low_setpoint_ac_amps", "AUX Low Setpoint AC Amps",
     _inv("aux_output_low_setpoint_ac_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    # --- Relay ---
    ("relay_mode", "Relay Mode", _inv("relay_mode"), None, None, False),
    ("relay_operation_mode", "Relay Operation Mode", _inv("relay_operation_mode"), None, None, False),
    ("relay_on_delay", "Relay On Delay", _inv("relay_on_delay"), None, None, False),
    ("relay_off_delay", "Relay Off Delay", _inv("relay_off_delay"), None, None, False),
    ("relay_high_setpoint_voltage", "Relay High Setpoint Voltage",
     _inv("relay_high_setpoint_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("relay_low_setpoint_voltage", "Relay Low Setpoint Voltage",
     _inv("relay_low_setpoint_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("relay_high_setpoint_ac_amps", "Relay High Setpoint AC Amps",
     _inv("relay_high_setpoint_ac_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    ("relay_low_setpoint_ac_amps", "Relay Low Setpoint AC Amps",
     _inv("relay_low_setpoint_ac_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
]

# Per-charge-controller config sensors.
_CC_CONFIG_SENSORS = [
    ("firmware", "Firmware", _cc("firmware"), None, None, True),
    ("model_type", "Model", _cc("model_type"), None, None, False),
    ("gt_mode", "Grid Tie Mode", _cc("gt_mode"), None, None, False),
    ("charger_absorb_voltage", "Absorb Voltage", _cc("charger_absorb_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_absorb_time", "Absorb Time", _cc("charger_absorb_time"), "min", None, False),
    ("charger_absorb_end_amps", "Absorb End Amps", _cc("charger_absorb_end_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    ("charger_float_voltage", "Float Voltage", _cc("charger_float_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_rebulk_voltage", "Re-Bulk Voltage", _cc("charger_rebulk_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_eq_voltage", "EQ Voltage", _cc("charger_eq_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("charger_eq_time", "EQ Time", _cc("charger_eq_time"), "min", None, False),
    ("charger_output_limit", "Output Current Limit", _cc("charger_output_limit"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    ("mppt_mode", "MPPT Mode", _cc("mppt_mode"), None, None, False),
    ("mppt_sweep_mode", "MPPT Sweep Mode", _cc("mppt_sweep_mode"), None, None, False),
    ("mppt_max_sweep", "MPPT Max Sweep", _cc("mppt_max_sweep"), None, None, False),
    ("mppt_upick_percentage", "MPPT Upick %", _cc("mppt_upick_percentage"), "%", None, False),
    ("mppt_restart_mode", "MPPT Restart Mode", _cc("mppt_restart_mode"), None, None, False),
    # --- Charger extras ---
    ("charger_eq_auto_interval_days", "EQ Auto Interval", _cc("charger_eq_auto_interval_days"),
     "d", None, False),
    # --- Wakeup / Snooze ---
    ("wakeup_interval", "Wakeup Interval", _cc("wakeup_interval"), None, None, False),
    ("wakeup_voc_change", "Wakeup VOC Change", _cc("wakeup_voc_change"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("snooze_amps", "Snooze Amps", _cc("snooze_amps"),
     UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, False),
    # --- Remote Temp Sensor ---
    ("rts_mode", "RTS Mode", _cc("rts_mode"), None, None, False),
    ("rts_maximum_voltage", "RTS Max Voltage", _cc("rts_maximum_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("rts_minimum_voltage", "RTS Min Voltage", _cc("rts_minimum_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    # --- AUX output ---
    ("aux_mode", "AUX Mode", _cc("aux_mode"), None, None, False),
    ("aux_operation_mode", "AUX Operation Mode", _cc("aux_operation_mode"), None, None, False),
    ("aux_polarity", "AUX Polarity", _cc("aux_polarity"), None, None, False),
    ("aux_error_low_batt_voltage", "AUX Error Low Battery Voltage",
     _cc("aux_error_low_batt_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_low_batt_disconnect_voltage", "AUX Low-Batt Disconnect Voltage",
     _cc("aux_low_batt_disconnect_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_low_batt_disconnect_delay", "AUX Low-Batt Disconnect Delay",
     _cc("aux_low_batt_disconnect_delay"), None, None, False),
    ("aux_low_batt_reconnect_voltage", "AUX Low-Batt Reconnect Voltage",
     _cc("aux_low_batt_reconnect_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_vent_fan_voltage", "AUX Vent Fan Voltage", _cc("aux_vent_fan_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_diversion_hold_time", "AUX Diversion Hold Time",
     _cc("aux_diversion_hold_time"), None, None, False),
    ("aux_diversion_delay", "AUX Diversion Delay",
     _cc("aux_diversion_delay"), None, None, False),
    ("aux_diversion_relative_voltage", "AUX Diversion Relative Voltage",
     _cc("aux_diversion_relative_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_diversion_hysteresis_voltage", "AUX Diversion Hysteresis Voltage",
     _cc("aux_diversion_hysteresis_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_pv_trigger_voltage", "AUX PV Trigger Voltage",
     _cc("aux_pv_trigger_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_pv_trigger_hold_time", "AUX PV Trigger Hold Time",
     _cc("aux_pv_trigger_hold_time"), None, None, False),
    ("aux_nite_light_threshold_voltage", "AUX Nite Light Threshold Voltage",
     _cc("aux_nite_light_threshold_voltage"),
     UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, False),
    ("aux_nite_light_on_hyst_time", "AUX Nite Light On Hyst Time",
     _cc("aux_nite_light_on_hyst_time"), None, None, False),
    ("aux_nite_light_off_hyst_time", "AUX Nite Light Off Hyst Time",
     _cc("aux_nite_light_off_hyst_time"), None, None, False),
    ("aux_nite_light_on_hours", "AUX Nite Light On Hours",
     _cc("aux_nite_light_on_hours"), "h", None, False),
]


def _config_system_sensors(mate3: "OutbackMate3", mac: str) -> List[SensorEntity]:
    out: List[SensorEntity] = []
    for key, name, getter, unit, dev_class, is_fw in _SYSTEM_CONFIG_SENSORS:
        out.append(OutbackConfigDiagnosticSensor(
            mate3, mac, "system", 0, key, name,
            getter,
            unit=unit, device_class=dev_class, is_firmware=is_fw,
        ))
    return out


def _config_inverter_sensors(mate3: "OutbackMate3", mac: str, index: int) -> List[SensorEntity]:
    out: List[SensorEntity] = []
    for key, name, getter, unit, dev_class, is_fw in _INVERTER_CONFIG_SENSORS:
        # getter takes (config, index)
        out.append(OutbackConfigDiagnosticSensor(
            mate3, mac, "inverter", index, key, name,
            lambda c, g=getter, i=index: g(c, i),
            unit=unit, device_class=dev_class, is_firmware=is_fw,
        ))
    return out


def _config_charge_controller_sensors(mate3: "OutbackMate3", mac: str, index: int) -> List[SensorEntity]:
    out: List[SensorEntity] = []
    for key, name, getter, unit, dev_class, is_fw in _CC_CONFIG_SENSORS:
        out.append(OutbackConfigDiagnosticSensor(
            mate3, mac, "charge_controller", index, key, name,
            lambda c, g=getter, i=index: g(c, i),
            unit=unit, device_class=dev_class, is_firmware=is_fw,
        ))
    return out
