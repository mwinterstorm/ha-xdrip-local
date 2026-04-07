import logging
import aiohttp
import hashlib
import asyncio
from datetime import datetime, timedelta, timezone
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.const import CONF_IP_ADDRESS, CONF_API_SECRET
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_time
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "xdrip_local"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_API_SECRET): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    ip_address = config.get(CONF_IP_ADDRESS)
    api_secret = config.get(CONF_API_SECRET)
    
    sensor = XDripSensor(hass, ip_address, api_secret)
    async_add_entities([sensor], True)

class XDripSensor(SensorEntity):
    def __init__(self, hass, ip_address, api_secret):
        self.hass = hass
        self._ip_address = ip_address
        self._api_secret = api_secret
        self._state = None
        self._attributes = {}
        self._attr_name = "MacDrip Glucose"
        self._attr_native_unit_of_measurement = "mmol/L"
        self._attr_icon = "mdi:water"
        self._last_reading_time = 0

    @property
    def should_poll(self):
        # Disable default polling because we use custom tiered backoff
        return False

    async def async_update(self, *_):
        """Fetch data and schedule the next check with tiered backoff."""
        await self._fetch_data()
        
        # Tell Home Assistant to update the UI with the fresh data
        self.async_write_ha_state()
        
        now_ms = datetime.now(timezone.utc).timestamp() * 1000
        age_ms = now_ms - self._last_reading_time
        age_min = age_ms / 60000
        
        # --- TIERED BACKOFF LOGIC ---
        if age_ms < 300000:
            # TIER 1: Fresh (Wait for the next 5-minute window)
            seconds_to_wait = ((300000 - age_ms) / 1000) + 5
            self._attributes["connection_status"] = "Synchronized"
        
        elif age_min < 6:
            # TIER 2A: Hunting (New data is expected any second)
            seconds_to_wait = 5
            self._attributes["connection_status"] = "Synchronized"

        elif age_min < 10:
            # TIER 2B: Hunting (New data still expected)
            seconds_to_wait = 15
            self._attributes["connection_status"] = "Hunting"
            
        elif age_min < 30:
            # TIER 3: Stale 
            seconds_to_wait = 60
            self._attributes["connection_status"] = "Stale (Slow Poll)"
            
        else:
            # TIER 4: Offline (Sensor/Phone likely disconnected)
            seconds_to_wait = 300
            self._attributes["connection_status"] = "Offline (Hibernating)"

        # Safety floor of 5 seconds to prevent infinite loops
        seconds_to_wait = max(5, seconds_to_wait)
        _LOGGER.debug(f"Data age: {age_min:.1f}m. Next poll in {seconds_to_wait}s.")

        next_update = dt_util.now() + timedelta(seconds=seconds_to_wait)
        async_track_point_in_time(self.hass, self.async_update, next_update)

    async def _fetch_data(self):
        url = f"http://{self._ip_address}:17580/pebble?count=1"
        hashed_secret = hashlib.sha1(self._api_secret.encode('utf-8')).hexdigest()
        headers = {"api-secret": hashed_secret}
        
        try:
            # Timeout is 10 seconds. If the phone is off Tailscale, it gracefully fails here
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "bgs" in data and len(data["bgs"]) > 0:
                            bg_data = data["bgs"][0]
                            mgdl = float(bg_data.get("sgv", 0))
                            self._state = round(mgdl / 18.018, 1)
                            self._last_reading_time = bg_data.get("datetime", 0)
                            
                            self._attributes = {
                                "direction": bg_data.get("direction", ""),
                                "iob": bg_data.get("iob", "0.0"),
                                "cob": bg_data.get("cob", "0"),
                                "reading_age_min": round((datetime.now(timezone.utc).timestamp() * 1000 - self._last_reading_time) / 60000, 1)
                            }
                        else:
                            self._state = "No Data"
                    elif response.status == 401:
                        self._state = "Auth Error"
        except Exception as e:
            _LOGGER.debug(f"Connection failed: {e}")
            # Do NOT reset the state to Unavailable here, otherwise the dashboard will flicker to 
            # "Unavailable" every time you lose signal for 2 minutes. Just let it show the old number 
            # until the Tiered Backoff pushes it to Stale/Offline.