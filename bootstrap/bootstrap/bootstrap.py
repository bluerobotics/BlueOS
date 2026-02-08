import curses
import json
import os
import pathlib
import shutil
import sys
import time
from typing import Any, Dict, Optional
from warnings import warn

import docker
import requests
from loguru import logger


class Bootstrapper:

    DEFAULT_FILE_PATH = pathlib.Path("/bootstrap/startup.json.default")
    DOCKER_CONFIG_PATH = pathlib.Path("/root/.config")
    DOCKER_CONFIG_FILE_PATH = DOCKER_CONFIG_PATH.joinpath("bootstrap/startup.json")
    HOST_CONFIG_PATH = os.environ.get("BLUEOS_CONFIG_PATH", "/tmp/blueos/.config")
    CORE_CONTAINER_NAME = "blueos-core"
    BOOTSTRAP_CONTAINER_NAME = "blueos-bootstrap"
    SETTINGS_NAME_CORE = "core"
    core_last_response_time = time.monotonic()

    def __init__(self, client: docker.DockerClient, low_level_api: Optional[docker.APIClient] = None) -> None:
        self.version_chooser_is_online = False
        self.client: docker.DockerClient = client
        self.core_last_response_time = time.monotonic()
        if low_level_api is None:
            self.low_level_api = docker.APIClient(base_url="unix://var/run/docker.sock")
        else:
            self.low_level_api = low_level_api

    @staticmethod
    def overwrite_config_file_with_defaults() -> None:
        """Overwrites the config file with the default configuration"""
        try:
            os.makedirs(pathlib.Path(Bootstrapper.DOCKER_CONFIG_FILE_PATH).parent, exist_ok=True)
        except Exception as exception:
            raise RuntimeError(
                f"Failed to create folder for configuration file: {Bootstrapper.DOCKER_CONFIG_FILE_PATH}"
            ) from exception

        try:
            shutil.copy(
                Bootstrapper.DOCKER_CONFIG_FILE_PATH, Bootstrapper.DOCKER_CONFIG_FILE_PATH.with_suffix(".json.bak")
            )
        except FileNotFoundError:
            logger.warning(f"File {Bootstrapper.DOCKER_CONFIG_FILE_PATH} not found, creating backup...")
        shutil.copy(Bootstrapper.DEFAULT_FILE_PATH, Bootstrapper.DOCKER_CONFIG_FILE_PATH)

    @staticmethod
    def read_config_file() -> Dict[str, Any]:
        """Tries to read the config file

        Returns:
            Any: Json data of startup.json
        """

        # Tries to open the current file
        config = {}
        try:
            with open(Bootstrapper.DOCKER_CONFIG_FILE_PATH, encoding="utf-8") as config_file:
                config = json.load(config_file)
                assert Bootstrapper.SETTINGS_NAME_CORE in config, "missing core entry in startup.json"
                necessary_keys = ["image", "tag", "binds", "privileged", "network"]
                for key in necessary_keys:
                    assert key in config[Bootstrapper.SETTINGS_NAME_CORE], f"missing key in json file: {key}"

        except Exception as error:
            logger.error(f"unable to read startup.json file ({error}), reverting to defaults...")
            # Copy defaults over and read again
            Bootstrapper.overwrite_config_file_with_defaults()
            with open(Bootstrapper.DEFAULT_FILE_PATH, encoding="utf-8") as config_file:
                config = json.load(config_file)

        config[Bootstrapper.SETTINGS_NAME_CORE]["binds"][str(Bootstrapper.HOST_CONFIG_PATH)] = {
            "bind": str(Bootstrapper.DOCKER_CONFIG_PATH),
            "mode": "rw",
        }
        return config

    def bootstrap_version(self) -> str:
        try:
            return next(
                str(container.image)
                for container in self.client.containers.list()
                if container.name == self.BOOTSTRAP_CONTAINER_NAME
            )
        except Exception as exception:
            return f"Bootstrap does not follow standard name: {self.BOOTSTRAP_CONTAINER_NAME}, {exception}"

    def pull(self, component_name: str) -> None:
        """Pulls an image

        Args:
            component_name (str): name of one of our components in startup.json, such as
            "core", "ttyd", or "bootstrap"
        """

        image = self.config[component_name]
        image_name = image["image"]
        tag = image["tag"]

        curses_ui = True
        try:
            # TODO: make it not clear the whole screen
            screen = curses.initscr()
            curses.noecho()
            curses.cbreak()
            curses.curs_set(0)
        except Exception as exception:
            logger.warning(f"Failed to initialize curses: {exception}")
            curses_ui = False

        # if there is no curses support, like in the testing environment, just dump everything
        if not curses_ui:
            try:
                self.client.images.pull(f"{image_name}:{tag}")
            except Exception as exception:
                logger.warning(f"Failed to pull image ({image_name}:{tag}): {exception}")
            return

        # if there is ncurses support, proceed with it
        lines: int = 0
        # map each id to a line
        id_line: Dict[str, int] = {}
        try:
            for line in self.low_level_api.pull(f"{image_name}:{tag}", stream=True, decode=True):
                if len(line.keys()) == 1 and "status" in line:
                    # in some cases there is only "status", print that on the last line
                    screen.addstr(lines, 0, line["status"])
                    continue
                if "id" not in line:
                    continue
                layer_id = line["id"]
                if layer_id not in id_line:
                    id_line[layer_id] = lines
                    lines += 1
                status = line["status"]
                current_line = id_line[layer_id]
                if "progress" in line:
                    progress = line["progress"]
                    screen.addstr(current_line, 0, f"[{layer_id}]\t({status})\t{progress}")
                else:
                    screen.addstr(current_line, 0, f"[{layer_id}]\t({status})")

                screen.clrtoeol()
                screen.refresh()
        finally:
            curses.echo()
            curses.nocbreak()
            curses.endwin()
        logger.info("Done")

    def image_is_available_locally(self, image_name: str, tag: str) -> bool:
        """Checks if the image is already available locally"""
        try:
            images = self.client.images.list(image_name)
            return any(f"{image_name}:{tag}" in image.tags for image in images)
        except Exception as exception:
            logger.warning(f"Failed to list image ({image_name}): {exception}")
        return False

    def start(self, component_name: str) -> bool:
        """Loads settings and starts the containers. Loads default settings if no settings are found

        Args:
            component_name (str): one of our images names, such as "core", "bootstrap", or "ttyd"

        Returns:
            bool: True if successful
        """
        image_version = "stable"

        self.config = Bootstrapper.read_config_file()

        image = self.config[component_name]
        image_name = image["image"]
        image_version = image["tag"]
        docker_name = f"{image_name}:{image_version}"
        binds = image["binds"]
        privileged = image["privileged"]
        network = image["network"]
        environment = image.get("environment", [])

        if not self.image_is_available_locally(image_name, image_version):
            try:
                self.pull(component_name)
            except docker.errors.NotFound:
                warn(f"Image {image_name}:{image_version} not found, reverting to default...")
                self.overwrite_config_file_with_defaults()
                return False
            except docker.errors.APIError as error:
                warn(f"Error trying to pull an update image: {error}")
                return False

        logger.info(f"Starting {image_name}")
        # Remove image if name already exist
        self.remove(component_name)
        try:
            self.client.containers.run(
                docker_name,
                name=f"blueos-{component_name}",
                volumes=binds,
                privileged=privileged,
                network=network,
                detach=True,
                environment=environment,
                log_config={
                    "Type": "json-file",
                    "Config": {
                        "max-size": "30m",
                        "max-file": "3",
                    },
                },
            )
        except docker.errors.APIError as error:
            warn(f"Error trying to start image: {error}, reverting to default...")
            self.overwrite_config_file_with_defaults()
            return False

        logger.info(f"{component_name} ({docker_name}) started")
        # Restart counter with new core
        self.core_last_response_time = time.monotonic()
        return True

    def is_running(self, component: str) -> bool:
        """Checks if the container for a given component of blueos is running

        Args:
            component (str): component name ("core", "bootstrap", "ttyd", ...)

        Returns:
            bool: True if the chosen container is running
        """
        try:
            return any(container.name.endswith(component) for container in self.client.containers.list())
        except Exception as exception:
            logger.warning(f"Could not list containers: {exception}")
        return False

    def is_version_chooser_online(self) -> bool:
        """Check if the version chooser service is online.

        Returns:
            bool: True if version chooser is online, False otherwise.
        """
        try:
            response = requests.get("http://localhost/version-chooser/v1.0/version/current", timeout=10)
            if Bootstrapper.SETTINGS_NAME_CORE in response.json()["repository"]:
                if not self.version_chooser_is_online:
                    self.version_chooser_is_online = True
                    logger.info("Version chooser is online")
                return True
        except Exception as e:
            logger.warning(
                f"Could not talk to version chooser for {time.monotonic() - self.core_last_response_time}: {e}"
            )
        self.version_chooser_is_online = False
        return False

    def remove(self, container: str) -> None:
        """Deletes the chosen container if it exists (needed for updating the running image)"""
        try:
            old_container = self.client.containers.get(f"blueos-{container}")
            old_container.stop()
            old_container.remove()
        except docker.errors.NotFound:
            # This exception is raised if the container does not exist
            pass

    def run(self) -> None:
        """Runs the bootstrapper"""
        logger.info(f"Starting bootstrap {self.bootstrap_version()}")
        while True:
            time.sleep(5)
            for image in self.read_config_file():
                # Start image if it's not running
                if not self.is_running(image):
                    try:
                        if self.start(image):
                            logger.warning(f"{image} is not running, starting..")
                    except Exception as error:
                        logger.error(f"error: {type(error)}: {error}, retrying...")

                if image != Bootstrapper.SETTINGS_NAME_CORE:
                    continue

                if self.is_version_chooser_online():
                    self.core_last_response_time = time.monotonic()
                    continue

                # Check if version chooser failed start before timeout
                if time.monotonic() - self.core_last_response_time < 300:
                    continue

                # Version choose failed, time to restarted core
                self.core_last_response_time = time.monotonic()
                logger.warning("Core has not responded in 5 minutes, resetting to factory...")
                self.overwrite_config_file_with_defaults()
                try:
                    if self.start(image):
                        logger.info("Restarted core..")
                except Exception as error:
                    logger.error(f"error: {type(error)}: {error}, retrying...")

            # This is required for the tests, we need to "finish" somehow
            if "pytest" in sys.modules:
                return
