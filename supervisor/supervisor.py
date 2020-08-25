#!/usr/bin/env python3
import os
import json
import time
import pathlib
import asyncio
from subprocess import Popen
import shutil
from typing import Optional, Dict, Any

import connexion
from aiohttp import web
from service import Service
from utils.updater import Updater


# this snippet takes care of running non-dockerized
IS_DOCKER = True
current_path = pathlib.Path(__file__).parent.absolute()
ROOT = pathlib.Path("/supervisor")
config_folder = os.path.join(current_path, ".config")
STATIC_PATH = "/supervisor/static"

if not os.path.exists(config_folder):
    IS_DOCKER = False
    ROOT = current_path
    config_folder = os.path.join(current_path.parent.absolute(), "config")
    STATIC_PATH = str(ROOT) + "/static"


class Supervisor:
    """
    Main supervisor
    Reponsible for creating, stoping, and managing the docker containers
    """

    services: Dict[str, Any] = {}
    last_versions_fetch: int = 0
    ttyd_session: Optional[Any] = None
    updater: Updater = Updater()
    settings: Dict[str, Any]

    def __init__(self) -> None:
        self.load_settings()
        for service, config in self.settings["dockers"].items():
            # don't create supervisor service if running non-dockerized
            if not IS_DOCKER and service == "supervisor":
                continue
            self.services[service] = Service(config)
        print(f"Found {len(self.services.keys())} Services:")
        for service in self.services:
            print(service)

        asyncio.create_task(self.do_maintenance())

    def load_settings(self) -> None:
        """Loads the settings file to self.settings, create it from defaults if not available"""
        config_path = os.path.join(config_folder, "dockers.json")
        default_config_path = os.path.join(
            current_path, "static", "dockers.json.default"
        )
        if not os.path.exists(config_path):
            shutil.copy(default_config_path, config_path)

        with open(config_path) as config_file:
            self.settings = json.load(config_file)

    async def enable(self, name: str) -> web.Response:
        """Enables a Docker container

        Args:
            name (str): Docker container to enable

        Returns:
            web.Response: 200 ("ok"), 404 if invalid name, 500 for internal error
        """
        if name not in self.services:
            return web.Response(status=404, text=f"Invalid image: {name}")
        self.settings["dockers"][name]["enabled"] = True
        self.services[name].enable()
        self.update_settings()
        return web.Response(status=200, text="ok")

    async def disable(self, name: str) -> web.Response:
        """Disables a Docker container

        Args:
            name (str): Docker container to disable

        Returns:
            web.Response: 200 ("ok"), 404 if invalid name, 500 for internal error
        """
        if name not in self.services:
            return web.Response(status=404, text=f"Invalid image: {name}")
        self.settings["dockers"][name]["enabled"] = False
        self.services[name].disable()
        self.update_settings()
        return web.Response(status=200, text="ok")

    async def attach(self, name: str) -> web.Response:
        """Starts a tty session attached to container "name"

        Args:
            name (str): Docker container to attach to

        Returns:
            web.Response: 200 ("ok"), 404 if invalid name, 500 for internal error
        """
        if name not in self.services:
            return web.Response(status=404, text=f"Invalid image: {name}")
        if self.ttyd_session is not None:
            self.ttyd_session.terminate()
            self.ttyd_session.wait()
            time.sleep(0.5)
        container_id = self.services[name].container.id
        self.ttyd_session = Popen(
            [
                "/usr/bin/ttyd",
                "-p",
                "8082",
                "/usr/bin/docker",
                "exec",
                "-it",
                container_id,
                "/usr/bin/tmux",
            ]
        )
        return web.Response(status=200, text="ok")

    async def set_version(self, name: str, version: str) -> web.Response:
        """Sets the version of a service

        Args:
            name (str): Service name as in the docker.json file
            version (str): the new version(tag) to use

        Returns:
            web.Response: 200 for success, 404 for invalid image
        """
        if name not in self.services:
            return web.Response(status=404, text=f"Invalid image: {name}")
        self.settings["dockers"][name]["tag"] = version
        self.update_settings()
        self.services[name].set_version(version)
        return web.Response(status=200, text="ok")

    async def top(self, name: str) -> web.Response:
        """Returns the running processes in the container

        Args:
            name (str): Name of the running container

        Returns:
            dict: described in https://docs.docker.com/engine/api/v1.24/#list-processes-running-inside-a-container
        """
        service = self.services.get(name, None)
        if service is None:
            return web.Response(status=404, text=f"Invalid image: {name}")
        return web.json_response(service.get_top())

    async def restart(self, name: str) -> web.Response:
        """Restarts a docker container

        Args:
            name (str): name of the container to restart
        """
        service = self.services.get(name, None)
        if service is None:
            return web.Response(status=404, text=f"Invalid image: {name}")
        return web.json_response(service.restart())

    def update_settings(self) -> None:
        """Writes current settings to dockers.json"""
        with open(os.path.join(config_folder, "dockers.json"), "w") as config_file:
            json.dump(self.settings, config_file, indent=4)

    async def do_maintenance(self) -> None:
        """Periodically checks all running containers, starting and stopping
        them as necessary
        """
        while True:
            print("Doing maintenance...")
            try:
                for service_name, service in self.services.items():
                    service.update()
                    # Disables service if it fails too much
                    if service.starts > 10 and service.enabled:
                        print(
                            "service {service_name} failed to start 10 times, disabling it for sanity reasons..."
                        )
                        await self.disable(service_name)

            except Exception as error:
                print(f"error in do_maintenance: {error}")
            # self.updater.fetch_available_versions()
            await asyncio.sleep(1)

    async def get_status(self) -> web.Response:
        """Gets the status of all services

        Returns:
            web.Response: json status
        TODO: describe this json in yaml
        """
        status = {}
        for service_name, service in self.services.items():
            status[service_name] = service.get_status()
        return web.json_response(status)

    async def get_versions(self) -> web.Response:
        """Gets the status of all services

        Returns:
            web.Response: json status
        TODO: describe this json in yaml
        """
        return web.json_response(self.updater.get_all_versions())

    async def get_version(self) -> web.Response:
        """Gets the name of the version currently running

        Returns:
            web.Response: The version currently running
        """
        return web.json_response(self.updater.get_running_version(self.services))

    async def get_logs(self, name: str) -> web.Response:
        """Gets logs of a service

        Args:
            name (str): service name

        Returns:
            web.Response: Html response with the logs as pure text
        """
        if name not in self.services:
            return web.Response(status=404, text=f"Invalid image: {name}")
        return web.Response(status=200, text=self.services[name].get_logs())


