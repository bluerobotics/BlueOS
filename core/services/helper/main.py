#!/usr/bin/env python3

import http
import json
import urllib
from pathlib import Path
from typing import Any, List
from urllib.request import urlopen

import psutil
import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from pydantic import BaseModel
from starlette.responses import Response as StarletteResponse

PORT = 80
DOCS_CANDIDATE_URLS = ["/v1.0/ui/", "/docs"]

HTML_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "html")


class PrettyJSONResponse(StarletteResponse):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(", ", ": "),
        ).encode(self.charset)


class ServiceInfo(BaseModel):
    valid: bool
    title: str
    documentation_url: str
    port: int


class Helper:
    @staticmethod
    def detect_service(port: int) -> ServiceInfo:
        info = ServiceInfo(valid=False, title="Unknown", documentation_url="", port=port)

        try:
            with urlopen(f"http://127.0.0.1:{port}/", timeout=0.2) as response:
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

        for documentation_path in DOCS_CANDIDATE_URLS:
            try:
                urlopen(f"http://127.0.0.1:{port}{documentation_path}", timeout=0.2)
                info.documentation_url = documentation_path
                break
            except Exception as error:
                pass  # any error here only means there's no documentation ui available
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


fast_api_app = FastAPI(
    title="Helper API",
    description="Everybody's helper to find web services that are running in companion.",
    default_response_class=PrettyJSONResponse,
)


@fast_api_app.get(
    "/web_services",
    response_model=List[ServiceInfo],
    summary="Retrieve web services found.",
)
@version(1, 0)
def web_services() -> Any:
    """REST API endpoint to retrieve web services running."""
    return Helper.scan_ports()


app = VersionedFastAPI(
    fast_api_app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)

app.mount("/", StaticFiles(directory=str(HTML_FOLDER), html=True))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
