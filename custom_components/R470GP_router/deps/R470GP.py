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
            return ret_infos
        host_infos = results.get("host_management", {}).get("host_info", [])
        for host_info_dict in host_infos:
            for _, host_info in host_info_dict.items():
                if self.host_is_online(host_info):
                    _LOGGER.debug(host_info)
                    mac = host_info.get("mac", "")
                    host_infos[mac] = host_info
        return ret_infos

    def host_is_online(self, host_info:dict) -> bool:
        """ check whether the client is online """
        state = host_info.get("state", "")
        if state == "online":
            return True

        connect_date = unquote(host_info.get("connect_date", ""))
        if not connect_date:
            return False
        connect_date_obj = datetime.datetime.strptime(connect_date,
                "%y/%m/%d")
        nowtime = datetime.datetime.now()

        #客户端下线超过7天才当成下线，避免偶尔断线被下线删除
        if nowtime - connect_date_obj > datetime.timedelta(days=7):
            return False
        return True
