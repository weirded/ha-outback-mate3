"""The Outback MATE3 integration."""
import asyncio
import logging
import socket
import re
from datetime import datetime
from typing import Dict, Set

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import (
    CONF_PORT,
    Platform,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Outback MATE3 from a config entry."""
    _LOGGER.debug("Setting up Outback MATE3 integration with entry: %s", entry.as_dict())
    
    # Initialize data storage
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    # Create MATE3 instance
    mate3 = OutbackMate3(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = mate3
    
    # Set up UDP server
    server = await asyncio.start_server(
        mate3.handle_connection,
        host="0.0.0.0",
        port=entry.data[CONF_PORT],
    )
    
    # Store server for cleanup
    mate3.server = server
    
    # Set up sensor platform
    await hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)
    
    # Create initial discovery info for MATE3
    discovery_info = {
        "device_type": "mate3",
        "entry_id": entry.entry_id,
        "mac_address": "default"  # Will be updated when first message arrives
    }
    hass.data[DOMAIN][f"{entry.entry_id}_discovery"] = discovery_info
    
    entry.async_on_unload(
        entry.add_update_listener(async_update_listener)
    )
    
    _LOGGER.debug("Outback MATE3 integration setup complete")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        mate3 = hass.data[DOMAIN].pop(entry.entry_id)
        mate3.stop_listening()

    return unload_ok


class OutbackMate3(DataUpdateCoordinator):
    """Main class for Outback MATE3 integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the MATE3 integration."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.hass = hass
        self.entry = entry
        self.port = entry.data[CONF_PORT]
        self._socket = None
        self._running = False
        self._add_entities_callback = None
        self.device_counts: Dict[str, Dict[int, int]] = {}  # mac_address -> {device_type -> count}
        self.charge_controllers: Dict[str, Dict[int, dict]] = {}  # mac_address -> {device_id -> data}
        self.inverters: Dict[str, Dict[int, dict]] = {}  # mac_address -> {device_id -> data}
        self.discovered_devices: Set[str] = set()  # Set of "mac_address_type_id" strings
        self.server = None
        self.device_data = {}
        _LOGGER.debug("Initialized OutbackMate3 with port %d", self.port)

    async def async_setup_entry(self, hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Set up Outback MATE3 from a config entry."""
        _LOGGER.debug("Setting up Outback MATE3 integration for entry: %s", entry.entry_id)
        
        self.hass = hass
        self.port = entry.data[CONF_PORT]
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = self
        
        # Forward to sensor platform
        _LOGGER.debug("Setting up sensor platform")
        await hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)
        
        return True

    def set_add_entities_callback(self, callback: AddEntitiesCallback) -> None:
        """Set the callback for adding entities."""
        _LOGGER.debug("Setting add_entities_callback")
        self._add_entities_callback = callback

    def start_listening(self):
        """Start listening for UDP packets."""
        if not self._running:
            self._running = True
            asyncio.create_task(self._listen())
            _LOGGER.debug("Created UDP listener task")

    def stop_listening(self):
        """Stop listening for UDP packets."""
        self._running = False
        if self._socket:
            self._socket.close()

    async def _listen(self):
        """Listen for UDP packets from MATE3."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(('', self.port))
        self._socket.setblocking(False)
        
        _LOGGER.debug("Started UDP listener on port %d", self.port)
        
        while self._running:
            try:
                data, addr = await self.hass.async_add_executor_job(
                    self._socket.recvfrom, 1024
                )
                remote_ip = addr[0]
                
                await self.hass.async_add_executor_job(
                    self._process_data, data, self.entry.entry_id
                )
            except BlockingIOError:
                await asyncio.sleep(0.1)
            except Exception as e:
                _LOGGER.error("Error in UDP listener: %s", str(e))
                await asyncio.sleep(1)

    def _process_data(self, data, entry_id):
        """Process received data."""
        try:
            # Decode and clean up the data
            message = data.decode().strip()
            _LOGGER.debug("Processing message: %s", message)
            
            # Only process messages that start with MAC address format [XXXXXX-XXXXXX]
            if not re.match(r'^\[[0-9A-F]{6}-[0-9A-F]{6}\]', message):
                _LOGGER.debug("Skipping message without MAC address format")
                return
            
            # Split into header and device messages
            try:
                header, *devices = re.split(']<|><|>', message)
                # Extract MAC address from header [XXXXXX-XXXXXX]
                mac_match = re.match(r'\[([0-9A-F]{6}-[0-9A-F]{6})', header)
                if not mac_match:
                    _LOGGER.warning("Could not find MAC address in message header: %s", header)
                    return
                    
                # Remove hyphen from MAC address
                mac_address = mac_match.group(1).replace('-', '')
                
                # Register MATE3 device if not already registered
                mate3_id = f"{mac_address}"
                if mate3_id not in self.discovered_devices:
                    _LOGGER.debug("Discovered new MATE3: %s", mate3_id)
                    self.discovered_devices.add(mate3_id)
                    
                    # Create discovery info for MATE3
                    discovery_info = {
                        "device_type": "mate3",
                        "entry_id": entry_id,
                        "mac_address": mac_address
                    }
                    
                    # Store discovery info in hass.data
                    self.hass.data[DOMAIN][f"{entry_id}_discovery"] = discovery_info
                    
                    # Add MATE3 entities
                    if self._add_entities_callback:
                        _LOGGER.debug("Setting up MATE3 entities for %s with discovery info: %s", mate3_id, discovery_info)
                        self.hass.create_task(
                            self.hass.config_entries.async_forward_entry_setup(
                                self.hass.config_entries.async_entries(DOMAIN)[0],
                                Platform.SENSOR
                            )
                        )
                    else:
                        _LOGGER.warning("No add_entities_callback available for MATE3: %s", mate3_id)
                
                _LOGGER.debug("Processing %d device messages from MAC %s", len(devices), mac_address)
                
                for device_msg in devices:
                    if not device_msg:  # Skip empty messages
                        continue
                        
                    # Split into values and remove empty strings
                    values = [v for v in device_msg.split(',') if v]
                    
                    if len(values) < 3:  # Need at least type and device number
                        continue
                        
                    try:
                        device_type = int(values[0])
                        device_no = int(values[1])
                        
                        # Create device identifier using MAC instead of entry_id
                        device_id = f"{mac_address}_{device_type}_{device_no}"
                        
                        _LOGGER.debug("Processing device: type=%d, no=%d, id=%s, values=%s", 
                                    device_type, device_no, device_id, values)
                        
                        # Process device data based on type
                        if device_type == 1:  # Inverter status
                            self._process_inverter(device_no, values, mac_address)
                        elif device_type == 2:  # Inverter power
                            self._process_inverter(device_no, values, mac_address)
                        elif device_type == 4:  # Charge controller status
                            self._process_charge_controller(device_no, values, mac_address)
                        elif device_type == 5:  # Charge controller power
                            self._process_charge_controller(device_no, values, mac_address)
                            
                    except (ValueError, IndexError) as e:
                        _LOGGER.warning("Error processing device message: %s - %s", device_msg, str(e))
                        continue
                        
            except ValueError as e:
                _LOGGER.warning("Invalid message format: %s - %s", message, str(e))
                    
        except Exception as e:
            _LOGGER.error("Error processing data: %s", str(e))

    async def handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming UDP data."""
        try:
            data = await reader.read(1024)
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
                entry_id = list(self.hass.config_entries.async_entries(DOMAIN))[0].entry_id
                discovery_info = self.hass.data[DOMAIN].get(f"{entry_id}_discovery")
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
            _LOGGER.error("Error handling connection: %s", str(e))
        finally:
            writer.close()
            await writer.wait_closed()
            
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
