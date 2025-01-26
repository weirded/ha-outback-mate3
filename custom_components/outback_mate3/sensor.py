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

from . import OutbackMate3
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    if discovery_info is None:
        return

    mate3 = hass.data[DOMAIN][discovery_info["remote_ip"]]
    device_type = discovery_info["device_type"]
    device_id = discovery_info["device_id"]
    remote_ip = discovery_info["remote_ip"]

    # Only create entities for the first device discovered
    if not hasattr(mate3, 'entities_created'):
        entities = create_mate3_entities(mate3, remote_ip)
        async_add_entities(entities)
        mate3.entities_created = True


def create_mate3_entities(mate3: OutbackMate3, remote_ip: str) -> List[SensorEntity]:
    """Create entities for the Mate3 system."""
    entities = []
    
    _LOGGER.debug("Creating sensors for Mate3 at IP %s", remote_ip)
    entities.extend([
        # Grid measurements
        OutbackMate3Sensor(mate3, remote_ip, "grid_current", "Grid Current",
                          SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
        OutbackMate3Sensor(mate3, remote_ip, "grid_voltage", "Grid Voltage",
                          SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
        OutbackMate3Sensor(mate3, remote_ip, "grid_power", "Grid Power",
                          SensorDeviceClass.POWER, UnitOfPower.WATT),
        OutbackMate3Sensor(mate3, remote_ip, "grid_energy", "Grid Energy",
                          SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),

        # Inverter measurements
        OutbackMate3Sensor(mate3, remote_ip, "inverter_current", "Inverter Current",
                          SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
        OutbackMate3Sensor(mate3, remote_ip, "inverter_power", "Inverter Power",
                          SensorDeviceClass.POWER, UnitOfPower.WATT),
        OutbackMate3Sensor(mate3, remote_ip, "inverter_energy", "Inverter Energy",
                          SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),

        # Charger measurements
        OutbackMate3Sensor(mate3, remote_ip, "charger_current", "Charger Current",
                          SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
        OutbackMate3Sensor(mate3, remote_ip, "charger_power", "Charger Power",
                          SensorDeviceClass.POWER, UnitOfPower.WATT),
        OutbackMate3Sensor(mate3, remote_ip, "charger_energy", "Charger Energy",
                          SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),

        # Solar measurements
        OutbackMate3Sensor(mate3, remote_ip, "solar_current", "Solar Current",
                          SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
        OutbackMate3Sensor(mate3, remote_ip, "solar_voltage", "Solar Voltage",
                          SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
        OutbackMate3Sensor(mate3, remote_ip, "solar_power", "Solar Power",
                          SensorDeviceClass.POWER, UnitOfPower.WATT),
        OutbackMate3Sensor(mate3, remote_ip, "solar_energy", "Solar Production",
                          SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),

        # Battery measurements
        OutbackMate3Sensor(mate3, remote_ip, "battery_voltage", "Battery Voltage",
                          SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),

        # System status
        OutbackMate3Sensor(mate3, remote_ip, "system_mode", "System Mode",
                          SensorDeviceClass.ENUM, None),
    ])

    _LOGGER.debug("Created %d entities for Mate3 at IP %s", 
                 len(entities), remote_ip)
    return entities


class OutbackMate3Sensor(CoordinatorEntity, SensorEntity):
    """Representation of an Outback MATE3 sensor."""

    def __init__(
            self,
            mate3: OutbackMate3,
            remote_ip: str,
            sensor_type: str,
            name: str,
            device_class: SensorDeviceClass | None,
            unit: str | None,
        ) -> None:
        """Initialize the sensor."""
        super().__init__(mate3)
        self._mate3 = mate3
        self._remote_ip = remote_ip
        self._sensor_type = sensor_type
        
        # Create entity_id friendly IP (replace dots with underscores)
        ip_id = remote_ip.replace('.', '_')
        
        # Set entity name and ID
        self._attr_has_entity_name = True
        self._attr_name = name
        self.entity_id = f"sensor.mate3_{ip_id}_{sensor_type}"
        
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        
        # Set state class based on device class
        if device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif device_class not in [SensorDeviceClass.ENUM]:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            
        self._attr_unique_id = f"{DOMAIN}_{remote_ip}_{sensor_type}"

        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"mate3_{remote_ip}")},
            name=f"Outback MATE3 ({remote_ip})",
            manufacturer="Outback Power",
            model="MATE3",
        )

        _LOGGER.debug("Initialized sensor %s for Mate3 at IP %s", 
                     sensor_type, remote_ip)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._mate3.get_aggregated_value(self._sensor_type)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._mate3.has_aggregated_value(self._sensor_type)
