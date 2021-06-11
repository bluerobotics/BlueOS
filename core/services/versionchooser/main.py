#!/usr/bin/env python3
from typing import Any

import connexion
import docker
from aiohttp import web

from utils.chooser import STATIC_FOLDER, VersionChooser

versionChooser = VersionChooser(docker.client.from_env())


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


async def get_available_versions(repository: str, image: str) -> Any:
    return await versionChooser.get_available_versions(f"{repository}/{image}")


if __name__ == "__main__":
    app = connexion.AioHttpApp(__name__, specification_dir="openapi/")
    app.add_api(
        "versionchooser.yaml", arguments={"title": "Companion Version Chooser"}, pass_context_arg_name="request"
    )
    app.app.router.add_static("/static/", path=str(STATIC_FOLDER))
    app.app.router.add_route("GET", "/", index)
    app.run(port=8081)
