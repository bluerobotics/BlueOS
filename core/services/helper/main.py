#!/usr/bin/env python3

import asyncio
import gzip
import http.client
import json
import logging
import re
import socket
import subprocess
from concurrent import futures
from datetime import datetime
from enum import Enum
from functools import cache
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse
from uuid import UUID

import psutil
from bs4 import BeautifulSoup
from commonwealth.utils.apis import GenericErrorHandlingRoute, PrettyJSONResponse
from commonwealth.utils.decorators import temporary_cache
from commonwealth.utils.general import (
    blueos_version,
    local_hardware_identifier,
    local_unique_identifier,
)
from commonwealth.utils.logs import InterceptHandler, init_logger
from fastapi import FastAPI, HTTPException
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from pydantic import BaseModel
from speedtest import Speedtest
from uvicorn import Config, Server

from nginx_parser import parse_nginx_file

SERVICE_NAME = "helper"
SPEED_TEST: Optional[Speedtest] = None

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
try:
    init_logger(SERVICE_NAME)
except Exception as logger_e:
    print(f"Error: unable to set logger path: {logger_e}")

logger.info("Starting Helper")

try:
    SPEED_TEST = Speedtest(secure=True)
except Exception:
    # When starting, the system may not be connected to the internet
    pass


class Website(Enum):
    ArduPilot = {
        "hostname": "firmware.ardupilot.org",
        "path": "/",
        "port": 80,
    }
    AWS = {
        "hostname": "amazon.com",
        "path": "/",
        "port": 80,
    }
    BlueOS = {
        "hostname": "telemetry.blueos.cloud",
        "path": "/ping/?"
        + f"&blueos_id={local_unique_identifier()}"
        + f"&hardware_id={local_hardware_identifier()}"
        + f"&version={blueos_version()}",
        "port": 443,
    }
    Cloudflare = {
        "hostname": "1.1.1.1",
        "path": "/",
        "port": 80,
    }
    GitHub = {
        "hostname": "github.com",
        "path": "/",
        "port": 80,
    }


class WebsiteStatus(BaseModel):
    site: Website
    online: bool
    error: Optional[str] = None


class ServiceMetadata(BaseModel):
    name: str
    description: str
    icon: str
    company: str
    version: str
    webpage: str
    route: Optional[str]
    new_page: Optional[bool]
    extra_query: Optional[str]
    avoid_iframes: Optional[bool]
    api: str
    sanitized_name: Optional[str]
    works_in_relative_paths: Optional[bool]


class ServiceInfo(BaseModel):
    valid: bool
    title: str
    documentation_url: str
    versions: List[str]
    port: int
    path: Optional[str]
    metadata: Optional[ServiceMetadata]

    def __hash__(self) -> int:
        return hash(self.port)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ServiceInfo):
            return self.port == other.port
        return False


class SpeedtestServer(BaseModel):
    url: str
    lat: str
    lon: str
    name: str
    country: str
    cc: str
    sponsor: str
    id: str
    host: str
    d: float
    latency: float


class SpeedtestClient(BaseModel):
    ip: str
    lat: str
    lon: str
    isp: str
    isprating: str
    rating: str
    ispdlavg: str
    ispulavg: str
    loggedin: str
    country: str


class SpeedTestResult(BaseModel):
    download: float
    upload: float
    ping: float
    server: SpeedtestServer
    timestamp: datetime
    bytes_sent: int
    bytes_received: int
    share: Optional[str] = None
    client: SpeedtestClient


class SimpleHttpResponse(BaseModel):
    status: Optional[int]
    decoded_data: Optional[str]
    as_json: Optional[Union[List[Any], Dict[Any, Any]]]
    error: Optional[str]
    timeout: bool


