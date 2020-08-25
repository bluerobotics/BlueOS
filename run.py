#!/usr/bin/env python3

import json
import docker
import pathlib
import os


def ensure_dir(file_path: str) -> None:
    """Makes sure that the file path exists

    Args:
        file_path (str): path to check/make
    """
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)


ensure_dir("/tmp/wpa_playground")

supervisor_version = "latest"
binds = {}
ports = {}
current_folder = pathlib.Path(__file__).parent.absolute()

try:
    with open("config/dockers.json") as f:
        data = f.read().replace("{PWD}", str(current_folder))
        dockers_config = json.loads(data)
        supervisor_version = dockers_config["dockers"]["supervisor"]["tag"]
        binds = dockers_config["dockers"]["supervisor"]["binds"]
        ports = dockers_config["dockers"]["supervisor"]["ports"]
except Exception as error:
    print(f"unable to get version from file, using latest ({error})")

client = docker.from_env()

try:
    old_container = client.containers.get("companion_supervisor")
    old_container.stop()
    old_container.remove()
except Exception as e:
    pass

client.containers.run(f'bluerobotics/supervisor:{supervisor_version}',
                      name="companion_supervisor",
                      volumes=binds,
                      ports=ports,
                      detach=True)
print("All done, open http://localhost:8080")
# /var/run/docker.sock:/var/run/docker.sock -v /home/pi/git/companion-docker/config:/home/companion/.config
