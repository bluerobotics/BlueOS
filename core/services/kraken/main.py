#! /usr/bin/env python3
import argparse
import asyncio
import logging
from typing import Any, List, Optional

from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.general import limit_ram_usage
from commonwealth.utils.logs import InterceptHandler, init_logger
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from pydantic import BaseModel
from uvicorn import Config, Server

from kraken import Kraken


class Extension(BaseModel):
    name: str
    docker: str
    tag: str
    permissions: str
    enabled: bool
    identifier: str
    user_permissions: str
    id: Optional[str] = None

    def is_valid(self) -> bool:
        return all([self.name, self.docker, self.tag, any([self.permissions, self.user_permissions]), self.identifier])


SERVICE_NAME = "kraken"

limit_ram_usage()

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

kraken = Kraken()

app = FastAPI(
    title="Kraken API",
    description="Kraken is the BlueOS service responsible for installing and managing thirdy-party extensions.",
)
app.router.route_class = GenericErrorHandlingRoute
logger.info("Releasing the Kraken!")


@app.get("/extensions_manifest", status_code=status.HTTP_200_OK)
@version(1, 0)
async def fetch_manifests() -> Any:
    return await kraken.fetch_manifests()


@app.get("/installed_extensions", status_code=status.HTTP_200_OK)
@version(1, 0)
async def get_installed_extensions() -> Any:
    extensions = await kraken.get_configured_extensions()
    extensions_list = [
        Extension(
            identifier=extension.identifier,
            name=extension.name,
            docker=extension.docker,
            tag=extension.tag,
            permissions=extension.permissions,
            enabled=extension.enabled,
            user_permissions=extension.user_permissions,
            id=extension.id,
        )
        for extension in extensions
    ]
    extensions_list.sort(key=lambda extension: extension.name)
    return extensions_list


@app.post("/extension/install", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def install_extension(extension: Extension) -> Any:
    if not extension.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid extension description",
        )
    return StreamingResponse(kraken.install_extension(extension))


@app.post("/extension/update_to_version", status_code=status.HTTP_201_CREATED)
@version(1, 0)
async def update_extension(extension_identifier: str, new_version: str) -> Any:
    return StreamingResponse(kraken.update_extension_to_version(extension_identifier, new_version))


@app.post("/extension/uninstall", status_code=status.HTTP_200_OK)
@version(1, 0)
async def uninstall_extension(extension_identifier: str) -> Any:
    return await kraken.uninstall_extension_from_identifier(extension_identifier)


@app.post("/extension/enable", status_code=status.HTTP_200_OK)
@version(1, 0)
async def enable_extension(extension_identifier: str) -> Any:
    return await kraken.enable_extension(extension_identifier)


@app.post("/extension/disable", status_code=status.HTTP_200_OK)
@version(1, 0)
async def disable_extension(extension_identifier: str) -> Any:
    return await kraken.disable_extension(extension_identifier)


@app.post("/extension/restart", status_code=status.HTTP_202_ACCEPTED)
@version(1, 0)
async def restart_extension(extension_identifier: str) -> Any:
    return await kraken.restart_extension(extension_identifier)


@app.get("/list_containers", status_code=status.HTTP_200_OK)
@version(1, 0)
async def list_containers() -> Any:
    containers = await kraken.list_containers()
    return [
        {
            "name": container["Names"][0],
            "image": container["Image"],
            "imageId": container["ImageID"],
            "status": container["Status"],
        }
        for container in containers
    ]


@app.get("/log", status_code=status.HTTP_200_OK)
@version(1, 0)
async def log_containers(container_name: str) -> List[str]:
    return await kraken.load_logs(container_name)


@app.get("/stats", status_code=status.HTTP_200_OK)
@version(1, 0)
async def load_stats() -> Any:
    return await kraken.load_stats()


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger(SERVICE_NAME).setLevel(logging.DEBUG)

    logger.info("Releasing the Kraken service.")

    loop = asyncio.new_event_loop()

    config = Config(app=app, loop=loop, host="0.0.0.0", port=9134, log_config=None)
    server = Server(config)

    loop.create_task(kraken.run())
    loop.run_until_complete(server.serve())
    loop.run_until_complete(kraken.stop())