class Helper:
    LOCALSERVER_CANDIDATES = ["0.0.0.0", "::"]
    DOCS_CANDIDATE_URLS = ["/docs", "/v1.0/ui/"]
    API_CANDIDATE_URLS = ["/docs.json", "/openapi.json", "/swagger.json"]
    PORT = 81
    BLUEOS_SYSTEM_SERVICES_PORTS = {
        PORT,  # Helper
        2748,  # NMEA Injector
        6020,  # MAVLink Camera Manager
        6030,  # System Information
        6040,  # MAVLink2Rest
        7777,  # File Browser
        8000,  # ArduPilot Manager
        8081,  # Version Chooser
        8088,  # ttyd
        9000,  # Wifi Manager
        9002,  # Cerulean DVL
        9090,  # Cable-guy
        9100,  # Commander
        9101,  # Bag Of Holding
        9110,  # Ping Service
        9111,  # Beacon Service
        9120,  # Pardal
        9134,  # Kraken
        27353,  # Bridget
    }
    SKIP_PORTS: Set[int] = {
        22,  # SSH
        80,  # BlueOS
        5201,  # Iperf
        6021,  # Mavlink Camera Manager's WebRTC signaller
        7000,  # Major Tom does not have a public API yet
        8554,  # Mavlink Camera Manager's RTSP server
        5777,  # ardupilot-manager's Mavlink TCP Server
        5555,  # DGB server
        2770,  # NGINX
    }
    KNOWN_SERVICES: Set[ServiceInfo] = set()
    # Whether we should or not keep a BlueOS system service when it's TCP port is not alive.
    # If 'False', when a service dies, it is not returned as an available service
    KEEP_BLUEOS_SERVICES_ALIVE = False
    # Wether or not we should rescan periodically all services
    PERIODICALLY_RESCAN_ALL_SERVICES = False
    # Wether or not we should rescan periodically just the 3rdparty services (extensions)
    PERIODICALLY_RESCAN_3RDPARTY_SERVICES = True

    @staticmethod
    # pylint: disable=too-many-arguments,too-many-branches,too-many-locals
    def simple_http_request(
        host: str,
        port: int = http.client.HTTP_PORT,
        path: str = "/",
        timeout: Optional[float] = None,
        method: str = "GET",
        try_json: bool = False,
        follow_redirects: int = 0,
    ) -> SimpleHttpResponse:
        """This function is a simple wrappper around http.client to make convenient requests and get the answer
        knowing that it will never raise"""

        conn: Optional[Union[http.client.HTTPConnection, http.client.HTTPSConnection]] = None
        request_response = SimpleHttpResponse(status=None, decoded_data=None, as_json=None, timeout=False, error=None)

        # Based on requests library
        headers = {
            "User-Agent": "python",
            "Accept-Encoding": "gzip, deflate",
            "Accept": "*/*",
        }
        # Prepare the header for json request
        if try_json:
            headers["Accept"] = "application/json"

        try:
            # Make the connection and the request
            if port == http.client.HTTPS_PORT:
                conn = http.client.HTTPSConnection(host, port, timeout=timeout)
            else:
                conn = http.client.HTTPConnection(host, port, timeout=timeout)

            conn.request(method, path, headers=headers)
            response = conn.getresponse()

            # Follow redirects if required
            location_header = response.getheader("location")
            if follow_redirects > 0 and location_header is not None:
                url = urlparse(location_header)
                return Helper.simple_http_request(
                    host=url.hostname or host,
                    port=url.port or port,
                    path=url.path or path,  # note: ignoring params, query and fragment
                    timeout=timeout,
                    method=method,
                    try_json=try_json,
                    follow_redirects=follow_redirects - 1,
                )

            # Decode the data
            request_response.status = response.status
            if response.status == http.client.OK:
                encoding = response.headers.get_content_charset() or "utf-8"
                if response.getheader("Content-Encoding") == "gzip":
                    buffer = BytesIO(response.read())
                    with gzip.GzipFile(fileobj=buffer) as file:
                        decompressed_data = file.read()
                else:
                    decompressed_data = response.read()

                request_response.decoded_data = decompressed_data.decode(encoding)

                # Interpret it as json
                if try_json:
                    request_response.as_json = json.loads(request_response.decoded_data)

        except socket.timeout as e:
            logger.warning(e)
            request_response.timeout = True
            request_response.error = str(e)

        except (http.client.HTTPException, socket.error, json.JSONDecodeError) as e:
            logger.warning(e)
            request_response.error = str(e)

        except Exception as e:
            logger.exception(e)
            request_response.error = str(e)

        finally:
            if conn:
                conn.close()

        return request_response

    @staticmethod
    @temporary_cache(timeout_seconds=1)  # a temporary cache helps us deal with changes in metadata
    def detect_service(port: int) -> ServiceInfo:
        path = port_to_service_map.get(port)
        info = ServiceInfo(valid=False, title="Unknown", documentation_url="", versions=[], port=port, path=path)

        response = Helper.simple_http_request(
            "127.0.0.1", port=port, path="/", timeout=1.0, method="GET", follow_redirects=10
        )
        log_msg = f"Detecting service at port {port}"
        if response.status != http.client.OK:
            # If not valid web server, documentation will not be available
            logger.debug(f"{log_msg}: Invalid: {response.status} - {response.decoded_data}")
            return info

        info.valid = True
        try:
            soup = BeautifulSoup(response.decoded_data, features="html.parser")
            title_element = soup.find("title")
            info.title = title_element.text.strip() if title_element else "Unknown"
            log_msg = f"{log_msg}: {info.title}"
        except Exception as e:
            logger.warning(f"Failed parsing the service title: {e}")

        # Try to get the metadata from the service
        response = Helper.simple_http_request(
            "127.0.0.1",
            port=port,
            path="/register_service",
            timeout=1.0,
            method="GET",
            try_json=True,
            follow_redirects=10,
        )
        response_as_json = response.as_json
        if response.status == http.client.OK and response_as_json is not None and isinstance(response_as_json, dict):
            try:
                info.metadata = ServiceMetadata.parse_obj(response_as_json)
                info.metadata.sanitized_name = re.sub(r"[^a-z0-9]", "", info.metadata.name.lower())
            except Exception as e:
                logger.warning(f"Failed parsing the received JSON as ServiceMetadata object: {e}")
        else:
            logger.debug(f"No metadata received from {info.title} (port {port})")

        # Try to get the documentation links
        for documentation_path in Helper.DOCS_CANDIDATE_URLS:
            # Skip until we find a valid documentation path
            response = Helper.simple_http_request(
                "127.0.0.1", port=port, path=documentation_path, timeout=1.0, method="GET", follow_redirects=10
            )
            if response.status != http.client.OK:
                continue
            info.documentation_url = documentation_path

            # Get main openapi json description file
            for api_path in Helper.API_CANDIDATE_URLS:
                response = Helper.simple_http_request(
                    "127.0.0.1", port=port, path=api_path, timeout=1.0, method="GET", try_json=True, follow_redirects=10
                )

                # Skip until we find the expected data. The expected data is like:
                # {
                #     "paths": {
                #         "v1.0.0": ...,
                #         "v2.0.0": ...,
                #     }
                # }
                response_as_json = response.as_json
                if (
                    response.status != http.client.OK
                    or response_as_json is None
                    or not isinstance(response_as_json, dict)
                ):
                    continue
                version_paths = response_as_json.get("paths", {}).keys()

                # Check all available versions for the ones that provide a swagger-ui
                for version_path in version_paths:
                    response = Helper.simple_http_request(
                        "127.0.0.1", port=port, path=str(version_path), timeout=1.0, method="GET", follow_redirects=10
                    )
                    if (
                        response.status == http.client.OK
                        and response.decoded_data is not None
                        and "swagger-ui" in response.decoded_data
                    ):
                        info.versions += [version_path]

            # Since we have at least found one info.documentation_path, we finish here
            break

        logger.debug(f"{log_msg}: Valid.")
        return info

    @staticmethod
    @temporary_cache(timeout_seconds=3)
    def scan_ports() -> List[ServiceInfo]:
        # Get TCP ports that are listen and can be accessed by external users (like server in 0.0.0.0, as described by the LOCALSERVER_CANDIDATES)
        ports = {
            connection.laddr.port
            for connection in psutil.net_connections("tcp")
            if connection.status == psutil.CONN_LISTEN and connection.laddr.ip in Helper.LOCALSERVER_CANDIDATES
        }

        # If a known service is not within the detected ports, we remove it from the known services
        if Helper.KEEP_BLUEOS_SERVICES_ALIVE:
            Helper.KNOWN_SERVICES = {
                service
                for service in Helper.KNOWN_SERVICES
                if service.port in ports or service.port in Helper.BLUEOS_SYSTEM_SERVICES_PORTS
            }
        else:
            Helper.KNOWN_SERVICES = {service for service in Helper.KNOWN_SERVICES if service.port in ports}

        # Filter out ports we want to skip, as well as the ports from services we already know, assuming the services don't change,
        known_ports = {service.port for service in Helper.KNOWN_SERVICES}
        ports.difference_update(Helper.SKIP_PORTS, known_ports)

        # The detect_services run several of requests sequentially, so we are capping the amount of executors to lower the peaks on the CPU usage
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            tasks = [executor.submit(Helper.detect_service, port) for port in ports]
            services = {task.result() for task in futures.as_completed(tasks)}

        # Update our known services cache
        Helper.KNOWN_SERVICES.update(services)
        Helper.update_nginx(services)
        return [service for service in Helper.KNOWN_SERVICES if service.valid]

    @staticmethod
    @temporary_cache(timeout_seconds=1)
    def check_website(site: Website) -> WebsiteStatus:
        hostname = str(site.value["hostname"])
        port = int(str(site.value["port"]))
        path = str(site.value["path"])

        response = Helper.simple_http_request(hostname, port=port, path=path, timeout=10, method="GET")
        website_status = WebsiteStatus(site=site, online=False)

        log_msg = f"Running check_website for '{hostname}:{port}'"
        if response.error is None:
            logger.debug(f"{log_msg}: Online.")
            website_status.online = True
        else:
            logger.warning(f"{log_msg}: Offline: {website_status.error}.")
            website_status.error = response.error

        return website_status

    @staticmethod
    def reload_nginx() -> None:
        with open("/var/run/nginx.pid", "r", encoding="utf-8") as f:
            pid = int(f.readline())
            # kill -HUP is the right way of doing a graceful reload in Nginx
            subprocess.run(["kill", "-HUP", f"{pid}"], check=False)

    @staticmethod
    def update_nginx(services: Set[ServiceInfo]) -> None:
        changed = 0
        for service in services:
            if service.metadata:
                if Helper.setup_nginx_route(service.metadata, service.port):
                    changed += 1
        if changed:
            Helper.reload_nginx()

    @staticmethod
    @temporary_cache(timeout_seconds=5)
    def check_internet_access() -> Dict[str, WebsiteStatus]:
        # 10 concurrent executors is fine here because its a very short/light task
        with futures.ThreadPoolExecutor(max_workers=10) as executor:
            tasks = [executor.submit(Helper.check_website, site) for site in Website]
            status_list = [task.result() for task in futures.as_completed(tasks)]

        return {status.site.name: status for status in status_list}

    @staticmethod
    def setup_nginx_route(metadata: ServiceMetadata, port: int) -> bool:
        name = metadata.sanitized_name
        text = f"""
        location /extensionv2/{name}/ {{
        proxy_pass http://127.0.0.1:{port}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        }}
        """
        filename = f"/home/pi/tools/nginx/extensions/{name}.conf"
        Path.mkdir(Path("/home/pi/tools/nginx/extensions/"), parents=True, exist_ok=True)
        try:
            with open(filename, "r", encoding="utf-8") as f:
                if f.read() == text:
                    return False
        except Exception as e:
            logging.info(f"file '{filename}' not found ({e}):, a new one will be created")
        with open(filename, "w", encoding="utf-8") as f:
            logging.info(f"updating nginx route for {name}")
            f.write(text)
            logging.info(f"file updated: {filename}")
        return True


