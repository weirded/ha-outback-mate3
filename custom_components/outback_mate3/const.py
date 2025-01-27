"""Constants for the Outback MATE3 integration."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
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

# Sensor definitions - (name, sensor_type, device_class, unit, state_class)
INVERTER_SENSORS = [
    ("Current", "inverter_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, SensorStateClass.MEASUREMENT),
    ("Charger Current", "charger_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, SensorStateClass.MEASUREMENT),
    ("Grid Current", "grid_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, SensorStateClass.MEASUREMENT),
    ("Grid Voltage", "grid_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, SensorStateClass.MEASUREMENT),
    ("Output Voltage", "output_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, SensorStateClass.MEASUREMENT),
    ("Power", "inverter_power", SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT),
    ("Charger Power", "charger_power", SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT),
    ("Grid Power", "grid_power", SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT),
    ("Operating Mode", "inverter_mode", None, None, None),  # Text sensor
    ("AC Mode", "ac_mode", None, None, None),  # Text sensor
]

CHARGE_CONTROLLER_SENSORS = [
    ("Solar Current", "solar_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, SensorStateClass.MEASUREMENT),
    ("Solar Voltage", "solar_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, SensorStateClass.MEASUREMENT),
    ("Battery Voltage", "battery_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, SensorStateClass.MEASUREMENT),
    ("Solar Power", "solar_power", SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT),
    ("Charge Mode", "charge_mode", None, None, None),  # Text sensor
]
