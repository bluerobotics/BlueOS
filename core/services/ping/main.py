#! /usr/bin/env python3
import argparse
import asyncio
import logging
from typing import Any, List, Set

from commonwealth.settings.manager import PydanticManager
from commonwealth.utils.apis import (
    GenericErrorHandlingRoute,
    PrettyJSONResponse,
    use_local_docs_assets,
)
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import FastAPI, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from ping1d_driver import USERDATA
from pingmanager import PingManager
from pingprober import PingProber
from portwatcher import PortWatcher
from settings import SettingsV1
from typedefs import PingDeviceDescriptorModel
from uvicorn import Config, Server

SERVICE_NAME = "ping"

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

app = FastAPI(
    title="Ping Manager API",
    description="Ping Manager is responsible for managing Ping devices connected to BlueOS.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)
app.router.route_class = GenericErrorHandlingRoute
logger.info("Starting Ping Service.")

# TODO: move to singleton
ping_manager = PingManager()
ping_prober = PingProber()
port_watcher = PortWatcher(probe_callback=ping_prober.probe, found_callback=ping_manager.register_ethernet_ping360)
settings_manager = PydanticManager(SERVICE_NAME, SettingsV1, USERDATA / "settings" / SERVICE_NAME)
port_watcher.ignored_paths = settings_manager.settings.ignored_ports


@app.get("/sensors", response_model=List[PingDeviceDescriptorModel], summary="Current sensors detected.")
@version(1, 0)
def get_sensors() -> Any:
    devices = ping_manager.devices()
    return [PingDeviceDescriptorModel.from_descriptor(device) for device in devices]


@app.post("/sensors", status_code=status.HTTP_200_OK, summary="Set sensor settings.")
@version(1, 0)
def set_sensor(sensor_settings: dict[str, Any]) -> Any:
    if "port" not in sensor_settings:
        raise ValueError("'device' key is missing")
    return ping_manager.update_device_settings(sensor_settings)


@app.get("/ignored_ports", response_model=List[str], summary="Serial ports that are not probed.")
@version(1, 0)
def get_ignored_ports() -> Any:
    return sorted(port_watcher.ignored_paths)


@app.post("/ignored_ports", status_code=status.HTTP_200_OK, summary="Set serial ports that are not probed.")
@version(1, 0)
def set_ignored_ports(ports: Set[str]) -> Any:
    settings_manager.load()  # re-load as ping1d drivers could have changed it
    settings_manager.settings.ignored_ports = ports
    settings_manager.save()
    port_watcher.ignored_paths = ports


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)
use_local_docs_assets(app)


@app.get("/")
async def root() -> Any:
    html_content = """
    <html>
        <head>
            <title>Ping Service</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


async def sensor_manager() -> None:
    port_watcher.set_port_post_callback(ping_manager.stop_driver_at_port)

    ping_prober.on_ping_found(ping_manager.launch_driver_instance)

    await port_watcher.start_watching()


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    parser = argparse.ArgumentParser(description="Ping Service for Bluerobotics BlueOS")
    _ = parser.parse_args()

    # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, host="0.0.0.0", port=9110, log_config=None)
    server = Server(config)

    asyncio.create_task(sensor_manager())
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
