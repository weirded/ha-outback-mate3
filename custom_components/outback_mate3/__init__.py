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

_LOGGER = logging.getLogger(__name__)

DOMAIN = "outback_mate3"
DEFAULT_PORT = 57027

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

MAC_PATTERN = re.compile(r'\[([0-9A-F]{6})-([0-9A-F]{6})\]')

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
        self.device_counts: Dict[str, Dict[int, int]] = {}  # MAC -> {device_type -> count}
        self.charge_controllers: Dict[str, Dict[int, dict]] = {}  # MAC -> {device_id -> data}
        self.inverters: Dict[str, Dict[int, dict]] = {}  # MAC -> {device_id -> data}
        self.discovered_devices: Set[str] = set()  # Set of "mac_type_id" strings
        self.combined_metrics: Dict[str, dict] = {}  # MAC -> combined metrics
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
            
            # Extract MAC address from the start of the data line
            mac_match = MAC_PATTERN.match(metrics)
            if not mac_match:
                _LOGGER.debug("Could not find MAC address in data: %s", metrics)
                return
            
            mac_address = mac_match.group(1) + mac_match.group(2)
            
            header, *devices = re.split(']<|><|>', metrics)
            devices = list(filter(lambda x: x.startswith('0'), devices))

            _LOGGER.debug("Processing %d devices from IP %s", len(devices), remote_ip)
            if mac_address not in self.device_counts:
                self.device_counts[mac_address] = {}
            self.device_counts[mac_address].clear()
            
            # Initialize combined metrics for this MAC
            if mac_address not in self.combined_metrics:
                self.combined_metrics[mac_address] = {}
            
            combined = {
                'total_grid_power': 0.0,
                'total_grid_current': 0.0,
                'total_charger_power': 0.0,
                'total_charger_current': 0.0,
                'total_inverter_power': 0.0,
                'total_inverter_current': 0.0,
                'total_cc_output_current': 0.0,
                'total_cc_output_power': 0.0,
            }
            
            # Process each device and accumulate totals
            for device in devices:
                self._process_device(device, mac_address)
            
            # Calculate combined metrics for inverters
            for inv_data in self.inverters.get(mac_address, {}).values():
                combined['total_grid_power'] += float(inv_data.get('grid_power', 0))
                combined['total_grid_current'] += float(inv_data.get('grid_current', 0))
                combined['total_charger_power'] += float(inv_data.get('charger_power', 0))
                combined['total_charger_current'] += float(inv_data.get('charger_current', 0))
                combined['total_inverter_power'] += float(inv_data.get('inverter_power', 0))
                combined['total_inverter_current'] += float(inv_data.get('total_inverter_current', 0))
            
            # Calculate combined metrics for charge controllers
            for cc_data in self.charge_controllers.get(mac_address, {}).values():
                output_current = float(cc_data.get('output_current', 0))
                battery_voltage = float(cc_data.get('battery_voltage', 0))
                output_power = output_current * battery_voltage
                
                # Store the calculated output power
                cc_data['output_power'] = output_power
                
                combined['total_cc_output_current'] += output_current
                combined['total_cc_output_power'] += output_power
            
            # Update the combined metrics
            self.combined_metrics[mac_address] = combined
            
        except Exception as e:
            _LOGGER.error("Error processing data: %s", str(e))

    def _process_device(self, device, mac_address):
        """Process individual device data."""
        values = list(device.split(","))
        device_type = int(values[1])
        no = self.device_counts[mac_address].get(device_type, 0) + 1
        self.device_counts[mac_address][device_type] = no

        device_key = f"{mac_address}_{device_type}_{no}"
        is_new_device = device_key not in self.discovered_devices

        _LOGGER.debug("Processing device type %d, number %d from MAC %s", device_type, no, mac_address)

        if device_type == 6:  # Inverter
            if mac_address not in self.inverters:
                self.inverters[mac_address] = {}
            self._process_inverter(no, values, mac_address)
        elif device_type == 3:  # Charge Controller
            if mac_address not in self.charge_controllers:
                self.charge_controllers[mac_address] = {}
            self._process_charge_controller(no, values, mac_address)
        else:
            _LOGGER.warning("Unknown device type: %s", device_type)
            return

        if is_new_device:
            self.discovered_devices.add(device_key)
            if self._add_entities_callback:
                from .sensor import create_device_entities
                entities = create_device_entities(self, mac_address, device_type, no)
                self.hass.async_create_task(self._add_entities_callback(entities))

    def _process_inverter(self, no, values, mac_address):
        """Process inverter data."""
        if no not in self.inverters[mac_address]:
            self.inverters[mac_address][no] = {
                'inverter_mode': 'unknown',  # Initialize mode sensors
                'ac_mode': 'unknown'
            }
            _LOGGER.debug("Created new inverter with ID %d for MAC %s", no, mac_address)

        inv = self.inverters[mac_address][no]

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

        # Combined measurements
        inv['total_inverter_current'] = l1_inverter_current + l2_inverter_current
        inv['total_charger_current'] = l1_charger_current + l2_charger_current
        
        # Combine buy/sell into grid current (buy is positive, sell is negative)
        total_buy = l1_buy_current + l2_buy_current
        total_sell = l1_sell_current + l2_sell_current
        inv['grid_current'] = total_buy if total_buy > 0 else -total_sell
        
        # Average voltages (they should be the same for both legs)
        inv['ac_input_voltage'] = (l1_ac_input_voltage + l2_ac_input_voltage) / 2
        inv['ac_output_voltage'] = (l1_ac_output_voltage + l2_ac_output_voltage) / 2

        # Calculate power values
        inv['inverter_power'] = (l1_inverter_current + l2_inverter_current) * ((l1_ac_output_voltage + l2_ac_output_voltage) / 2)
        inv['charger_power'] = (l1_charger_current + l2_charger_current) * ((l1_ac_input_voltage + l2_ac_input_voltage) / 2)
        
        # Grid power (buy is positive, sell is negative)
        grid_voltage = (l1_ac_input_voltage + l2_ac_input_voltage) / 2  # Use input voltage for both buy and sell
        inv['grid_power'] = inv['grid_current'] * grid_voltage

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

        _LOGGER.debug("Updated inverter %d values for MAC %s", no, mac_address)

    def _process_charge_controller(self, no, values, mac_address):
        """Process charge controller data."""
        if no not in self.charge_controllers[mac_address]:
            self.charge_controllers[mac_address][no] = {
                'charge_mode': 'unknown'  # Initialize mode sensor
            }
            _LOGGER.debug("Created new charge controller with ID %d for MAC %s", no, mac_address)
            
        cc = self.charge_controllers[mac_address][no]
        
        pv_current = float(values[4])
        pv_voltage = float(values[5])
        battery_voltage = float(values[6])  # Already in proper units
        cc['pv_current'] = pv_current
        cc['pv_voltage'] = pv_voltage
        cc['pv_power'] = pv_voltage * pv_current

        cc['output_current'] = float(values[3]) + (float(values[7]) / 10)
        cc['battery_voltage'] = battery_voltage

        charge_mode = int(values[8])
        cc['charge_mode'] = {
            0: 'silent',
            1: 'float',
            2: 'bulk',
            3: 'absorb',
            4: 'eq',
        }.get(charge_mode, 'unknown')

        _LOGGER.debug("Updated charge controller %d values for MAC %s", no, mac_address)
