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
            OutbackInverterSensor(mate3, mac_address, device_id, "current", "Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "charger_current", "Charger Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_buy_current", "L1 Buy Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_sell_current", "L1 Sell Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_buy_current", "L2 Buy Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_sell_current", "L2 Sell Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_ac_input_voltage", "L1 AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_ac_output_voltage", "L1 AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_ac_input_voltage", "L2 AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_ac_output_voltage", "L2 AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_grid_power", "L1 Grid Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_grid_power", "L2 Grid Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_inverter_power", "L1 Inverter Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_inverter_power", "L2 Inverter Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l1_charger_power", "L1 Charger Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "l2_charger_power", "L2 Charger Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "battery_voltage", "Battery Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
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
