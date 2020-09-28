import json
import logging
import pathlib
from dataclasses import asdict
from typing import Dict, List

import appdirs
import docker
from aiohttp import web
from utils.dockerhub import TagFetcher

DOCKER_CONFIG_PATH = pathlib.Path(appdirs.user_config_dir("bootstrap"), "startup.json")

current_folder = pathlib.Path(__file__).parent.parent.absolute()
# Folder for static files (mostly css/js)
STATIC_FOLDER = pathlib.Path.joinpath(current_folder, "static")

logging.basicConfig(level=logging.INFO)


class VersionChooser:
    def __init__(self, client: docker.DockerClient):
        self.client = client

    @staticmethod
    def index() -> web.FileResponse:
        """Serve index.html"""
        return web.FileResponse(str(STATIC_FOLDER) + "/index.html", headers={"cache-control": "no-cache"})

    def get_version(self) -> web.Response:
        """Fetches current version from config file

        Returns:
            web.Response: json with image name, tag, last modification date,
            sha and architecture of the image
        """
        with open(DOCKER_CONFIG_PATH) as startup_file:
            try:
                core = json.load(startup_file)["core"]
                tag = core["tag"]
                image_name = core["image"]
                full_name = f"{image_name}:{tag}"
                image = self.client.images.get(full_name)
                output = {
                    "repository": image_name,
                    "tag": tag,
                    "last_modified": image.attrs["Created"],
                    "sha": image.id,
                    "architecture": image.attrs["Architecture"],
                }
                return web.json_response(output)
            except KeyError as error:
                return web.Response(status=500, text=f"Invalid version file: {error}")
            except Exception as error:
                return web.Response(status=500, text=f"Error: {type(error)}: {error}")

    @staticmethod
    def is_valid_version(_repository: str, _tag: str) -> bool:
        # TODO implement basic validation
        return True

    async def pull_version(self, request: web.Request, repository: str, tag: str) -> web.StreamResponse:
        """Applies a new version.

        Pulls the image from dockerhub, streaming the output as a StreamResponse

        Args:
            request (web.Request): http request from aiohttp
            repository (str): name of the image, such as bluerobotics/companion-core
            tag (str): image tag

        Returns:
            web.StreamResponse: Streams the 'docker pull' output
        """
        response = web.StreamResponse()
        response.headers["Content-Type"] = "application/x-www-form-urlencoded"
        # This step actually starts the chunked response
        await response.prepare(request)

        low_level_api = docker.APIClient(base_url="unix://var/run/docker.sock")
        # Stream every line of the output back to the client
        for line in low_level_api.pull(f"{repository}:{tag}", stream=True, decode=True):
            await response.write(f"{line}\n\n".replace("'", '"').encode("utf-8"))
        await response.write_eof()
        return response

    async def set_version(self, image: str, tag: str) -> web.StreamResponse:
        """Sets the current version.

        Sets the version in startup.json()

        Args:
            image (str): the repository of the image
            tag (str): the desired tag

        Returns:
            web.Response:
                200 - OK
                400 - Invalid image/tag
                500 - Invalid settings file/Other internal error
        """
        if not self.is_valid_version(image, tag):
            return web.Response(status=400, text="Invalid version")

        with open(DOCKER_CONFIG_PATH, "r+") as startup_file:
            try:
                data = json.load(startup_file)
                data["core"]["image"] = image
                data["core"]["tag"] = tag

                # overwrite file contents
                startup_file.seek(0)
                startup_file.write(json.dumps(data, indent=2))
                startup_file.truncate()

                logging.info("Starting bootstrap...")
                bootstrap = self.client.containers.get("companion-bootstrap")
                bootstrap.start()

                logging.info("Stopping core...")
                core = self.client.containers.get("companion-core")
                core.kill()
                return web.Response(status=200, text=f"Changed to version {image}:{tag}, restarting...")

            except KeyError:
                return web.Response(status=500, text="Invalid version file")

            except Exception as error:
                logging.critical("Error: %s: %s", type(error), error)
                return web.Response(status=500, text=f"Error: {type(error)}: {error}")

    async def get_available_versions(self, repository: str) -> web.Response:
        """Returns versions available locally and in the remote

        Args:
            repository (str): repository name (such as bluerobotics/companion-core)
            tag (str): tag (such as "master" or "latest")

        Returns:
            web.Response: json described in the openapi file
        """
        output: Dict[str, List[Dict[str, str]]] = {"local": [], "remote": []}
        for image in self.client.images.list():
            if not any("companion-core" in tag for tag in image.tags):
                continue
            for image_tag in image.tags:
                image_repository, tag = image_tag.split(":")
                output["local"].append(
                    {
                        "repository": image_repository,
                        "tag": tag,
                        "last_modified": image.attrs["Created"],
                        "sha": image.id,
                        "architecture": image.attrs["Architecture"],
                    }
                )
        try:
            online_tags = await TagFetcher().fetch_remote_tags(repository)
        except Exception as error:
            logging.critical("error fetching online tags: %s", error)
            online_tags = []
        output["remote"].extend([asdict(tag) for tag in online_tags])

        return web.json_response(output)
