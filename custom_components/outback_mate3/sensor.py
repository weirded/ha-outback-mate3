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
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from . import OutbackMate3
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    mate3 = hass.data[DOMAIN][entry.entry_id]
    mate3.set_add_entities_callback(async_add_entities)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    if discovery_info is None:
        return

    for entry_id, mate3_instance in hass.data[DOMAIN].items():
        if isinstance(mate3_instance, OutbackMate3):
            mate3 = mate3_instance
            break
    else:
        _LOGGER.error("No MATE3 instance found")
        return

    device_type = discovery_info["device_type"]
    device_id = discovery_info["device_id"]
    entry_id = discovery_info["entry_id"]

    # Create device-specific entities
    entities = create_device_entities(mate3, entry_id, device_type, device_id)
    
    # Create combined entities if not already created
    if not hasattr(mate3, 'combined_entities_created'):
        entities.extend(create_combined_entities(mate3, entry_id))
        mate3.combined_entities_created = True
        
    async_add_entities(entities)


def create_device_entities(mate3: OutbackMate3, entry_id: str, device_type: int, device_id: int) -> List[SensorEntity]:
    """Create entities for a newly discovered device."""
    entities = []
    
    if device_type == 6:  # Inverter
        _LOGGER.debug("Creating sensors for inverter %d from entry %s", device_id, entry_id)
        entities.extend([
            OutbackInverterSensor(mate3, entry_id, device_id, "inverter_current", "Inverter Current",
                              SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, entry_id, device_id, "charger_current", "Charger Current",
                              SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, entry_id, device_id, "grid_current", "Grid Current",
                              SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, entry_id, device_id, "grid_voltage", "Grid Voltage",
                              SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, entry_id, device_id, "output_voltage", "Output Voltage",
                              SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, entry_id, device_id, "inverter_power", "Inverter Power",
                              SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, entry_id, device_id, "charger_power", "Charger Power",
                              SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, entry_id, device_id, "grid_power", "Grid Power",
                              SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, entry_id, device_id, "inverter_mode", "Inverter Mode",
                              SensorDeviceClass.ENUM, None),
            OutbackInverterSensor(mate3, entry_id, device_id, "ac_mode", "AC Mode",
                              SensorDeviceClass.ENUM, None),
        ])
    elif device_type == 3:  # Charge Controller
        _LOGGER.debug("Creating sensors for charge controller %d from entry %s", device_id, entry_id)
        entities.extend([
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "solar_current", "Solar Current",
                                      SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "solar_voltage", "Solar Voltage",
                                      SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "battery_voltage", "Battery Voltage",
                                      SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "solar_power", "Solar Power",
                                      SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "charge_mode", "Charge Mode",
                                      SensorDeviceClass.ENUM, None),
        ])

    _LOGGER.debug("Created %d entities for device type %d, id %d from entry %s", 
                 len(entities), device_type, device_id, entry_id)
    return entities


