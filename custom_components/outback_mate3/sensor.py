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
from .const import DOMAIN, CHARGE_CONTROLLER_SENSORS, INVERTER_SENSORS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    _LOGGER.debug("Setting up sensor platform with entry_id: %s", entry.entry_id)
    
    mate3 = hass.data[DOMAIN][entry.entry_id]
    discovery_info = hass.data[DOMAIN].get(f"{entry.entry_id}_discovery")
    
    _LOGGER.debug("Retrieved discovery info: %s", discovery_info)
    
    if discovery_info is None:
        _LOGGER.debug("No discovery info, setting add_entities_callback")
        mate3.set_add_entities_callback(async_add_entities)
        return
        
    device_type = discovery_info["device_type"]
    entry_id = discovery_info["entry_id"]
    mac_address = discovery_info["mac_address"]
    
    _LOGGER.debug("Processing discovery info - type: %s, entry_id: %s, mac: %s",
                 device_type, entry_id, mac_address)
    
    if device_type == "mate3":
        # Create device info for MATE3
        device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            name=f"Outback MATE3 ({entry_id})",
            manufacturer="Outback Power",
            model="MATE3",
        )
        
        _LOGGER.debug("Created MATE3 device info: %s", device_info)
        
        # Create all inverter and charge controller entities
        entities = []
        
        # Add inverter entities
        for i in range(1, 11):  # Support up to 10 inverters
            _LOGGER.debug("Creating entities for inverter %d", i)
            for sensor_info in INVERTER_SENSORS:
                entities.append(
                    OutbackInverterSensor(
                        mate3,
                        entry_id,
                        i,
                        sensor_info[1],  # sensor_type
                        sensor_info[0],  # name
                        sensor_info[2],  # device_class
                        sensor_info[3],  # unit
                        mac_address,
                        device_info
                    )
                )
        
        # Add charge controller entities
        for i in range(1, 11):  # Support up to 10 charge controllers
            _LOGGER.debug("Creating entities for charge controller %d", i)
            for sensor_info in CHARGE_CONTROLLER_SENSORS:
                entities.append(
                    OutbackChargeControllerSensor(
                        mate3,
                        entry_id,
                        i,
                        sensor_info[1],  # sensor_type
                        sensor_info[0],  # name
                        sensor_info[2],  # device_class
                        sensor_info[3],  # unit
                        mac_address,
                        device_info
                    )
                )
        
        # Add system-wide sensors
        system_entities = [
            OutbackSystemSensor(mate3, "total_solar_power", "Total Solar Power",
                              SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackSystemSensor(mate3, "total_grid_power", "Total Grid Power",
                              SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackSystemSensor(mate3, "total_solar_energy", "Total Solar Energy",
                              SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
            OutbackSystemSensor(mate3, "total_grid_energy_import", "Total Grid Energy Import",
                              SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
            OutbackSystemSensor(mate3, "total_grid_energy_export", "Total Grid Energy Export",
                              SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
        ]
        entities.extend(system_entities)
        
        if entities:
            _LOGGER.debug("Adding %d entities for MATE3 %s", len(entities), mac_address)
            async_add_entities(entities)
    elif device_type == 6:  # Inverter
        _LOGGER.debug("Creating sensors for inverter %d from MAC %s", discovery_info["device_id"], mac_address)
        for sensor_info in INVERTER_SENSORS:
            entities.append(
                OutbackInverterSensor(
                    mate3,
                    entry_id,
                    discovery_info["device_id"],
                    sensor_info[1],  # sensor_type
                    sensor_info[0],  # name
                    sensor_info[2],  # device_class
                    sensor_info[3],  # unit
                    mac_address
                )
            )
    elif device_type == 3:  # Charge Controller
        _LOGGER.debug("Creating sensors for charge controller %d from MAC %s", discovery_info["device_id"], mac_address)
        for sensor_info in CHARGE_CONTROLLER_SENSORS:
            entities.append(
                OutbackChargeControllerSensor(
                    mate3,
                    entry_id,
                    discovery_info["device_id"],
                    sensor_info[1],  # sensor_type
                    sensor_info[0],  # name
                    sensor_info[2],  # device_class
                    sensor_info[3],  # unit
                    mac_address
                )
            )
            
    if entities:
        _LOGGER.debug("Adding %d entities for device type %d, id %d from MAC %s", 
                     len(entities), device_type, discovery_info["device_id"], mac_address)
        async_add_entities(entities)


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
    mac_address = discovery_info["mac_address"]

    # Create device-specific entities
    entities = create_device_entities(mate3, entry_id, device_type, device_id, mac_address)
    
    # Create combined entities if not already created
    if not hasattr(mate3, 'combined_entities_created'):
        entities.extend(create_combined_entities(mate3, entry_id, mac_address))
        mate3.combined_entities_created = True
        
    async_add_entities(entities)


def create_device_entities(mate3: OutbackMate3, entry_id: str, device_type: int, device_id: int, mac_address: str) -> List[SensorEntity]:
    """Create entities for a newly discovered device."""
    entities = []
    
    if device_type == 6:  # Inverter
        _LOGGER.debug("Creating sensors for inverter %d from entry %s", device_id, entry_id)
        entities.extend([
            OutbackInverterSensor(mate3, entry_id, device_id, "inverter_current", "Inverter Current",
                              SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "charger_current", "Charger Current",
                              SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "grid_current", "Grid Current",
                              SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "grid_voltage", "Grid Voltage",
                              SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "output_voltage", "Output Voltage",
                              SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "inverter_power", "Inverter Power",
                              SensorDeviceClass.POWER, UnitOfPower.WATT, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "charger_power", "Charger Power",
                              SensorDeviceClass.POWER, UnitOfPower.WATT, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "grid_power", "Grid Power",
                              SensorDeviceClass.POWER, UnitOfPower.WATT, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "inverter_mode", "Inverter Mode",
                              SensorDeviceClass.ENUM, None, mac_address),
            OutbackInverterSensor(mate3, entry_id, device_id, "ac_mode", "AC Mode",
                              SensorDeviceClass.ENUM, None, mac_address),
        ])
    elif device_type == 3:  # Charge Controller
        _LOGGER.debug("Creating sensors for charge controller %d from entry %s", device_id, entry_id)
        entities.extend([
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "solar_current", "Solar Current",
                                      SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, mac_address),
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "solar_voltage", "Solar Voltage",
                                      SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, mac_address),
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "battery_voltage", "Battery Voltage",
                                      SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, mac_address),
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "solar_power", "Solar Power",
                                      SensorDeviceClass.POWER, UnitOfPower.WATT, mac_address),
            OutbackChargeControllerSensor(mate3, entry_id, device_id, "charge_mode", "Charge Mode",
                                      SensorDeviceClass.ENUM, None, mac_address),
        ])

    _LOGGER.debug("Created %d entities for device type %d, id %d from entry %s", 
                 len(entities), device_type, device_id, entry_id)
    return entities


def create_combined_entities(mate3: OutbackMate3, entry_id: str, mac_address: str) -> List[SensorEntity]:
    """Create combined entities for energy dashboard."""
    _LOGGER.debug("Creating combined sensors for Mate3 at entry %s", entry_id)
    return [
        OutbackCombinedSensor(mate3, entry_id, "grid_energy", "Grid Energy",
                           SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, mac_address),
        OutbackCombinedSensor(mate3, entry_id, "inverter_energy", "Inverter Energy",
                           SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, mac_address),
        OutbackCombinedSensor(mate3, entry_id, "charger_energy", "Charger Energy",
                           SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, mac_address),
        OutbackCombinedSensor(mate3, entry_id, "solar_energy", "Solar Production",
                           SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, mac_address),
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
            mac_address: str,
            device_info: DeviceInfo | None = None,
        ) -> None:
        """Initialize the sensor."""
        super().__init__(mate3)
        self._mate3 = mate3
        self._entry_id = entry_id
        self._device_id = device_id
        self._sensor_type = sensor_type
        self._name = name
        self._device_class = device_class
        self._unit = unit
        self._mac_address = mac_address
        self._device_info = device_info
        
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
        
        # Set device info
        if device_info is not None:
            self._attr_device_info = device_info


class OutbackInverterSensor(OutbackBaseSensor):
    """Representation of an Outback inverter sensor."""

    def __init__(self, *args, **kwargs):
        """Initialize the inverter sensor."""
        super().__init__(*args, **kwargs)
        
        # Set up entity ID and unique ID using MAC address
        self.entity_id = f"sensor.mate3_{self._mac_address}_inverter_{self._device_id}_{self._sensor_type}"
        self._attr_unique_id = f"{DOMAIN}_{self._mac_address}_inverter_{self._device_id}_{self._sensor_type}"
        
        # Set up device info if not provided
        if self._device_info is None:
            device_name = f"Outback Inverter {self._device_id}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"inverter_{self._mac_address}_{self._device_id}")},
                name=device_name,
                manufacturer="Outback Power",
                model="Radian Inverter",
                via_device=(DOMAIN, self._mac_address),
            )
        
        # Make name distinct for each sensor
        self._attr_name = f"Inverter {self._device_id} {self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            device_key = f"{self._mac_address}_inverter_{self._device_id}"
            device_data = self._mate3.device_data.get(device_key)
            _LOGGER.debug("Getting value for inverter sensor %s from data: %s", device_key, device_data)
            
            if not device_data:
                return None
                
            if self._sensor_type == "inverter_current":
                return float(device_data[3])
            elif self._sensor_type == "charger_current":
                return float(device_data[4])
            elif self._sensor_type == "grid_current":
                return float(device_data[5])
            elif self._sensor_type == "grid_voltage":
                return float(device_data[6])
            elif self._sensor_type == "output_voltage":
                return float(device_data[7])
            elif self._sensor_type == "inverter_power":
                return float(device_data[8])
            elif self._sensor_type == "charger_power":
                return float(device_data[9])
            elif self._sensor_type == "grid_power":
                return float(device_data[10])
            elif self._sensor_type == "inverter_mode":
                return device_data[11]
            elif self._sensor_type == "ac_mode":
                return device_data[12]
        except (KeyError, IndexError, ValueError) as e:
            _LOGGER.warning("Error getting inverter sensor value: %s", str(e))
            return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class OutbackChargeControllerSensor(OutbackBaseSensor):
    """Representation of an Outback charge controller sensor."""

    def __init__(self, *args, **kwargs):
        """Initialize the charge controller sensor."""
        super().__init__(*args, **kwargs)
        
        # Set up entity ID and unique ID using MAC address
        self.entity_id = f"sensor.mate3_{self._mac_address}_cc_{self._device_id}_{self._sensor_type}"
        self._attr_unique_id = f"{DOMAIN}_{self._mac_address}_cc_{self._device_id}_{self._sensor_type}"
        
        # Set up device info if not provided
        if self._device_info is None:
            device_name = f"Outback Charge Controller {self._device_id}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"cc_{self._mac_address}_{self._device_id}")},
                name=device_name,
                manufacturer="Outback Power",
                model="Charge Controller",
                via_device=(DOMAIN, self._mac_address),
            )
        
        # Make name distinct for each sensor
        self._attr_name = f"Charge Controller {self._device_id} {self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            device_key = f"{self._mac_address}_cc_{self._device_id}"
            device_data = self._mate3.device_data.get(device_key)
            _LOGGER.debug("Getting value for charge controller sensor %s from data: %s", device_key, device_data)
            
            if not device_data:
                return None
                
            if self._sensor_type == "solar_current":
                return float(device_data[3])
            elif self._sensor_type == "solar_voltage":
                return float(device_data[4])
            elif self._sensor_type == "battery_voltage":
                return float(device_data[5])
            elif self._sensor_type == "solar_power":
                return float(device_data[6])
            elif self._sensor_type == "charge_mode":
                return device_data[7]
        except (KeyError, IndexError, ValueError) as e:
            _LOGGER.warning("Error getting charge controller sensor value: %s", str(e))
            return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class OutbackCombinedSensor(OutbackBaseSensor):
    """Representation of a combined Outback MATE3 sensor."""

    def __init__(self, *args, **kwargs):
        """Initialize the combined sensor."""
        super().__init__(*args, device_id=None, **kwargs)
        
        # Set up entity ID and unique ID using MAC address
        self.entity_id = f"sensor.mate3_{self._mac_address}_{self._sensor_type}"
        self._attr_unique_id = f"{DOMAIN}_{self._mac_address}_{self._sensor_type}"
        
        # Set up device info if not provided
        if self._device_info is None:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._mac_address)},
                name="Outback MATE3",
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


