import json
import os
import pathlib
import shutil
import sys
import time
from typing import Any, Dict
from warnings import warn

import docker


class Bootstrapper:

    LOW_LEVEL_API = docker.APIClient(base_url="unix://var/run/docker.sock")
    DEFAULT_FILE_PATH = pathlib.Path("/bootstrap/startup.json.default")
    DOCKER_CONFIG_PATH = pathlib.Path("/root/.config/companion/startup.json")
    HOST_CONFIG_PATH = os.environ.get("COMPANION_CONFIG_PATH", None)
    CORE_CONTAINER_NAME = "companion_core"

    def __init__(self, client: docker.DockerClient) -> None:
        self.client: docker.DockerClient = client

    @staticmethod
    def ensure_dir(file_path: str) -> None:
        """Makes sure that the file path exists

        Args:
            file_path (str): path to check/make
        """
        directory = pathlib.Path(file_path)
        os.makedirs(directory, exist_ok=True)

    def stop_old_container(self) -> None:
        """ Looks for an old core container and stops it if found"""
        try:
            old_container = self.client.containers.get(Bootstrapper.CORE_CONTAINER_NAME)
            old_container.stop()
            old_container.remove()
        except docker.errors.NotFound:
            pass

    @staticmethod
    def overwrite_config_file_with_defaults() -> None:
        """Overwrites the config file with the default configuration"""
        shutil.copy(Bootstrapper.DEFAULT_FILE_PATH, Bootstrapper.DOCKER_CONFIG_PATH)

    @staticmethod
    def read_config_file() -> Dict[str, Any]:
        """Tries to read the config file

        Returns:
            Any: Json data of startup.json
        """

        # Tries to open the current file
        config = {}
        try:
            with open(Bootstrapper.DOCKER_CONFIG_PATH) as config_file:
                config = json.load(config_file)
        except FileNotFoundError as error:
            print(f"unable to read startup.json file ({error}), reverting to defaults...")
            # Copy defaults over and read again
            Bootstrapper.overwrite_config_file_with_defaults()
            with open(Bootstrapper.DEFAULT_FILE_PATH) as config_file:
                config = json.load(config_file)

        config["core"]["binds"][str(Bootstrapper.HOST_CONFIG_PATH)] = {
            "bind": str(Bootstrapper.DOCKER_CONFIG_PATH),
            "mode": "rw",
        }
        return config

    def start_core(self) -> None:
        """Loads core settings and launches the core docker. Loads default settings if no settings are found"""
        core_version = "stable"

        config = Bootstrapper.read_config_file()

        try:
            core = config["core"]
            image = core["image"]
            core_version = core["tag"]
            binds = core["binds"]
            privileged = core["privileged"]
            network = core["network"]

        except Exception as error:
            warn(f"Error reading startup json data! {error}")
            sys.exit(1)

        print("Attempting to pull an updated image... This might take a while...")
        try:
            for line in Bootstrapper.LOW_LEVEL_API.pull(f"{image}:{core_version}", stream=True, decode=True):
                print(line["status"])
        except docker.errors.APIError as error:
            warn(f"Error trying to pull an update image: {error}")

        print("Starting core")
        self.client.containers.run(
            f"{image}:{core_version}",
            name=Bootstrapper.CORE_CONTAINER_NAME,
            volumes=binds,
            privileged=privileged,
            network=network,
            detach=True,
        )
        print("Core started")

    def core_is_running(self) -> bool:
        """
        Returns:
            bool: True if the core container is running
        """
        for container in self.client.containers.list():
            if Bootstrapper.CORE_CONTAINER_NAME in container.name:
                return True
        return False

    def remove_core(self) -> None:
        """Deletes the core container if it exists (needed for updating the running image)"""
        try:
            old_container = self.client.containers.get(Bootstrapper.CORE_CONTAINER_NAME)
            old_container.remove()
        except docker.errors.NotFound:
            # This exception is raised if the container does not exist
            pass

    def run(self) -> None:
        """Runs the bootstrapper"""
        while True:
            if self.core_is_running():
                print("core is already running, waiting for it to stop...")
                time.sleep(1)
            else:
                try:
                    self.remove_core()
                    self.start_core()
                    print("Done")
                    return
                except Exception as error:
                    warn(f"error: {error}, retrying...")
            time.sleep(1)
