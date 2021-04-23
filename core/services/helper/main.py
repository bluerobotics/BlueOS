#!/usr/bin/env python3

import http
import urllib
from typing import List
from urllib.request import urlopen

import bottle
import psutil

PORT = 80


class Helper:
    @staticmethod
    def check_webpage(port: int) -> bool:
        try:
            urlopen(f"http://0.0.0.0:{port}/", timeout=0.2)
        except urllib.error.HTTPError as error:
            if error.code == http.HTTPStatus.NOT_FOUND:
                return True
            return False
        except Exception as error:
            return False
        else:
            return True

    @staticmethod
    def get_webpage_ports() -> List[int]:
        # Filter for TCP ports that are listen and can be accessed by external users (server in 0.0.0.0)
        connections = iter(psutil.net_connections("tcp"))
        connections = filter(lambda connection: connection.status == psutil.CONN_LISTEN, connections)
        connections = filter(lambda connection: connection.laddr.ip == "0.0.0.0", connections)

        # And check if there is a webpage available that is not us
        ports = iter([connection.laddr.port for connection in connections])
        ports = filter(lambda port: port != PORT, ports)
        ports = filter(Helper.check_webpage, ports)

        return list(ports)


if __name__ == "__main__":

    @bottle.route("/")
    def home() -> str:
        ports = Helper.get_webpage_ports()
        return r"<br>".join([f'<a href="/" onclick="javascript:event.target.port={port}">{port}</a>' for port in ports])

    bottle.run(host="0.0.0.0", port=PORT)