fast_api_app = FastAPI(
    title="Helper API",
    description="Everybody's helper to find web services that are running in BlueOS.",
    default_response_class=PrettyJSONResponse,
)
fast_api_app.router.route_class = GenericErrorHandlingRoute


@fast_api_app.get(
    "/web_services",
    response_model=List[ServiceInfo],
    summary="Retrieve web services found.",
)
@version(1, 0)
def web_services() -> Any:
    """REST API endpoint to retrieve web services running."""
    return Helper.scan_ports()


@fast_api_app.get(
    "/check_internet_access",
    response_model=Dict[str, WebsiteStatus],
    summary="Used to check if some websites are available or if there is internet access.",
)
@version(1, 0)
def check_internet_access() -> Any:
    return Helper.check_internet_access()


@fast_api_app.get(
    "/hardware_id",
    response_model=str,
    summary="An UUID that can be used as unique identifier based in the motherboard hardware configuration.",
)
@version(1, 0)
@cache
def hardware_id() -> Any:
    try:
        with open("/etc/blueos/hardware-uuid", "r", encoding="utf-8") as file:
            content = file.read().strip()
        uuid_obj = UUID(content, version=4)
        return str(uuid_obj)
    except Exception as exception:
        raise HTTPException(status_code=400, detail="Error: {exception}") from exception


