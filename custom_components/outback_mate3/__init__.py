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
    
    mate3 = OutbackMate3(hass, entry.data[CONF_PORT])
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

    def __init__(self, hass: HomeAssistant, port: int):
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
        self.device_counts: Dict[str, Dict[int, int]] = {}  # IP -> {device_type -> count}
        self.charge_controllers: Dict[str, Dict[int, dict]] = {}  # IP -> {device_id -> data}
        self.inverters: Dict[str, Dict[int, dict]] = {}  # IP -> {device_id -> data}
        self.discovered_devices: Set[str] = set()  # Set of "ip_type_id" strings
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
            _LOGGER.debug("Closed UDP socket")

    async def _listen(self):
        """Listen for UDP packets from MATE3."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(('0.0.0.0', self.port))
        self._socket.setblocking(False)

        _LOGGER.info('Listening for MATE3 streaming metrics on UDP port %d', self.port)

        while self._running:
            try:
                data, addr = await self.hass.loop.sock_recvfrom(self._socket, 4096)
                if data:
                    remote_ip = addr[0]
                    _LOGGER.debug("Received UDP data from %s: %s", remote_ip, data.decode('utf-8'))
                    self._process_data(data, remote_ip)
                    self.async_set_updated_data(None)
                    _LOGGER.debug("Current devices for IP %s - Inverters: %s, Charge Controllers: %s", 
                                remote_ip, 
                                list(self.inverters.get(remote_ip, {}).keys()), 
                                list(self.charge_controllers.get(remote_ip, {}).keys()))
            except Exception as e:
                _LOGGER.error("Error receiving data: %s", str(e))
                await asyncio.sleep(1)

    def _process_data(self, data, remote_ip):
        """Process received data."""
        try:
            metrics = data.decode('utf-8')
            header, *devices = re.split(']<|><|>', metrics)
            devices = list(filter(lambda x: x.startswith('0'), devices))

            _LOGGER.debug("Processing %d devices from IP %s", len(devices), remote_ip)
            if remote_ip not in self.device_counts:
                self.device_counts[remote_ip] = {}
            self.device_counts[remote_ip].clear()
            
            for device in devices:
                self._process_device(device, remote_ip)
        except Exception as e:
            _LOGGER.error("Error processing data: %s", str(e))

    def _process_device(self, device, remote_ip):
        """Process individual device data."""
        values = list(device.split(","))
        device_type = int(values[1])
        no = self.device_counts[remote_ip].get(device_type, 0) + 1
        self.device_counts[remote_ip][device_type] = no

        device_key = f"{remote_ip}_{device_type}_{no}"
        is_new_device = device_key not in self.discovered_devices

        _LOGGER.debug("Processing device type %d, number %d from IP %s", device_type, no, remote_ip)

        if device_type == 6:  # Inverter
            if remote_ip not in self.inverters:
                self.inverters[remote_ip] = {}
            self._process_inverter(no, values, remote_ip)
        elif device_type == 3:  # Charge Controller
            if remote_ip not in self.charge_controllers:
                self.charge_controllers[remote_ip] = {}
            self._process_charge_controller(no, values, remote_ip)
        else:
            _LOGGER.warning("Unknown device type: %s", device_type)
            return

        if is_new_device:
            self.discovered_devices.add(device_key)
            if self._add_entities_callback:
                from .sensor import create_device_entities
                entities = create_device_entities(self, remote_ip, device_type, no)
                self.hass.async_create_task(self._add_entities_callback(entities))

    def _process_inverter(self, no, values, remote_ip):
        """Process inverter data."""
        if no not in self.inverters[remote_ip]:
            self.inverters[remote_ip][no] = {}
            _LOGGER.debug("Created new inverter with ID %d for IP %s", no, remote_ip)

        inv = self.inverters[remote_ip][no]

        # L1 values
        l1_inverter_current = float(values[2])
        l1_charger_current = float(values[3])
        l1_buy_current = float(values[4])
        l1_sell_current = float(values[5])
        l1_ac_input_voltage = float(values[6])
        l1_ac_output_voltage = float(values[8])

        # L2 values
        l2_inverter_current = float(values[2 + 7])
        l2_charger_current = float(values[3 + 7])
        l2_buy_current = float(values[4 + 7])
        l2_sell_current = float(values[5 + 7])
        l2_ac_input_voltage = float(values[6 + 7])
        l2_ac_output_voltage = float(values[8 + 7])

        # Store raw values for aggregation
        inv['inverter_current'] = l1_inverter_current + l2_inverter_current
        inv['charger_current'] = l1_charger_current + l2_charger_current
        
        # Combine buy/sell into grid current (buy is positive, sell is negative)
        total_buy = l1_buy_current + l2_buy_current
        total_sell = l1_sell_current + l2_sell_current
        inv['grid_current'] = total_buy if total_buy > 0 else -total_sell
        
        # Average voltages (they should be the same for both legs)
        inv['grid_voltage'] = (l1_ac_input_voltage + l2_ac_input_voltage) / 2
        inv['output_voltage'] = (l1_ac_output_voltage + l2_ac_output_voltage) / 2

        # Calculate power values
        inv['inverter_power'] = inv['inverter_current'] * inv['output_voltage']
        inv['charger_power'] = inv['charger_current'] * inv['grid_voltage']
        inv['grid_power'] = inv['grid_current'] * inv['grid_voltage']

        # Update energy counters (kWh)
        time_delta = 5/3600  # 5 seconds in hours
        if 'grid_energy' not in inv:
            inv['grid_energy'] = 0
            inv['inverter_energy'] = 0
            inv['charger_energy'] = 0
            
        inv['grid_energy'] += abs(inv['grid_power']) * time_delta / 1000  # Convert from Wh to kWh
        inv['inverter_energy'] += abs(inv['inverter_power']) * time_delta / 1000
        inv['charger_energy'] += abs(inv['charger_power']) * time_delta / 1000

        # Process modes
        inverter_mode = int(values[16])
        inv['inverter_mode'] = {
            0: 'off',
            1: 'search',
            2: 'inverting',
            3: 'charging',
            4: 'silent',
            5: 'floating',
            6: 'equalizing',
            7: 'charger-off',
            8: 'charger-off',
            9: 'selling',
            10: 'pass-through',
            11: 'slave-on',
            12: 'slave-off',
            14: 'offsetting',
            90: 'inverter-error',
            91: 'ags-error',
            92: 'comm-error',
        }.get(inverter_mode, 'unknown')

        ac_mode = int(values[18])
        inv['ac_mode'] = {
            0: 'no-ac',
            1: 'ac-drop',
            2: 'ac-use',
        }.get(ac_mode, 'unknown')

        _LOGGER.debug("Updated inverter %d values for IP %s", no, remote_ip)

    def _process_charge_controller(self, no, values, remote_ip):
        """Process charge controller data."""
        if no not in self.charge_controllers[remote_ip]:
            self.charge_controllers[remote_ip][no] = {}
            _LOGGER.debug("Created new charge controller with ID %d for IP %s", no, remote_ip)
            
        cc = self.charge_controllers[remote_ip][no]
        
        cc['solar_current'] = float(values[4])
        cc['solar_voltage'] = float(values[5])
        cc['battery_voltage'] = float(values[6])  # Already in proper units
        cc['solar_power'] = cc['solar_voltage'] * cc['solar_current']

        # Update energy counter (kWh)
        time_delta = 5/3600  # 5 seconds in hours
        if 'solar_energy' not in cc:
            cc['solar_energy'] = 0
        cc['solar_energy'] += (cc['solar_power'] * time_delta) / 1000  # Convert from Wh to kWh

        charge_mode = int(values[8])
        cc['charge_mode'] = {
            0: 'silent',
            1: 'float',
            2: 'bulk',
            3: 'absorb',
            4: 'eq',
        }.get(charge_mode, 'unknown')

        _LOGGER.debug("Updated charge controller %d values for IP %s", no, remote_ip)

    def get_aggregated_value(self, sensor_type: str) -> float | str | None:
        """Get aggregated value across all devices."""
        value = None

        # Handle inverter values
        if sensor_type in ['inverter_current', 'charger_current', 'grid_current',
                          'inverter_power', 'charger_power', 'grid_power',
                          'inverter_energy', 'charger_energy', 'grid_energy']:
            value = 0
            for ip in self.inverters:
                for inv in self.inverters[ip].values():
                    if sensor_type in inv:
                        value += inv[sensor_type]

        # Handle charge controller values
        elif sensor_type in ['solar_current', 'solar_power', 'solar_energy']:
            value = 0
            for ip in self.charge_controllers:
                for cc in self.charge_controllers[ip].values():
                    if sensor_type in cc:
                        value += cc[sensor_type]

        # Handle voltage values (use average)
        elif sensor_type in ['grid_voltage', 'output_voltage', 'solar_voltage', 'battery_voltage']:
            count = 0
            total = 0
            
            # Check inverters
            for ip in self.inverters:
                for inv in self.inverters[ip].values():
                    if sensor_type in inv:
                        total += inv[sensor_type]
                        count += 1
                        
            # Check charge controllers
            for ip in self.charge_controllers:
                for cc in self.charge_controllers[ip].values():
                    if sensor_type in cc:
                        total += cc[sensor_type]
                        count += 1
                        
            if count > 0:
                value = total / count

        # Handle system mode
        elif sensor_type == 'system_mode':
            # Use the first inverter's mode as the system mode
            for ip in self.inverters:
                for inv in self.inverters[ip].values():
                    if 'inverter_mode' in inv:
                        return inv['inverter_mode']
            value = 'unknown'

        return value

    def has_aggregated_value(self, sensor_type: str) -> bool:
        """Check if we have data for the given sensor type."""
        return self.get_aggregated_value(sensor_type) is not None
