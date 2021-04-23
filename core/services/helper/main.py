#!/usr/bin/env python3

import http
import urllib
from dataclasses import dataclass
from typing import List
from urllib.request import urlopen

import bottle
import psutil
from bs4 import BeautifulSoup

PORT = 80
DOCS_CANDIDATE_URLS = ["/v1.0/ui/", "/docs"]


@dataclass
class ServiceInfo:
    valid: bool
    title: str
    ui: str
    port: int

    def as_html(self) -> str:
        port_html = f"""
        <a href="#" onclick="javascript:event.target.port={self.port}">{self.port}:</a>{self.title}
        """
        swagger_html = f"""
        <a href="#" onclick="window.location.href = window.location.origin + ':' + {self.port} + '{self.ui}'">Open Api/Docs</a>
        """
        if self.ui:
            return port_html + swagger_html
        return port_html


class Helper:
    @staticmethod
    def detect_service(port: int) -> ServiceInfo:
        info = ServiceInfo(valid=False, title="Unknown", ui="", port=port)

        try:
            response = urlopen(f"http://127.0.0.1:{port}/", timeout=0.2)
            info.valid = True
            soup = BeautifulSoup(response.read(), features="html.parser")
            title_element = soup.find("title")
            info.title = title_element.text if title_element else "Unknown"
        except urllib.error.HTTPError as error:
            if error.code == http.HTTPStatus.NOT_FOUND:
                info.valid = True
        except Exception as error:
            info.valid = False

        if not info.valid:
            return info

        for ui_path in DOCS_CANDIDATE_URLS:
            try:
                urlopen(f"http://127.0.0.1:{port}{ui_path}", timeout=0.2)
                info.ui = ui_path
                break
            except Exception as error:
                pass  # any error here only means there's no ui available
        return info

    @staticmethod
    def scan_ports() -> List[ServiceInfo]:
        # Filter for TCP ports that are listen and can be accessed by external users (server in 0.0.0.0)
        connections = iter(psutil.net_connections("tcp"))
        connections = filter(lambda connection: connection.status == psutil.CONN_LISTEN, connections)
        connections = filter(lambda connection: connection.laddr.ip == "0.0.0.0", connections)

        # And check if there is a webpage available that is not us
        ports = iter([connection.laddr.port for connection in connections])
        ports = filter(lambda port: port != PORT, ports)
        services = map(Helper.detect_service, ports)
        valid_services = filter(lambda service: service.valid, services)
        return list(valid_services)


if __name__ == "__main__":

    @bottle.route("/")
    def home() -> str:
        services = Helper.scan_ports()
        return r"<br>".join([service.as_html() for service in services])

    bottle.run(host="0.0.0.0", port=PORT)
