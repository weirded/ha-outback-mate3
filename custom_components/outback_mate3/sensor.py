"""Support for Outback MATE3 sensors."""
from __future__ import annotations

import logging
from typing import List

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
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


def create_device_entities(mate3: OutbackMate3, mac_address: str, device_type: int, device_id: int) -> List[SensorEntity]:
    """Create entities for a newly discovered device."""
    entities = []
    
    # Create combined sensors if this is the first device for this MAC
    if f"combined_{mac_address}" not in mate3.discovered_devices:
        _LOGGER.debug("Creating combined sensors for MAC %s", mac_address)
        entities.extend([
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "total_grid_power",
                "Total Grid Power",
                SensorDeviceClass.POWER,
                UnitOfPower.WATT,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "total_grid_current",
                "Total Grid Current",
                SensorDeviceClass.CURRENT,
                UnitOfElectricCurrent.AMPERE,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "total_charger_power",
                "Total Charger Power",
                SensorDeviceClass.POWER,
                UnitOfPower.WATT,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "total_charger_current",
                "Total Charger Current",
                SensorDeviceClass.CURRENT,
                UnitOfElectricCurrent.AMPERE,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "total_inverter_power",
                "Total Inverter Power",
                SensorDeviceClass.POWER,
                UnitOfPower.WATT,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "total_inverter_current",
                "Total Inverter Current",
                SensorDeviceClass.CURRENT,
                UnitOfElectricCurrent.AMPERE,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "total_cc_output_current",
                "Total Charge Controller Output Current",
                SensorDeviceClass.CURRENT,
                UnitOfElectricCurrent.AMPERE,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "total_cc_output_power",
                "Total Charge Controller Output Power",
                SensorDeviceClass.POWER,
                UnitOfPower.WATT,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "avg_ac_input_voltage",
                "Average AC Input Voltage",
                SensorDeviceClass.VOLTAGE,
                UnitOfElectricPotential.VOLT,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "avg_ac_output_voltage",
                "Average AC Output Voltage",
                SensorDeviceClass.VOLTAGE,
                UnitOfElectricPotential.VOLT,
            ),
            OutbackCombinedSensor(
                mate3,
                mac_address,
                "avg_battery_voltage",
                "Average Battery Voltage",
                SensorDeviceClass.VOLTAGE,
                UnitOfElectricPotential.VOLT,
            ),
        ])
        mate3.discovered_devices.add(f"combined_{mac_address}")

    if device_type == 6:  # Inverter
        _LOGGER.debug("Creating sensors for inverter %d from MAC %s", device_id, mac_address)
        entities.extend([
            OutbackInverterSensor(mate3, mac_address, device_id, "current", "Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "charger_current", "Charger Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "grid_current", "Grid Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, mac_address, device_id, "ac_input_voltage", "AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "ac_output_voltage", "AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, mac_address, device_id, "inverter_power", "Inverter Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "charger_power", "Charger Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "grid_power", "Grid Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, mac_address, device_id, "inverter_mode", "Inverter Mode",
                                SensorDeviceClass.ENUM, None),
            OutbackInverterSensor(mate3, mac_address, device_id, "ac_mode", "AC Mode",
                                SensorDeviceClass.ENUM, None),
            OutbackInverterSensor(mate3, mac_address, device_id, "grid_mode", "Grid Mode",
                                SensorDeviceClass.ENUM, None),
            OutbackInverterSensor(mate3, mac_address, device_id, "battery_voltage", "Battery Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
        ])
    elif device_type == 3:  # Charge Controller
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

    _LOGGER.debug("Created %d entities for device type %d, id %d from MAC %s", 
                 len(entities), device_type, device_id, mac_address)
    return entities


class OutbackBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Outback MATE3 sensors."""

    def __init__(
            self,
            mate3: OutbackMate3,
            mac_address: str,
            device_id: int,
            sensor_type: str,
            name: str,
            device_class: SensorDeviceClass | None,
            unit: str | None,
        ) -> None:
        """Initialize the sensor."""
        super().__init__(mate3)
        self._mate3 = mate3
        self._mac_address = mac_address
        self._device_id = device_id
        self._sensor_type = sensor_type

        # Create entity_id friendly MAC (replace dots with underscores)
        mac_id = mac_address.replace('.', '_')
        device_name = f"Outback {self._get_device_type()} {device_id}"
        
        # Set entity name and ID
        self._attr_has_entity_name = True
        self._attr_name = name
        self.entity_id = f"sensor.mate3_{mac_id}_{self._get_device_type().lower()}_{device_id}_{sensor_type}"

        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        if device_class not in [SensorDeviceClass.ENUM]:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{DOMAIN}_{mac_address}_{self._get_device_type().lower()}_{device_id}_{sensor_type}"
        
        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac_address}_{self._get_device_type().lower()}_{device_id}")},
            name=device_name,
            manufacturer="Outback Power",
            model=self._get_device_type(),
        )
        
        _LOGGER.debug("Initialized sensor %s for device %d from MAC %s", 
                     sensor_type, device_id, mac_address)

    def _get_device_type(self) -> str:
        """Get the device type string."""
        raise NotImplementedError


class OutbackCombinedSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Outback combined metrics sensor."""

    def __init__(
        self,
        mate3: OutbackMate3,
        mac_address: str,
        sensor_type: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
    ) -> None:
        """Initialize the combined sensor."""
        super().__init__(mate3)
        self._mate3 = mate3
        self._mac_address = mac_address
        self._sensor_type = sensor_type
        
        # Create entity_id friendly MAC (replace dots with underscores)
        mac_id = mac_address.replace('.', '_')
        device_name = f"Outback System {mac_address}"
        
        # Set entity name and ID
        self._attr_has_entity_name = True
        self._attr_name = name
        self.entity_id = f"sensor.mate3_{mac_id}_system_{sensor_type}"

        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{DOMAIN}_{mac_address}_system_{sensor_type}"
        
        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"system_{mac_address}")},
            name=device_name,
            manufacturer="Outback Power",
            model="Combined System Metrics",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._mac_address in self._mate3.combined_metrics:
            return self._mate3.combined_metrics[self._mac_address].get(self._sensor_type)
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self._mac_address in self._mate3.combined_metrics
            and self._sensor_type in self._mate3.combined_metrics[self._mac_address]
        )


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
