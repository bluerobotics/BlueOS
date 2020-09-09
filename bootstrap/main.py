#!/usr/bin/env python3

import json
import os
import pathlib
import shutil
import sys
import time
from typing import Any
from warnings import warn

import docker

client = docker.from_env()
low_level_api = docker.APIClient(base_url="unix://var/run/docker.sock")

DEFAULT_FILE_PATH = pathlib.Path("/bootstrap/startup.json.default")
DOCKER_CONFIG_PATH = pathlib.Path("/root/.config/companion/startup.json")

HOST_CONFIG_PATH = os.environ.get("COMPANION_CONFIG_PATH", None)

CORE_CONTAINER_NAME = "companion_core"


def ensure_dir(file_path: str) -> None:
    """Makes sure that the file path exists

    Args:
        file_path (str): path to check/make
    """
    directory = pathlib.Path(file_path).parent
    os.makedirs(directory, exist_ok=True)


def stop_old_container() -> None:
    """ Looks for an old core container and stops it if found"""
    try:
        old_container = client.containers.get(CORE_CONTAINER_NAME)
        old_container.stop()
        old_container.remove()
    except docker.errors.NotFound:
        pass


def overwrite_config_file_with_defaults() -> None:
    """Overwrites the config file with the default configuration"""
    shutil.copy(DEFAULT_FILE_PATH, DOCKER_CONFIG_PATH)


def read_config_file() -> Any:
    """Tries to read the config file

    Returns:
        Any: Json data of startup.json
    """

    # Tries to open the current file
    config = {}
    try:
        with open(DOCKER_CONFIG_PATH) as config_file:
            config = json.load(config_file)
    except Exception as error:
        warn(f"unable to read startup.json file ({type(error).__name__}:{error}), reverting to defaults...")
        # Copy defaults over and read again
        overwrite_config_file_with_defaults()
        with open(DEFAULT_FILE_PATH) as config_file:
            config = json.load(config_file)

    config["core"]["binds"][str(HOST_CONFIG_PATH)] = {
        "bind": str(DOCKER_CONFIG_PATH),
        "mode": "rw",
    }
    return config


def start_core() -> None:
    """Loads core settings and launches the core docker. Loads default settings if no settings are found"""
    core_version = "stable"

    config = read_config_file()

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
        for line in low_level_api.pull(f"{image}:{core_version}", stream=True, decode=True):
            print(line["status"])
    except docker.errors.APIError as error:
        warn("Error trying to pull an update image: {error}")

    print("Starting core")
    client.containers.run(
        f"{image}:{core_version}",
        name=CORE_CONTAINER_NAME,
        volumes=binds,
        privileged=privileged,
        network=network,
        detach=True,
    )
    print("Core started")


def core_is_running() -> bool:
    """
    Returns:
        bool: True if the core container is running
    """
    for container in client.containers.list():
        if CORE_CONTAINER_NAME in container.name:
            return True
    return False


def remove_core() -> None:
    """Deletes the core container if it exists (needed for updating the running image)"""
    try:
        old_container = client.containers.get(CORE_CONTAINER_NAME)
        old_container.remove()
    except docker.errors.NotFound:
        # This exception is raised if the container does not exist
        pass


if __name__ == "__main__":
    if HOST_CONFIG_PATH is None:
        print("Please supply the host path for the config files as the COMPANION_CONFIG_PATH environment variable.")
        print("Example docker command line:")
        print(
            "docker run -it -v /var/run/docker.sock:/var/run/docker.sock -v $HOME/.config/companion:"
            "/root/.config/companion -e COMPANION_CONFIG_PATH=$HOME/.config/companion  bluerobotics/bootstrap:master"
        )
        sys.exit(1)

    while True:
        if core_is_running():
            print("core is already running, waiting for it to stop...")
            time.sleep(1)
        else:
            try:
                remove_core()
                start_core()
                print("Done")
                sys.exit(0)
            except Exception as error:
                warn(f"error: {error}, retrying...")
        time.sleep(1)
