"""The Outback MATE3 integration."""
import asyncio
import logging
import re
from typing import Any, Dict, Optional, Set

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    INVERTER_SENSORS,
    CHARGE_CONTROLLER_SENSORS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Outback MATE3 from a config entry."""
    _LOGGER.debug("Setting up Outback MATE3 integration with entry: %s", entry.as_dict())
    
    # Initialize data storage
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    # Create MATE3 instance
    mate3 = OutbackMate3(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = mate3
    
    # Create initial discovery info for MATE3
    discovery_info = {
        "device_type": "mate3",
        "entry_id": entry.entry_id,
        "mac_address": "default"  # Will be updated when first message arrives
    }
    hass.data[DOMAIN][f"{entry.entry_id}_discovery"] = discovery_info
    
    # Set up sensor platform
    await hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)
    
    # Set up UDP server
    try:
        class UDPServerProtocol(asyncio.DatagramProtocol):
            def connection_made(self, transport):
                self.transport = transport

            def datagram_received(self, data, addr):
                asyncio.create_task(mate3.handle_message(data, addr))

        # Create UDP endpoint
        loop = asyncio.get_event_loop()
        transport, _ = await loop.create_datagram_endpoint(
            UDPServerProtocol,
            local_addr=('0.0.0.0', entry.data[CONF_PORT])
        )
        
        mate3.transport = transport
        
        entry.async_on_unload(
            entry.add_update_listener(async_update_listener)
        )
        
        # Add cleanup callback
        async def stop_server(event):
            """Stop UDP server."""
            if mate3.transport:
                mate3.transport.close()
        
        hass.bus.async_listen_once("homeassistant_stop", stop_server)
        
        _LOGGER.debug("Outback MATE3 integration setup complete")
        return True
        
    except Exception as e:
        _LOGGER.error("Error setting up UDP server: %s", str(e))
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Outback MATE3 integration")
    
    # Close UDP transport if it exists
    mate3 = hass.data[DOMAIN][entry.entry_id]
    if mate3.transport:
        mate3.transport.close()
    
    # Unload sensors
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_discovery", None)
    
    return unload_ok

async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

class OutbackMate3:
    """Main class for Outback MATE3 integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the MATE3 integration."""
        self.hass = hass
        self.entry = entry
        self.port = entry.data[CONF_PORT]
        self._add_entities_callback = None
        self.charge_controllers: Dict[str, Dict[int, dict]] = {}  # mac_address -> {device_id -> data}
        self.inverters: Dict[str, Dict[int, dict]] = {}  # mac_address -> {device_id -> data}
        self.discovered_devices: Set[str] = set()  # Set of "mac_address_type_id" strings
        self.transport = None
        self.device_data = {}
        _LOGGER.debug("Initialized OutbackMate3 with port %d", self.port)

    def set_add_entities_callback(self, callback):
        """Set callback for adding entities."""
        self._add_entities_callback = callback
        
    async def handle_message(self, data: bytes, addr: tuple) -> None:
        """Handle incoming UDP message."""
        try:
            message = data.decode().strip()
            _LOGGER.debug("Processing message: %s", message)
            
            # Only process messages that start with MAC address format [XXXXXX-XXXXXX]
            if not re.match(r'^\[[0-9A-F]{6}-[0-9A-F]{6}\]', message):
                _LOGGER.debug("Skipping message without MAC address format")
                return
            
            # Split into header and device messages
            try:
                header = message[1:15]  # Extract MAC address without brackets
                mac_address = header.replace('-', '')
                
                # Update discovery info with actual MAC address if needed
                discovery_info = self.hass.data[DOMAIN].get(f"{self.entry.entry_id}_discovery")
                if discovery_info and discovery_info["mac_address"] == "default":
                    discovery_info["mac_address"] = mac_address
                    _LOGGER.debug("Updated discovery info with MAC address: %s", mac_address)
                    
                    # Force sensor setup if this is the first message
                    if self._add_entities_callback:
                        _LOGGER.debug("Setting up sensors for first time with MAC: %s", mac_address)
                        await self.setup_sensors(mac_address)
                
                # Process device data
                device_data = message[16:].split(',')
                if len(device_data) >= 2:
                    device_type = device_data[0]
                    device_no = int(device_data[1])
                    
                    if device_type in ["1", "2"]:
                        self._process_inverter(device_no, device_data, mac_address)
                    elif device_type in ["4", "5"]:
                        self._process_charge_controller(device_no, device_data, mac_address)
                    
            except (IndexError, ValueError) as e:
                _LOGGER.warning("Error processing message: %s", str(e))
                
        except Exception as e:
            _LOGGER.error("Error handling message: %s", str(e))

    async def setup_sensors(self, mac_address: str) -> None:
        """Set up sensors for the first time."""
        if self._add_entities_callback:
            _LOGGER.debug("Setting up MATE3 entities for %s", mac_address)
            # Create inverter sensors for device 1 (assuming at least one inverter)
            inverter_sensors = [
                OutbackInverterSensor(
                    self, mac_address, 1, name, sensor_type, device_class, unit, state_class
                )
                for name, sensor_type, device_class, unit, state_class in INVERTER_SENSORS
            ]
            
            # Create charge controller sensors for device 1 (assuming at least one CC)
            cc_sensors = [
                OutbackChargeControllerSensor(
                    self, mac_address, 1, name, sensor_type, device_class, unit, state_class
                )
                for name, sensor_type, device_class, unit, state_class in CHARGE_CONTROLLER_SENSORS
            ]
            
            # Add all sensors
            self._add_entities_callback(inverter_sensors + cc_sensors, True)
            self._add_entities_callback = None  # Clear callback after use

    def _process_inverter(self, device_no, values, mac_address):
        """Process inverter data."""
        _LOGGER.debug("Processing inverter %d data: %s", device_no, values)
        
        # Get existing data or initialize new
        device_key = f"{mac_address}_inverter_{device_no}"
        device_data = list(self.device_data.get(device_key, [0] * 15))
        
        try:
            if len(values) >= 15:
                # Type 1: Status data
                if values[0] == "1":
                    device_data[11] = values[11]  # inverter_mode
                    device_data[12] = values[12]  # ac_mode
                # Type 2: Power data
                elif values[0] == "2":
                    device_data[3] = float(values[3])   # inverter_current
                    device_data[4] = float(values[4])   # charger_current
                    device_data[5] = float(values[5])   # grid_current
                    device_data[6] = float(values[6])   # grid_voltage
                    device_data[7] = float(values[7])   # output_voltage
                    device_data[8] = float(values[8])   # inverter_power
                    device_data[9] = float(values[9])   # charger_power
                    device_data[10] = float(values[10]) # grid_power
                
                # Store combined data
                self.device_data[device_key] = device_data
                _LOGGER.debug("Updated inverter data for %s: %s", device_key, device_data)
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Error processing inverter data: %s", str(e))

    def _process_charge_controller(self, device_no, values, mac_address):
        """Process charge controller data."""
        _LOGGER.debug("Processing charge controller %d data: %s", device_no, values)
        
        # Get existing data or initialize new
        device_key = f"{mac_address}_cc_{device_no}"
        device_data = list(self.device_data.get(device_key, [0] * 10))
        
        try:
            if len(values) >= 8:
                # Type 4: Status data
                if values[0] == "4":
                    device_data[7] = values[7]  # charge_mode
                # Type 5: Power data
                elif values[0] == "5":
                    device_data[3] = float(values[3])  # solar_current
                    device_data[4] = float(values[4])  # solar_voltage
                    device_data[5] = float(values[5])  # battery_voltage
                    device_data[6] = float(values[6])  # solar_power
                
                # Store combined data
                self.device_data[device_key] = device_data
                _LOGGER.debug("Updated charge controller data for %s: %s", device_key, device_data)
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Error processing charge controller data: %s", str(e))

    def get_aggregated_value(self, sensor_type: str) -> float:
        """Get aggregated value across all devices."""
        total = 0.0
        
        # Sum up values from all inverters
        for mac_devices in self.inverters.values():
            for device_data in mac_devices.values():
                if sensor_type in device_data:
                    try:
                        total += float(device_data[sensor_type])
                    except (ValueError, TypeError):
                        pass
                        
        # Sum up values from all charge controllers
        for mac_devices in self.charge_controllers.values():
            for device_data in mac_devices.values():
                if sensor_type in device_data:
                    try:
                        total += float(device_data[sensor_type])
                    except (ValueError, TypeError):
                        pass
                        
        return total

    def has_aggregated_value(self, sensor_type: str) -> bool:
        """Check if we have data for the given sensor type."""
        # Check inverters
        for mac_devices in self.inverters.values():
            for device_data in mac_devices.values():
                if sensor_type in device_data:
                    return True
                    
        # Check charge controllers
        for mac_devices in self.charge_controllers.values():
            for device_data in mac_devices.values():
                if sensor_type in device_data:
                    return True
                    
        return False
