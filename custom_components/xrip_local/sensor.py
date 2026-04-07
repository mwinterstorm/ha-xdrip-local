import logging
import aiohttp
import hashlib
from datetime import timedelta
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.const import CONF_IP_ADDRESS, CONF_API_SECRET, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Default polling to 5 minutes if not specified
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_API_SECRET): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
})

async self.async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    ip_address = config.get(CONF_IP_ADDRESS)
    api_secret = config.get(CONF_API_SECRET)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    
    async_add_entities([XDripSensor(ip_address, api_secret, scan_interval)], True)

class XDripSensor(SensorEntity):
    def __init__(self, ip_address, api_secret, scan_interval):
        self._ip_address = ip_address
        self._api_secret = api_secret
        self._attr_update_interval = scan_interval
        self._state = None
        self._attributes = {}
        self._attr_name = "MacDrip Glucose"
        self._attr_native_unit_of_measurement = "mmol/L"
        self._attr_icon = "mdi:water"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_update(self):
        url = f"http://{self._ip_address}:17580/pebble?count=1"
        
        # SHA-1 Hash of the API Secret
        hashed_secret = hashlib.sha1(self._api_secret.encode('utf-8')).hexdigest()
        headers = {"api-secret": hashed_secret}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "bgs" in data and len(data["bgs"]) > 0:
                            bg_data = data["bgs"][0]
                            mgdl = float(bg_data.get("sgv", 0))
                            self._state = round(mgdl / 18.018, 1)
                            
                            self._attributes = {
                                "direction": bg_data.get("direction", ""),
                                "iob": bg_data.get("iob", "0.0"),
                                "cob": bg_data.get("cob", "0"),
                                "last_check": bg_data.get("datetime", "")
                            }
                        else:
                            self._state = "No Data"
                    elif response.status == 401:
                        _LOGGER.error("xDrip Auth Error: Check your API Secret")
                        self._state = "Auth Error"
                    else:
                        self._state = "Error"
        except Exception as e:
            _LOGGER.debug(f"Connection failed: {e}")
            self._state = "Unavailable"