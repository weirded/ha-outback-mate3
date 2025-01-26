"""Support for Outback MATE3 sensors."""
from __future__ import annotations

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, OutbackMate3

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Outback MATE3 sensors."""
    mate3: OutbackMate3 = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    # Add inverter sensors
    for inv_id in mate3.inverters:
        entities.extend([
            OutbackInverterSensor(mate3, inv_id, "l1_inverter_current", "L1 Inverter Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, inv_id, "l1_charger_current", "L1 Charger Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, inv_id, "l1_buy_current", "L1 Buy Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, inv_id, "l1_sell_current", "L1 Sell Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, inv_id, "l1_ac_input_voltage", "L1 AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, inv_id, "l1_ac_output_voltage", "L1 AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, inv_id, "l2_inverter_current", "L2 Inverter Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, inv_id, "l2_charger_current", "L2 Charger Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, inv_id, "l2_buy_current", "L2 Buy Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, inv_id, "l2_sell_current", "L2 Sell Current",
                                SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackInverterSensor(mate3, inv_id, "l2_ac_input_voltage", "L2 AC Input Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, inv_id, "l2_ac_output_voltage", "L2 AC Output Voltage",
                                SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackInverterSensor(mate3, inv_id, "output_power", "Output Power",
                                SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackInverterSensor(mate3, inv_id, "inverter_mode", "Inverter Mode",
                                None, None),
            OutbackInverterSensor(mate3, inv_id, "ac_mode", "AC Mode",
                                None, None),
        ])

    # Add charge controller sensors
    for cc_id in mate3.charge_controllers:
        entities.extend([
            OutbackChargeControllerSensor(mate3, cc_id, "pv_current", "PV Current",
                                        SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackChargeControllerSensor(mate3, cc_id, "pv_voltage", "PV Voltage",
                                        SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackChargeControllerSensor(mate3, cc_id, "pv_power", "PV Power",
                                        SensorDeviceClass.POWER, UnitOfPower.WATT),
            OutbackChargeControllerSensor(mate3, cc_id, "output_current", "Output Current",
                                        SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            OutbackChargeControllerSensor(mate3, cc_id, "battery_voltage", "Battery Voltage",
                                        SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            OutbackChargeControllerSensor(mate3, cc_id, "charger_mode", "Charger Mode",
                                        None, None),
        ])

    async_add_entities(entities)


class OutbackBaseSensor(SensorEntity):
    """Base class for Outback MATE3 sensors."""

    def __init__(
        self,
        mate3: OutbackMate3,
        device_id: int,
        sensor_type: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._mate3 = mate3
        self._device_id = device_id
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{sensor_type}"
        self._state = None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state


class OutbackInverterSensor(OutbackBaseSensor):
    """Representation of an Outback inverter sensor."""

    def __init__(
        self,
        mate3: OutbackMate3,
        device_id: int,
        sensor_type: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
    ) -> None:
        """Initialize the inverter sensor."""
        super().__init__(mate3, device_id, sensor_type, name, device_class, unit)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"inverter_{device_id}")},
            name=f"Outback Inverter {device_id}",
            manufacturer="Outback Power",
            model="Radian Inverter",
        )


class OutbackChargeControllerSensor(OutbackBaseSensor):
    """Representation of an Outback charge controller sensor."""

    def __init__(
        self,
        mate3: OutbackMate3,
        device_id: int,
        sensor_type: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
    ) -> None:
        """Initialize the charge controller sensor."""
        super().__init__(mate3, device_id, sensor_type, name, device_class, unit)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"charge_controller_{device_id}")},
            name=f"Outback Charge Controller {device_id}",
            manufacturer="Outback Power",
            model="Charge Controller",
        )
