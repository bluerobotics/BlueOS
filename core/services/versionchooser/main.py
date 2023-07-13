#!/usr/bin/env python3
import logging
from typing import Any

import aiodocker
import connexion
from aiohttp import web
from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger

from utils.chooser import STATIC_FOLDER, VersionChooser

SERVICE_NAME = "version-chooser"

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

logger.info("Starting Version Chooser")

versionChooser = VersionChooser(aiodocker.Docker())


async def index(_request: web.Request) -> Any:
    return versionChooser.index()


async def get_version() -> Any:
    return versionChooser.get_version()


async def pull_version(request: web.Request) -> Any:
    data = await request.json()
    repository = data["repository"]
    tag = data["tag"]
    return await versionChooser.pull_version(request, repository, tag)


async def set_version(request: web.Request) -> Any:
    data = await request.json()
    tag = data["tag"]
    repository = data["repository"]
    return await versionChooser.set_version(repository, tag)


async def delete_version(request: web.Request) -> Any:
    data = await request.json()
    tag = data["tag"]
    repository = data["repository"]
    return await versionChooser.delete_version(repository, tag)


async def get_available_local_versions() -> Any:
    return await versionChooser.get_available_local_versions()


async def get_available_versions(repository: str, image: str) -> Any:
    return await versionChooser.get_available_versions(f"{repository}/{image}")


async def get_bootstrap_version() -> Any:
    return await versionChooser.get_bootstrap_version()


async def set_bootstrap_version(request: web.Request) -> Any:
    data = await request.json()
    tag = data["tag"]
    return await versionChooser.set_bootstrap_version(tag)


async def load(request: web.Request) -> Any:
    data = await request.read()
    return await versionChooser.load(data)


async def restart() -> Any:
    return await versionChooser.restart()


if __name__ == "__main__":
    maximum_number_of_bytes = 2 * (2**30)  # 2 GBs
    app = connexion.AioHttpApp(__name__, specification_dir="openapi/")
    app.add_api("versionchooser.yaml", arguments={"title": "BlueOS Version Chooser"}, pass_context_arg_name="request")
    app.app._client_max_size = maximum_number_of_bytes
    app.app.router.add_static("/static/", path=str(STATIC_FOLDER))
    app.app.router.add_route("GET", "/", index)
    app.run(port=8081)
