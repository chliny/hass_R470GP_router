"""Support for TP-Link R470GP routers."""

import logging
import voluptuous as vol

from datetime import timedelta
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, DeviceScanner, CONF_SCAN_INTERVAL,
    SOURCE_TYPE_ROUTER)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_time_interval

from .deps.R470GP import R470GPRouter

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = 30

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
})

async def async_setup_scanner(hass, config, async_see, discover_info=None):
    """Set up the device_tracker."""
    scanner = TplinkDeviceScanner(hass, config, async_see)
    return await scanner.async_init()

class TplinkDeviceScanner(DeviceScanner):
    """ rewrite device scanners """

    def __init__(self, hass, config, async_see):
        session = aiohttp_client.async_create_clientsession(hass,
                auto_cleanup=False)
        host = config[CONF_HOST]
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]
        self.router = R470GPRouter(session, host, username, password)
        interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self.scan_interval = timedelta(seconds=interval)
        self._hass = hass
        self._async_see = async_see
        self.client_infos = {}

    async def async_init(self):
        await self.async_update()
        async_track_time_interval(self._hass,
                                  self.async_update,
                                  self.scan_interval)
    async def async_update(self, now=None) -> None:
        """Ensure the information from the router is up to date """
        new_client_infos = await self.router.get_host_info()
        if not new_client_infos:
            _LOGGER.error("get client infos failed")
            return
        self.client_infos = new_client_infos
        for mac, client in self.client_infos.items():
            dev_id = mac.replace("-", "")
            hostname = client.get("hostname", "")
            await self._async_see(mac=mac, dev_id=dev_id, host_name=hostname,
                    source_type=SOURCE_TYPE_ROUTER, attributes=self.get_extra_attributes(mac))

    async def async_scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        await self.async_update()
        devices = list(self.client_infos.keys())
        return devices

    def get_extra_attributes(self, device:str) -> dict:
        """ other attributes for client """
        newinfo = {}
        results = self.client_infos.get(device, {})
        if not results:
            return newinfo
        return results
    """
        infomap = {"mac": "mac", "host_name": "hostname", "ip": "ip"}
        for newkey, oldkey in infomap.items():
            newinfo[newkey] = results.get(oldkey, "")
        newinfo["dev_id"] = results.get("mac", "").replace(":", "")
        return newinfo
    """

    def get_device_name(self, device):
        """Get firmware doesn't save the name of the wireless device."""
        return self.client_infos.get(device, {}).get("hostname", "")