@fast_api_app.get(
    "/software_id",
    response_model=str,
    summary="An UUID that can bse used as unique identifier, generated once on BlueOS first boot.",
)
@version(1, 0)
@cache
def software_id() -> Any:
    try:
        with open("/etc/blueos/uuid", "r", encoding="utf-8") as file:
            content = file.read().strip()
        uuid_obj = UUID(content, version=4)
        return str(uuid_obj)
    except Exception as exception:
        raise HTTPException(status_code=400, detail="Error: {exception}") from exception


@fast_api_app.get(
    "/internet_best_server",
    response_model=SpeedTestResult,
    summary="Check internet best server for test from BlueOS.",
)
@version(1, 0)
async def internet_best_server() -> Any:
    # Since we are finding a new server, clear previous results
    # pylint: disable=global-statement
    global SPEED_TEST
    SPEED_TEST = Speedtest(secure=True)
    SPEED_TEST.get_best_server()
    return SPEED_TEST.results.dict()


@fast_api_app.get(
    "/internet_download_speed",
    response_model=SpeedTestResult,
    summary="Check internet download speed test from BlueOS.",
)
@version(1, 0)
async def internet_download_speed() -> Any:
    if not SPEED_TEST:
        raise RuntimeError("SPEED_TEST not initialized, initialize server search.")
    SPEED_TEST.download()
    return SPEED_TEST.results.dict()


