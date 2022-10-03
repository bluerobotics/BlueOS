#! /usr/bin/env python3
import argparse
import asyncio
import logging
from typing import Any

from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.logs import InterceptHandler, get_new_log_path
from fastapi import FastAPI, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from pydantic import BaseModel
from uvicorn import Config, Server

from kraken import Kraken


class Extension(BaseModel):
    name: str
    tag: str
    permissions: str
    enabled: bool
    identifier: str


SERVICE_NAME = "kraken"

logging.basicConfig(handlers=[InterceptHandler()], level=0)

kraken = Kraken()

try:
    logger.add(get_new_log_path(SERVICE_NAME))
except Exception as e:
    print(f"unable to set logging path: {e}")


app = FastAPI(
    title="Kraken API",
    description="Kraken is the BlueOS service responsible for installing and managing thirdy-party extensions.",
)
app.router.route_class = GenericErrorHandlingRoute
logger.info("Releasing the Kraken!")


@app.get("/extensions_manifest", status_code=status.HTTP_200_OK)
@version(1, 0)
async def fetch_manifest() -> Any:
    return await kraken.fetch_manifest()


@app.get("/installed_extensions", status_code=status.HTTP_200_OK)
@version(1, 0)
async def get_installed_extensions() -> Any:
    extensions = await kraken.get_configured_extensions()
    return [
        Extension(
            identifier=extension.identifier,
            name=extension.name,
            tag=extension.tag,
            permissions=extension.permissions,
            enabled=extension.enabled,
        )
        for extension in extensions
    ]


@app.post("/extension/install", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def install_extension(extension: Extension) -> Any:
    return await kraken.install_extension(extension)


@app.post("/extension/uninstall", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def uninstall_extension(extension_name: str) -> Any:
    return await kraken.uninstall_extension(extension_name)


@app.get("/list_containers", status_code=status.HTTP_200_OK)
@version(1, 0)
async def list_containers() -> Any:
    containers = await kraken.list_containers()
    return [
        {"name": container["Names"][0], "image": container["Image"], "imageId": container["ImageID"]}
        for container in containers
    ]


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)


@app.get("/")
async def root() -> Any:
    html_content = """
    <html>
        <head>
            <title>Kraken</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.add(get_new_log_path(SERVICE_NAME))

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger("kraken").setLevel(logging.DEBUG)

    logger.info("Releasing the Kraken service.")

    loop = asyncio.new_event_loop()

    config = Config(app=app, loop=loop, host="0.0.0.0", port=9134, log_config=None)
    server = Server(config)

    loop.create_task(kraken.run())
    loop.run_until_complete(server.serve())
    loop.run_until_complete(kraken.stop())
