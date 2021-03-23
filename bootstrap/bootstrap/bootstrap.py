import curses
import json
import os
import pathlib
import shutil
import time
from typing import Any, Dict
from warnings import warn

import docker


class Bootstrapper:

    DEFAULT_FILE_PATH = pathlib.Path("/bootstrap/startup.json.default")
    DOCKER_CONFIG_PATH = pathlib.Path("/root/.config")
    DOCKER_CONFIG_FILE_PATH = DOCKER_CONFIG_PATH.joinpath("bootstrap/startup.json")
    HOST_CONFIG_PATH = os.environ.get("COMPANION_CONFIG_PATH", "/tmp/companion/.config")
    CORE_CONTAINER_NAME = "companion-core"

    def __init__(self, client: docker.DockerClient, low_level_api: docker.APIClient = None) -> None:
        self.client: docker.DockerClient = client
        if low_level_api is None:
            self.low_level_api = docker.APIClient(base_url="unix://var/run/docker.sock")
        else:
            self.low_level_api = low_level_api

    @staticmethod
    def overwrite_config_file_with_defaults() -> None:
        """Overwrites the config file with the default configuration"""
        try:
            shutil.copy(
                Bootstrapper.DOCKER_CONFIG_FILE_PATH, Bootstrapper.DOCKER_CONFIG_FILE_PATH.with_suffix(".json.bak")
            )
        except FileNotFoundError:
            # we don't mind if the file is already there
            pass
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
            with open(Bootstrapper.DOCKER_CONFIG_FILE_PATH) as config_file:
                config = json.load(config_file)
                assert "core" in config, "missing core entry in startup.json"
                necessary_keys = ["image", "tag", "binds", "privileged", "network"]
                for key in necessary_keys:
                    assert key in config["core"], f"missing key in json file: {key}"

        except (FileNotFoundError, AssertionError) as error:
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

    def pull_core(self) -> None:

        core = self.config["core"]
        image = core["image"]
        tag = core["tag"]

        curses_ui = True
        try:
            # TODO: make it not clear the whole screen
            screen = curses.initscr()
            curses.noecho()
            curses.cbreak()
            curses.curs_set(0)
        except Exception:
            curses_ui = False

        # if there is no curses support, like in the testing environment, just dump everything
        if not curses_ui:
            self.client.images.pull(f"{image}:{tag}")
            return

        # if there is ncurses support, proceed with it
        lines: int = 0
        # map each id to a line
        id_line: Dict[str, int] = {}
        try:
            for line in self.low_level_api.pull(f"{image}:{tag}", stream=True, decode=True):
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
        print("Done")

    def start_core(self) -> bool:
        """Loads core settings and launches the core docker. Loads default settings if no settings are found"""
        core_version = "stable"

        self.config = Bootstrapper.read_config_file()

        core = self.config["core"]
        image = core["image"]
        core_version = core["tag"]
        binds = core["binds"]
        privileged = core["privileged"]
        network = core["network"]

        print("Attempting to pull an updated image... This might take a while...")
        try:
            self.pull_core()
        except docker.errors.ImageNotFound:
            warn("Image not found, reverting to default...")
            self.overwrite_config_file_with_defaults()
            return False
        except docker.errors.APIError as error:
            warn(f"Error trying to pull an update image: {error}")

        print("Starting core")
        try:
            self.client.containers.run(
                f"{image}:{core_version}",
                name=Bootstrapper.CORE_CONTAINER_NAME,
                volumes=binds,
                privileged=privileged,
                network=network,
                detach=True,
            )
        except docker.errors.APIError as error:
            warn(f"Error trying to start image: {error}, reverting to default...")
            self.overwrite_config_file_with_defaults()
            return False

        print("Core started")
        return True

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
                    if self.start_core():
                        print("Done")
                        return
                except Exception as error:
                    warn(f"error: {type(error)}: {error}, retrying...")
            time.sleep(1)
