#!/usr/bin/env python3

import json
import os
import pathlib
import shutil
import sys
import time

import docker

client = docker.from_env()


def ensure_dir(file_path: str) -> None:
    """Makes sure that the file path exists

    Args:
        file_path (str): path to check/make
    """
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)


def stop_old_container() -> None:
    """ Looks for an old supervisor container and stops it if found"""
    try:
        old_container = client.containers.get("companion_supervisor")
        old_container.stop()
        old_container.remove()
    except Exception:
        pass


def start_supervisor() -> None:
    """Loads suppervisor settings and launches the supervisor docker. Loads default settings if no settings are found"""
    supervisor_version = "stable"
    binds = {}
    ports = {}

    default_file_path = pathlib.Path("/dockers.json.default")
    config_file_path = pathlib.Path("/config/dockers.json")

    if not config_file_path.exists():
        shutil.copy(default_file_path, config_file_path)

    try:
        with open("/config/dockers.json") as config_file:
            data = config_file.read()
            dockers_config = json.loads(data)
            supervisor_version = dockers_config["dockers"]["supervisor"]["tag"]
            binds = dockers_config["dockers"]["supervisor"]["binds"]
            ports = dockers_config["dockers"]["supervisor"]["ports"]
    except Exception as error:
        print(f"ERROR! {error}")

    client.containers.run(f'williangalvani/supervisor:{supervisor_version}',
                          name="companion_supervisor",
                          volumes=binds,
                          ports=ports,
                          detach=True)
    print("Started, open http://localhost:8080")


def supervisor_is_running() -> bool:
    """
    Returns:
        bool: True if the supervisor container is running
    """
    for container in client.containers.list():
        if "supervisor" in container.name:
            return True
    return False


def remove_supervisor() -> None:
    """Deletes the supervisor container if it exists (needed for updating the running image)"""
    try:
        old_container = client.containers.get("companion_supervisor")
        old_container.remove()
    except Exception:
        pass


if __name__ == "__main__":
    while True:
        if supervisor_is_running():
            print("Supervisor is already running, waiting for it to stop...")
            time.sleep(1)
        else:
            try:
                remove_supervisor()
                start_supervisor()
                sys.exit(0)
            except Exception as error:
                print(f"error: {error}, restarting...")
        time.sleep(1)
    sys.exit(0)
