#! /usr/bin/env python3
import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, List

import uvicorn
from commonwealth.utils.apis import PrettyJSONResponse
from commonwealth.utils.logs import InterceptHandler
from fastapi import Body, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger

from api.manager import (
    EthernetInterface,
    EthernetManager,
    InterfaceConfiguration,
    InterfaceMode,
)

parser = argparse.ArgumentParser(description="CableGuy service for Blue Robotics Companion")
parser.add_argument(
    "--default_config",
    dest="default_config",
    type=str,
    default="bluerov2",
    choices=["bluerov2"],
    help="Specify configuration to use if settings file cannot be loaded or is not found. Defaults to 'bluerov2'.",
)

args = parser.parse_args()

if args.default_config == "bluerov2":
    default_config = EthernetInterface(
        name="eth0", configuration=InterfaceConfiguration(ip="192.168.2.2", mode=InterfaceMode.Unmanaged)
    )

manager = EthernetManager(default_config)

logging.basicConfig(handlers=[InterceptHandler()], level=0)

HTML_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "html")

app = FastAPI(
    title="Cable Guy API",
    description="Cable Guy is responsible for managing internet interfaces on Companion.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)


@app.get("/ethernet", response_model=List[EthernetInterface], summary="Retrieve ethernet interfaces.")
@version(1, 0)
def retrieve_interfaces() -> Any:
    """REST API endpoint to retrieve the configured ethernet interfaces."""
    return manager.get_interfaces()


@app.post("/ethernet", response_model=EthernetInterface, summary="Configure a ethernet interface.")
@version(1, 0)
def configure_interface(interface: EthernetInterface = Body(...)) -> Any:
    """REST API endpoint to configure a new ethernet interface or modify an existing one."""
    if not manager.set_configuration(interface):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not configure ethernet interface with provided configuration.",
        )

    manager.save()
    return interface


app = VersionedFastAPI(
    app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)
app.mount("/", StaticFiles(directory=str(HTML_FOLDER), html=True))

if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.error(
            "You need root privileges to run this script.\nPlease try again, this time using **sudo**. Exiting."
        )
        sys.exit(1)

    # Running uvicorn with log disabled so loguru can handle it
    uvicorn.run(app, host="0.0.0.0", port=9090, log_config=None)
