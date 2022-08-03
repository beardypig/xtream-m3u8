from typing import Optional
from urllib.parse import quote, urlencode

import arrow

import requests

from .connection import Connection
from .util import filter_none_dict


class Client:
    def __init__(self, connection: Connection, user_agent: Optional[str] = None):
        self.connection = connection
        self.user_agent = user_agent

    def get_live_categories(self):
        return self.player_api("get_live_categories")

    def get_live_streams(self):
        return self.player_api("get_live_streams")

    def get_user_info(self):
        return self.player_api(None)

    def live_url(self, channel_id, extension="m3u8"):
        return f"{self.connection.scheme}://{self.connection.host}/live/"\
               f"{quote(self.connection.username)}/{quote(self.connection.password)}/{channel_id}.{extension}"

    def timeshift_url(self, channel_id, shift=1):
        info = self.get_user_info()
        server_now = arrow.get(info['server_info']['timestamp_now'], tzinfo=info['server_info']['timezone'])
        base = f"{self.connection.scheme}://{self.connection.host}/streaming/timeshift.php"
        args = {"duration": "1000",
                "username": self.connection.username,
                "password": self.connection.password,
                "stream": channel_id,
                "start": server_now.shift(hours=-shift).format("YYYY-MM-DD:hh-mm")
                }

        return f"{base}?{urlencode(filter_none_dict(args))}"

    def player_api(self, action):
        base = f"{self.connection.scheme}://{self.connection.host}/player_api.php"
        args = {"action": action,
                "username": self.connection.username,
                "password": self.connection.password}

        url = f"{base}?{urlencode(filter_none_dict(args))}"

        return requests.get(url).json()