# API methods


async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(str(ROOT) + "/index.html")


# These transparently forward the resquests to the Supervisor instance


async def status(request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.get_status()


async def enable(name: str, request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.enable(name)


async def disable(name: str, request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.disable(name)


async def attach(name: str, request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.attach(name)


async def top(name: str, request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.top(name)


async def restart(name: str, request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.restart(name)


async def log(name: str, request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.get_logs(name)


async def versions(request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.get_versions()


async def currentversion(request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"
    return await supervisor.get_version()


async def set_version(name: str, request: web.Request) -> web.Response:
    supervisor = request.config_dict["supervisor"]
    assert isinstance(supervisor, Supervisor), "Invalid Supervisor instance in aiohttp"

    await request.post()
    version = (await request.json())["version"]
    return await supervisor.set_version(name, version)


async def create_supervisor(aiohttp_app: web.Application) -> None:
    aiohttp_app["supervisor"] = Supervisor()


if __name__ == "__main__":
    app = connexion.AioHttpApp(__name__, specification_dir="openapi/")
    app.add_api(
        "supervisor.yaml",
        arguments={"title": "Companion Supervisor"},
        pass_context_arg_name="request",
    )
    app.app.on_startup.append(create_supervisor)
    app.app.router.add_static("/static/", path=str(STATIC_PATH))
    app.app.router.add_route("GET", "/", index)
    app.run(port=8081)