def create_combined_entities(mate3: OutbackMate3, entry_id: str) -> List[SensorEntity]:
    """Create combined entities for energy dashboard."""
    _LOGGER.debug("Creating combined sensors for Mate3 at entry %s", entry_id)
    return [
        OutbackCombinedSensor(mate3, entry_id, "grid_energy", "Grid Energy",
                           SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
        OutbackCombinedSensor(mate3, entry_id, "inverter_energy", "Inverter Energy",
                           SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
        OutbackCombinedSensor(mate3, entry_id, "charger_energy", "Charger Energy",
                           SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
        OutbackCombinedSensor(mate3, entry_id, "solar_energy", "Solar Production",
                           SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
    ]


class OutbackBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Outback MATE3 sensors."""

    def __init__(
            self,
            mate3: OutbackMate3,
            entry_id: str,
            device_id: int | None,
            sensor_type: str,
            name: str,
            device_class: SensorDeviceClass | None,
            unit: str | None,
        ) -> None:
        """Initialize the sensor."""
        super().__init__(mate3)
        self._mate3 = mate3
        self._entry_id = entry_id
        self._device_id = device_id
        self._sensor_type = sensor_type
        
        # Create entity_id friendly IP (replace dots with underscores)
        entry_id_id = entry_id.replace('.', '_')
        
        # Set entity name and ID
        self._attr_has_entity_name = True
        self._attr_name = name
        
        # Set device class and unit
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        
        # Set state class based on device class
        if device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif device_class not in [SensorDeviceClass.ENUM]:
            self._attr_state_class = SensorStateClass.MEASUREMENT


class OutbackInverterSensor(OutbackBaseSensor):
    """Representation of an Outback inverter sensor."""

    def __init__(self, *args, **kwargs):
        """Initialize the inverter sensor."""
        super().__init__(*args, **kwargs)
        
        # Set up entity ID and unique ID
        entry_id_id = self._entry_id.replace('.', '_')
        self.entity_id = f"sensor.mate3_{entry_id_id}_inverter_{self._device_id}_{self._sensor_type}"
        self._attr_unique_id = f"{DOMAIN}_{self._entry_id}_inverter_{self._device_id}_{self._sensor_type}"
        
        # Set up device info
        device_name = f"Outback Inverter {self._device_id} ({self._entry_id})"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"inverter_{self._entry_id}_{self._device_id}")},
            name=device_name,
            manufacturer="Outback Power",
            model="Radian Inverter",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if (self._entry_id in self._mate3.inverters and 
            self._device_id in self._mate3.inverters[self._entry_id]):
            return self._mate3.inverters[self._entry_id][self._device_id].get(self._sensor_type)
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (self._entry_id in self._mate3.inverters and 
                self._device_id in self._mate3.inverters[self._entry_id] and
                self._sensor_type in self._mate3.inverters[self._entry_id][self._device_id])


class OutbackChargeControllerSensor(OutbackBaseSensor):
    """Representation of an Outback charge controller sensor."""

    def __init__(self, *args, **kwargs):
        """Initialize the charge controller sensor."""
        super().__init__(*args, **kwargs)
        
        # Set up entity ID and unique ID
        entry_id_id = self._entry_id.replace('.', '_')
        self.entity_id = f"sensor.mate3_{entry_id_id}_cc_{self._device_id}_{self._sensor_type}"
        self._attr_unique_id = f"{DOMAIN}_{self._entry_id}_cc_{self._device_id}_{self._sensor_type}"
        
        # Set up device info
        device_name = f"Outback Charge Controller {self._device_id} ({self._entry_id})"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"cc_{self._entry_id}_{self._device_id}")},
            name=device_name,
            manufacturer="Outback Power",
            model="Charge Controller",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if (self._entry_id in self._mate3.charge_controllers and 
            self._device_id in self._mate3.charge_controllers[self._entry_id]):
            return self._mate3.charge_controllers[self._entry_id][self._device_id].get(self._sensor_type)
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (self._entry_id in self._mate3.charge_controllers and 
                self._device_id in self._mate3.charge_controllers[self._entry_id] and
                self._sensor_type in self._mate3.charge_controllers[self._entry_id][self._device_id])


class OutbackCombinedSensor(OutbackBaseSensor):
    """Representation of a combined Outback MATE3 sensor."""

    def __init__(self, *args, **kwargs):
        """Initialize the combined sensor."""
        super().__init__(*args, device_id=None, **kwargs)
        
        # Set up entity ID and unique ID
        entry_id_id = self._entry_id.replace('.', '_')
        self.entity_id = f"sensor.mate3_{entry_id_id}_{self._sensor_type}"
        self._attr_unique_id = f"{DOMAIN}_{self._entry_id}_{self._sensor_type}"
        
        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"mate3_{self._entry_id}")},
            name=f"Outback MATE3 ({self._entry_id})",
            manufacturer="Outback Power",
            model="MATE3",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._mate3.get_aggregated_value(self._sensor_type)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._mate3.has_aggregated_value(self._sensor_type)
