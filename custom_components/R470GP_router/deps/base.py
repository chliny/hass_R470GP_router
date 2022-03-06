""" wrap class for router requests """

import logging
from aiohttp import (
    ClientSession, ClientConnectorError)

_LOGGER = logging.getLogger(__name__)

class BaseRouter():
    """router requests"""
    def __init__(self, session:ClientSession, host:str):
        self.session = session
        self.host = host

    async def _post(self, url:str, data:dict, header:dict[str,str]) -> dict:
        send_header = {
            "Host": self.host,
            "Content-Type": "application/json",
        }
        if header:
            send_header.update(header)
        try:
            ret = await self.session.post(url, json=data, headers=header)
            if not ret.ok:
                _LOGGER.error("request %s faield %s", url, ret.text)
                return {}
        except ClientConnectorError as err:
            _LOGGER.error(err)
            return {}
        return await ret.json()
