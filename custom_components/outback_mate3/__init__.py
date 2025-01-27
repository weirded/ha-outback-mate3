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
    _LOGGER.debug("Setting up Outback MATE3 integration")
    hass.data.setdefault(DOMAIN, {})
    
    mate3 = OutbackMate3(hass, entry.data[CONF_PORT], entry.entry_id)
    hass.data[DOMAIN][entry.entry_id] = mate3

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    _LOGGER.debug("Starting UDP listener")
    mate3.start_listening()
    
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

    def __init__(self, hass: HomeAssistant, port: int, entry_id: str):
        """Initialize the MATE3 integration."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.hass = hass
        self.port = port
        self._socket = None
        self._running = False
        self._add_entities_callback = None
        self.device_counts: Dict[str, Dict[int, int]] = {}  # entry_id -> {device_type -> count}
        self.charge_controllers: Dict[str, Dict[int, dict]] = {}  # entry_id -> {device_id -> data}
        self.inverters: Dict[str, Dict[int, dict]] = {}  # entry_id -> {device_id -> data}
        self.discovered_devices: Set[str] = set()  # Set of "entry_id_type_id" strings
        self._entry_id = entry_id
        _LOGGER.debug("Initialized OutbackMate3 with port %d", port)

    def set_add_entities_callback(self, callback: AddEntitiesCallback) -> None:
        """Set the callback for adding entities."""
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
                    self._process_data, data, self._entry_id
                )
            except BlockingIOError:
                await asyncio.sleep(0.1)
            except Exception as e:
                _LOGGER.error("Error in UDP listener: %s", str(e))
                await asyncio.sleep(1)

    def _process_data(self, data, entry_id):
        """Process received data."""
        try:
            # Split data into device messages
            messages = data.decode().strip().split('\n')
            for message in messages:
                if not message:
                    continue
                    
                # Extract device type and number
                match = re.match(r'(\d+),(\d+),', message)
                if match:
                    device_type = int(match.group(1))
                    device_no = int(match.group(2))
                    self._process_device(message, device_type, device_no, entry_id)
                else:
                    _LOGGER.warning("Invalid message format: %s", message)
                    
        except Exception as e:
            _LOGGER.error("Error processing data: %s", str(e))

    def _process_device(self, message, device_type, device_no, entry_id):
        """Process individual device data."""
        # Create device identifier
        device_id = f"{entry_id}_{device_type}_{device_no}"
        
        # Skip if we've already discovered this device
        if device_id in self.discovered_devices:
            if device_type == 2:  # Inverter
                self._process_inverter(device_no, message.split(','), entry_id)
            elif device_type == 3:  # Charge Controller
                self._process_charge_controller(device_no, message.split(','), entry_id)
            return
            
        # Add to discovered devices
        self.discovered_devices.add(device_id)
        
        # Initialize device counts for this IP if not exists
        if entry_id not in self.device_counts:
            self.device_counts[entry_id] = {}
            
        # Initialize count for this device type if not exists
        if device_type not in self.device_counts[entry_id]:
            self.device_counts[entry_id][device_type] = 0
            
        # Increment device count
        self.device_counts[entry_id][device_type] += 1
        
        # Create discovery info
        discovery_info = {
            "device_type": device_type,
            "device_id": device_no,
            "entry_id": entry_id
        }
        
        # Add entities
        if self._add_entities_callback:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.hass.config_entries.async_entries(DOMAIN)[0],
                    Platform.SENSOR,
                    discovery_info
                )
            )
        
        # Process device data
        if device_type == 2:  # Inverter
            self._process_inverter(device_no, message.split(','), entry_id)
        elif device_type == 3:  # Charge Controller
            self._process_charge_controller(device_no, message.split(','), entry_id)

    def _process_inverter(self, no, values, entry_id):
        """Process inverter data."""
        if len(values) < 15:
            return
            
        if entry_id not in self.inverters:
            self.inverters[entry_id] = {}
            
        if no not in self.inverters[entry_id]:
            self.inverters[entry_id][no] = {}
            
        try:
            self.inverters[entry_id][no].update({
                'inverter_current': float(values[3]),
                'charger_current': float(values[4]),
                'grid_current': float(values[5]),
                'grid_voltage': float(values[6]),
                'output_voltage': float(values[7]),
                'inverter_power': float(values[8]),
                'charger_power': float(values[9]),
                'grid_power': float(values[10]),
                'inverter_mode': values[11],
                'ac_mode': values[12],
            })
        except (ValueError, IndexError) as e:
            _LOGGER.error("Error processing inverter data: %s", str(e))

    def _process_charge_controller(self, no, values, entry_id):
        """Process charge controller data."""
        if len(values) < 8:
            return
            
        if entry_id not in self.charge_controllers:
            self.charge_controllers[entry_id] = {}
            
        if no not in self.charge_controllers[entry_id]:
            self.charge_controllers[entry_id][no] = {}
            
        try:
            self.charge_controllers[entry_id][no].update({
                'solar_current': float(values[3]),
                'solar_voltage': float(values[4]),
                'battery_voltage': float(values[5]),
                'solar_power': float(values[6]),
                'charge_mode': values[7],
            })
        except (ValueError, IndexError) as e:
            _LOGGER.error("Error processing charge controller data: %s", str(e))

    def get_aggregated_value(self, sensor_type: str) -> float:
        """Get aggregated value across all devices."""
        total = 0.0
        
        # Sum up values from all inverters
        for entry_devices in self.inverters.values():
            for device_data in entry_devices.values():
                if sensor_type in device_data:
                    try:
                        total += float(device_data[sensor_type])
                    except (ValueError, TypeError):
                        pass
                        
        # Sum up values from all charge controllers
        for entry_devices in self.charge_controllers.values():
            for device_data in entry_devices.values():
                if sensor_type in device_data:
                    try:
                        total += float(device_data[sensor_type])
                    except (ValueError, TypeError):
                        pass
                        
        return total

    def has_aggregated_value(self, sensor_type: str) -> bool:
        """Check if we have data for the given sensor type."""
        # Check inverters
        for entry_devices in self.inverters.values():
            for device_data in entry_devices.values():
                if sensor_type in device_data:
                    return True
                    
        # Check charge controllers
        for entry_devices in self.charge_controllers.values():
            for device_data in entry_devices.values():
                if sensor_type in device_data:
                    return True
                    
        return False
