"""The Outback MATE3 integration."""
import asyncio
import logging
import socket
import re
from datetime import datetime

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_PORT,
    Platform,
)

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

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Outback MATE3 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    mate3 = OutbackMate3(hass, entry.data[CONF_PORT])
    hass.data[DOMAIN][entry.entry_id] = mate3

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    mate3.start_listening()
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        mate3 = hass.data[DOMAIN].pop(entry.entry_id)
        mate3.stop_listening()

    return unload_ok

class OutbackMate3:
    """Main class for Outback MATE3 integration."""

    def __init__(self, hass: HomeAssistant, port: int):
        """Initialize the MATE3 integration."""
        self.hass = hass
        self.port = port
        self._socket = None
        self._running = False
        self.device_counts = {}
        self.charge_controllers = {}
        self.inverters = {}

    def start_listening(self):
        """Start listening for UDP packets."""
        self._running = True
        asyncio.create_task(self._listen())

    def stop_listening(self):
        """Stop listening for UDP packets."""
        self._running = False
        if self._socket:
            self._socket.close()

    async def _listen(self):
        """Listen for UDP packets from MATE3."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(('0.0.0.0', self.port))
        self._socket.setblocking(False)

        _LOGGER.info('Listening for MATE3 streaming metrics on UDP port %d', self.port)

        while self._running:
            try:
                data = await self.hass.loop.sock_recv(self._socket, 4096)
                if data:
                    self._process_data(data)
            except Exception as e:
                _LOGGER.error("Error receiving data: %s", str(e))
                await asyncio.sleep(1)

    def _process_data(self, data):
        """Process received data."""
        try:
            metrics = str(data)
            header, *devices = re.split(']<|><|>', metrics)
            devices = filter(lambda x: x.startswith('0'), devices)

            self.device_counts = {}
            for device in devices:
                self._process_device(device)
        except Exception as e:
            _LOGGER.error("Error processing data: %s", str(e))

    def _process_device(self, device):
        """Process individual device data."""
        values = list(device.split(","))
        device_type = int(values[1])
        no = self.device_counts.get(device_type, 0) + 1
        self.device_counts[device_type] = no

        if device_type == 6:  # Inverter
            self._process_inverter(no, values)
        elif device_type == 3:  # Charge Controller
            self._process_charge_controller(no, values)
        else:
            _LOGGER.warning("Unknown device type: %s", device_type)

    def _process_inverter(self, no, values):
        """Process inverter data."""
        if no not in self.inverters:
            self.inverters[no] = {}

        inv = self.inverters[no]
        misc = int(values[20])
        
        is_240v = bool(misc & (1 << 7))
        ac_factor = 2 if is_240v else 2

        is_grid = bool(misc & (1 << 6))
        inv['ac_source'] = "grid" if is_grid else "generator"

        # L1 values
        inv['l1_inverter_current'] = float(values[2])
        inv['l1_charger_current'] = float(values[3])
        inv['l1_buy_current'] = float(values[4])
        inv['l1_sell_current'] = float(values[5])
        inv['l1_ac_input_voltage'] = float(values[6]) * ac_factor
        inv['l1_ac_output_voltage'] = float(values[8]) * ac_factor
        
        # L2 values
        inv['l2_inverter_current'] = float(values[2 + 7])
        inv['l2_charger_current'] = float(values[3 + 7])
        inv['l2_buy_current'] = float(values[4 + 7])
        inv['l2_sell_current'] = float(values[5 + 7])
        inv['l2_ac_input_voltage'] = float(values[6 + 7]) * ac_factor
        inv['l2_ac_output_voltage'] = float(values[8 + 7]) * ac_factor

        output_power = (float(values[2]) + float(values[2 + 7])) * 110.0 
        inv['output_power'] = int(output_power)

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

    def _process_charge_controller(self, no, values):
        """Process charge controller data."""
        if no not in self.charge_controllers:
            self.charge_controllers[no] = {}
            
        cc = self.charge_controllers[no]
        
        pv_current = int(values[4])
        pv_voltage = int(values[5])
        cc['pv_current'] = pv_current
        cc['pv_voltage'] = pv_voltage
        cc['pv_power'] = pv_voltage * pv_current

        cc_amps = float(values[3]) + (float(values[7]) / 10)
        cc['output_current'] = cc_amps

        charger_mode = int(values[10])
        cc['charger_mode'] = {
            0: 'silent',
            1: 'float',
            2: 'bulk',
            3: 'absorb',
            4: 'equalize',
        }.get(charger_mode, 'unknown')

        cc['battery_voltage'] = float(values[11])/10