class OutbackSystemSensor(OutbackBaseSensor):
    """Representation of an Outback system-wide sensor."""

    def __init__(
            self,
            mate3: OutbackMate3,
            sensor_type: str,
            name: str,
            device_class: SensorDeviceClass | None,
            unit: str | None,
        ) -> None:
        """Initialize the system sensor."""
        super().__init__(mate3, "system", 0, sensor_type, name, device_class, unit)
        
        # Set up device info for the system device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "system")},
            name="Outback MATE3 System",
            manufacturer="Outback Power",
            model="MATE3 System",
        )
        
        if device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if self._sensor_type == "total_solar_power":
                return sum(float(data.get("pv_power", 0)) 
                         for ip in self._mate3.charge_controllers 
                         for data in self._mate3.charge_controllers[ip].values())
            elif self._sensor_type == "total_grid_power":
                return sum(float(data.get("grid_power", 0))
                         for ip in self._mate3.inverters
                         for data in self._mate3.inverters[ip].values())
            elif self._sensor_type == "total_solar_energy":
                # Convert Wh to kWh
                return sum(float(data.get("pv_power", 0)) / 1000.0
                         for ip in self._mate3.charge_controllers
                         for data in self._mate3.charge_controllers[ip].values())
            elif self._sensor_type == "total_grid_energy_import":
                # Only sum positive grid power (import) and convert to kWh
                return sum(max(0, float(data.get("grid_power", 0))) / 1000.0
                         for ip in self._mate3.inverters
                         for data in self._mate3.inverters[ip].values())
            elif self._sensor_type == "total_grid_energy_export":
                # Only sum negative grid power (export) and convert to kWh
                return sum(max(0, -float(data.get("grid_power", 0))) / 1000.0
                         for ip in self._mate3.inverters
                         for data in self._mate3.inverters[ip].values())
        except (ValueError, TypeError):
            return None
        return None
