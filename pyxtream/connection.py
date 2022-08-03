from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse

from .util import filter_none_dict


class Connection:
    def __init__(self,
                 server: str,
                 scheme: str = "http",
                 port: Optional[int] = None,
                 username: Optional[str] = None,
                 password: Optional[str] = None):
        self.scheme = scheme
        self.server = server
        self.port = port
        self.username = username
        self.password = password

    @property
    def host(self):
        port = f":{self.port}" if self.port else ""
        return f"{self.server}{port}"

    def __repr__(self):
        args = filter_none_dict({"username": self.username, "password": self.password})
        return f"{self.scheme}://{self.host}?{urlencode(args)}"

    def __str__(self):
        return repr(self)

    @classmethod
    def from_url(cls, url: str):
        o = urlparse(url)
        qs = dict(parse_qsl(o.params))
        return (
            cls(server=o.hostname,
                port=o.port,
                scheme=o.scheme,
                username=qs.get("username"),
                password=qs.get("password")
                )
        )
