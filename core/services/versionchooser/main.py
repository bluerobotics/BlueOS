#! /usr/bin/env python3
import asyncio
import logging
from typing import Any

import aiodocker
import connexion
from aiohttp import web
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from loguru import logger

from docker_login import (
    DockerLoginInfo,
    get_docker_accounts,
    make_docker_login,
    make_docker_logout,
)
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


async def docker_login(request: web.Request) -> None:
    data = await request.json()
    info = DockerLoginInfo.from_json(data)

    return make_docker_login(info)


async def docker_logout(request: web.Request) -> Any:
    data = await request.json()
    info = DockerLoginInfo.from_json(data)

    return make_docker_logout(info)


def docker_accounts() -> Any:
    return get_docker_accounts()


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    app = connexion.AioHttpApp(__name__, specification_dir="openapi/")
    app.add_api("versionchooser.yaml", arguments={"title": "BlueOS Version Chooser"}, pass_context_arg_name="request")

    app.app.client_max_size = 2 * (2**30)  # 2 GBs

    app.app.router.add_static("/static/", path=str(STATIC_FOLDER))
    app.app.router.add_route("GET", "/", index)

    runner = web.AppRunner(app.app)
    await runner.setup()

    site = web.TCPSite(runner, host="0.0.0.0", port=8081)
    await site.start()

    # Wait forever
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