@fast_api_app.get(
    "/internet_upload_speed",
    response_model=SpeedTestResult,
    summary="Check internet upload speed test from BlueOS.",
)
@version(1, 0)
async def internet_upload_speed() -> Any:
    if not SPEED_TEST:
        raise RuntimeError("SPEED_TEST not initialized, initialize server search.")
    SPEED_TEST.upload(pre_allocate=False)
    return SPEED_TEST.results.dict()


@fast_api_app.get(
    "/internet_test_previous_result",
    response_model=SpeedTestResult,
    summary="Return previous result of internet speed test.",
)
@version(1, 0)
async def internet_test_previous_result() -> Any:
    if not SPEED_TEST:
        raise RuntimeError("SPEED_TEST not initialized, initialize server search.")
    return SPEED_TEST.results.dict()


async def periodic() -> None:
    while True:
        await asyncio.sleep(60)
        Helper.check_internet_access()

        # Clear the known ports cache and re-scan it
        if Helper.PERIODICALLY_RESCAN_ALL_SERVICES:
            Helper.KNOWN_SERVICES.clear()
        # To get changes in the metadata of extensions, we clear the cache for them to force a rescan
        elif Helper.PERIODICALLY_RESCAN_3RDPARTY_SERVICES:
            Helper.KNOWN_SERVICES = {
                service for service in Helper.KNOWN_SERVICES if service.port in Helper.BLUEOS_SYSTEM_SERVICES_PORTS
            }


app = VersionedFastAPI(
    fast_api_app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)

port_to_service_map: Dict[int, str] = parse_nginx_file("/home/pi/tools/nginx/nginx.conf")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()

    # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, loop=loop, host="0.0.0.0", port=Helper.PORT, log_config=None)
    server = Server(config)

    loop.create_task(periodic())
    loop.run_until_complete(server.serve())
