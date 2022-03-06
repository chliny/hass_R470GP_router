""" TPLink R470GP router requests """
import logging
import datetime

from aiohttp import ClientSession
from urllib.parse import unquote

from .base import BaseRouter

_LOGGER = logging.getLogger(__name__)

class R470GPRouter(BaseRouter):
    """ request router infos """
    def __init__(self, session:ClientSession, host:str, username:str,
            password:str):
        self.stok = ""
        self.username = username
        self.password = password
        super().__init__(session, host)
        self.static_macs = {}

    async def get_token(self) -> bool:
        """ login router to get stok token """
        _LOGGER.info("Retrieving auth tokens...")
        url = f"http://{self.host}"
        header = {
            "Referer": f"http://{self.host}/login.htm",
        }
        data = {"method":"do","login":{
            "username": self.username,
            "password": self.password,
        }}
        results = await self._post(url, data, header)
        if results:
            self.stok = results.get("stok", "")
            if self.stok:
                _LOGGER.info("get stok from %s success", self.host)
                await self.get_static_macs()
                return True
        _LOGGER.error("login %s failed", self.host)
        return False

    async def get_host_info(self) -> dict:
        """ get router client infos """
        _LOGGER.info("Loading clients...")
        ret_infos = {}
        if not self.stok and not await self.get_token():
            return ret_infos

        url = f"http://{self.host}/stok={self.stok}/ds"
        data = {"method":"get","host_management":{"table":"host_info"}}
        results = await self._post(url, data, header={})
        if not results:
            _LOGGER.error("get host_info from %s failed", url)
            self.stok = ""
            return ret_infos
        host_infos = results.get("host_management", {}).get("host_info", [])
        for host_info_dict in host_infos:
            for _, host_info in host_info_dict.items():
                host_info = self._filter(host_info)
                _LOGGER.debug(host_info)
                mac = host_info.get("mac", "")
                ret_infos[mac] = host_info

        if not self.static_macs:
            await self.get_static_macs()

        for mac, static_info in self.static_macs.items():
            host_info = ret_infos.get(mac, {})
            if host_info:
                _LOGGER.debug("replace %s to %s", host_info["hostname"],
                        static_info["note"])
                host_info["hostname"] = static_info.get("note", "")
                ret_infos[mac] = host_info
            else:
                ret_infos[mac] = self.static_to_onlineinfo(static_info)
        return ret_infos

    def static_to_onlineinfo(self, static_info:dict) -> dict:
        replace_map = {"ip":"ip", "hostname":"note", "mac":"mac"}
        #'mac': '68-A4-0E-18-BB-01', 'type': 'wired', 'host_save': 'off', 'ip':'192.168.0.127', 'state': 'online', 'is_cur_host': False, 'hostname':'68A40E18BB01', 'down_limit': '0', 'up_limit': '0', 'interface':'br-lan', 'is_deprecate': False
        new_host_info = {
            "state": "offline",
            "type": "wired",
            "host_save": "on",
            "is_cur_host": False,
            "down_limit": 0,
            "up_limit": 0,
            "interface": "br-lan",
            "is_deprecate": False
        }
        for key, replace_key in replace_map.items():
            new_host_info[key] = static_info.get(replace_key, "")
        _LOGGER.debug("add static:%s", new_host_info)
        return new_host_info

    def _filter(self, host_info:dict) -> dict:
        host_info = self._unquote(host_info)
        host_info = self._unique_name(host_info)
        host_info["is_deprecate"] = self.host_is_deprecate(host_info)
        return host_info

    def _unquote(self, host_info:dict) -> dict:
        keys = ["connect_date", "connect_time", "ssid"]
        for key in keys:
            value = host_info.get(key, "")
            if not value:
                continue
            escape_value = unquote(value)
            host_info[key] = escape_value
        return host_info

    def _unique_name(self, host_info:dict) -> dict:
        mac = host_info.get("mac", "")
        if not mac:
            return host_info
        hostname = host_info.get("hostname", "")
        if not hostname or hostname in ["", "---", "anonymous"]:
            newname = mac.replace("-", "")
            host_info["hostname"] = newname
        return host_info


    def host_is_deprecate(self, host_info:dict) -> bool:
        """ check whether the client is online """
        state = host_info.get("state", "")
        if state == "online":
            return False

        connect_date = host_info.get("connect_date", "")
        if not connect_date:
            return True
        connect_date_obj = datetime.datetime.strptime(connect_date,
                "%y/%m/%d")
        nowtime = datetime.datetime.now()

        #客户端下线超过7天才当成下线，避免偶尔断线被下线删除
        if nowtime - connect_date_obj > datetime.timedelta(days=7):
            return True
        return False

    async def get_static_macs(self) -> bool:
        if not self.stok:
            return False

        static_macs = {}
        url = f"http://{self.host}/stok={self.stok}/ds"
        data = {"method":"get",
            "dhcpd":{
            "table":"dhcp_static",
            "para":{"start":0,"end":199}}
        }
        results = await self._post(url, data, header={})
        _LOGGER.debug(results)
        results = results.get("dhcpd", {}).get("dhcp_static", {})
        for dhcp_static in results:
            for _, host in dhcp_static.items():
                mac = host.get("mac", "")
                if not mac:
                    continue
                static_macs[mac] = host

        self.static_macs = static_macs
        _LOGGER.debug(self.static_macs)
        return True
