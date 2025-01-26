"""Support for Outback MATE3 sensors."""
from __future__ import annotations

import logging
from typing import List

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
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


def create_device_entities(mate3: OutbackMate3, remote_ip: str, device_type: int, device_id: int) -> List[SensorEntity]:
    """Create entities for a newly discovered device."""
    entities = []
    
    if device_type == 6:  # Inverter
        _LOGGER.debug("Creating sensors for inverter %d from IP %s", device_id, remote_ip)
        entities.extend([
            # Combined measurements
            OutbackInverterSensor(mate3, remote_ip, device_id, "total_inverter_current", "Total Inverter Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, remote_ip, device_id, "total_charger_current", "Total Charger Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, remote_ip, device_id, "total_buy_current", "Total Buy Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, remote_ip, device_id, "total_sell_current", "Total Sell Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, remote_ip, device_id, "ac_input_voltage", "AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, remote_ip, device_id, "ac_output_voltage", "AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            
            # Power measurements
            OutbackInverterSensor(mate3, remote_ip, device_id, "inverter_power", "Inverter Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, remote_ip, device_id, "charger_power", "Charger Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, remote_ip, device_id, "buy_power", "Buy Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, remote_ip, device_id, "sell_power", "Sell Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),

            # Mode sensors
            OutbackInverterSensor(mate3, remote_ip, device_id, "inverter_mode", "Inverter Mode",
                                None, None),
            OutbackInverterSensor(mate3, remote_ip, device_id, "ac_mode", "AC Mode",
                                None, None),
        ])
    elif device_type == 3:  # Charge Controller
        _LOGGER.debug("Creating sensors for charge controller %d from IP %s", device_id, remote_ip)
        entities.extend([
            OutbackChargeControllerSensor(mate3, remote_ip, device_id, "pv_current", "PV Current",
                                        SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackChargeControllerSensor(mate3, remote_ip, device_id, "pv_voltage", "PV Voltage",
                                        SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackChargeControllerSensor(mate3, remote_ip, device_id, "pv_power", "PV Power",
                                        SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackChargeControllerSensor(mate3, remote_ip, device_id, "output_current", "Output Current",
                                        SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackChargeControllerSensor(mate3, remote_ip, device_id, "battery_voltage", "Battery Voltage",
                                        SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackChargeControllerSensor(mate3, remote_ip, device_id, "charge_mode", "Charge Mode",
                                        None, None),
        ])

    _LOGGER.debug("Created %d entities for device type %d, id %d from IP %s", 
                 len(entities), device_type, device_id, remote_ip)
    return entities


class OutbackBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Outback MATE3 sensors."""

    def __init__(
            self,
            mate3: OutbackMate3,
            remote_ip: str,
            device_id: int,
            sensor_type: str,
            name: str,
            device_class: SensorDeviceClass | None,
            unit: str | None,
        ) -> None:
        """Initialize the sensor."""
        super().__init__(mate3)
        self._mate3 = mate3
        self._remote_ip = remote_ip
        self._device_id = device_id
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{DOMAIN}_{remote_ip}_{device_id}_{sensor_type}"
        _LOGGER.debug("Initialized sensor %s for device %d from IP %s", 
                     sensor_type, device_id, remote_ip)


class OutbackInverterSensor(OutbackBaseSensor):
    """Representation of an Outback inverter sensor."""

    def __init__(
            self,
            mate3: OutbackMate3,
            remote_ip: str,
            device_id: int,
            sensor_type: str,
            name: str,
            device_class: SensorDeviceClass | None,
            unit: str | None,
        ) -> None:
        """Initialize the inverter sensor."""
        super().__init__(mate3, remote_ip, device_id, sensor_type, name, device_class, unit)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"inverter_{remote_ip}_{device_id}")},
            name=f"Outback Inverter {device_id} ({remote_ip})",
            manufacturer="Outback Power",
            model="Radian Inverter",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if (self._remote_ip in self._mate3.inverters and 
            self._device_id in self._mate3.inverters[self._remote_ip]):
            value = self._mate3.inverters[self._remote_ip][self._device_id].get(self._sensor_type)
            _LOGGER.debug("Inverter sensor %s for device %d from IP %s value: %s", 
                         self._sensor_type, self._device_id, self._remote_ip, value)
            return value
        return None


class OutbackChargeControllerSensor(OutbackBaseSensor):
    """Representation of an Outback charge controller sensor."""

    def __init__(
            self,
            mate3: OutbackMate3,
            remote_ip: str,
            device_id: int,
            sensor_type: str,
            name: str,
            device_class: SensorDeviceClass | None,
            unit: str | None,
        ) -> None:
        """Initialize the charge controller sensor."""
        super().__init__(mate3, remote_ip, device_id, sensor_type, name, device_class, unit)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"charge_controller_{remote_ip}_{device_id}")},
            name=f"Outback Charge Controller {device_id} ({remote_ip})",
            manufacturer="Outback Power",
            model="Charge Controller",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if (self._remote_ip in self._mate3.charge_controllers and 
            self._device_id in self._mate3.charge_controllers[self._remote_ip]):
            value = self._mate3.charge_controllers[self._remote_ip][self._device_id].get(self._sensor_type)
            _LOGGER.debug("Charge controller sensor %s for device %d from IP %s value: %s", 
                         self._sensor_type, self._device_id, self._remote_ip, value)
            return value
        return None
