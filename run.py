#!/usr/bin/env python3

import json
import pathlib
import os
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
    try:
        old_container = client.containers.get("companion_supervisor")
        old_container.stop()
        old_container.remove()
    except Exception:
        pass


def start_supervisor() -> None:
    supervisor_version = "stable"
    binds = {}
    ports = {}
    current_folder = pathlib.Path(__file__).parent.absolute()

    try:
        with open("config/dockers.json") as config_file:
            data = config_file.read().replace("{PWD}", str(current_folder))
            dockers_config = json.loads(data)
            supervisor_version = dockers_config["dockers"]["supervisor"]["tag"]
            binds = dockers_config["dockers"]["supervisor"]["binds"]
            ports = dockers_config["dockers"]["supervisor"]["ports"]
    except Exception:
        binds = {
            os.path.join(current_folder, "/config"): {
                "bind": "/supervisor/.config",
                "mode": "rw"
            }
        }
        ensure_dir("config")
    print("Started, open http://localhost:8080")

    client.containers.run(f'williangalvani/supervisor:{supervisor_version}',
                          name="companion_supervisor",
                          volumes=binds,
                          ports=ports,
                          detach=False)


while True:
    stop_old_container()
    try:
        start_supervisor()
    except Exception as error:
        print(f"error: {error}, restarting...")

    time.sleep(1)
