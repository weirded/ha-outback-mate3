"""Constants for the Outback MATE3 integration."""
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfEnergy,
)

DOMAIN = "outback_mate3"
DEFAULT_PORT = 57027

# Device types
DEVICE_TYPE_INVERTER = "Inverter"
DEVICE_TYPE_CHARGE_CONTROLLER = "Charge Controller"

# Common sensor attributes
ATTR_DEVICE_TYPE = "device_type"
ATTR_DEVICE_ID = "device_id"
ATTR_REMOTE_IP = "remote_ip"

# Update interval in seconds
UPDATE_INTERVAL = 60

# Sensor definitions - (name, sensor_type, device_class, unit)
INVERTER_SENSORS = [
    ("Inverter Current", "inverter_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
    ("Charger Current", "charger_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
    ("Grid Current", "grid_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
    ("Grid Voltage", "grid_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
    ("Output Voltage", "output_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
    ("Inverter Power", "inverter_power", SensorDeviceClass.POWER, UnitOfPower.WATT),
    ("Charger Power", "charger_power", SensorDeviceClass.POWER, UnitOfPower.WATT),
    ("Grid Power", "grid_power", SensorDeviceClass.POWER, UnitOfPower.WATT),
    ("Inverter Mode", "inverter_mode", SensorDeviceClass.ENUM, None),
    ("AC Mode", "ac_mode", SensorDeviceClass.ENUM, None),
]

CHARGE_CONTROLLER_SENSORS = [
    ("Solar Current", "solar_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
    ("Solar Voltage", "solar_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
    ("Battery Voltage", "battery_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
    ("Solar Power", "solar_power", SensorDeviceClass.POWER, UnitOfPower.WATT),
    ("Charge Mode", "charge_mode", SensorDeviceClass.ENUM, None),
]
