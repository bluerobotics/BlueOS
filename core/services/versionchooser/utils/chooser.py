import json
import pathlib
import sys
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import aiodocker
import appdirs
import docker
from aiohttp import web
from loguru import logger

from utils.dockerhub import TagFetcher

DOCKER_CONFIG_PATH = pathlib.Path(appdirs.user_config_dir("bootstrap"), "startup.json")

current_folder = pathlib.Path(__file__).parent.parent.absolute()
# Folder for static files (mostly css/js)
FRONTEND_FOLDER = pathlib.Path.joinpath(current_folder, "frontend")
STATIC_FOLDER = pathlib.Path.joinpath(FRONTEND_FOLDER, "static")


class VersionChooser:
    def __init__(self, client: aiodocker.Docker):
        self.client = client
        self.cleanup()
        self.bootstrap_name = "blueos-bootstrap"

    @staticmethod
    def cleanup() -> None:
        if "pytest" in sys.modules:  # don't run this in testing environment
            return
        # TODO: migrate this to aiodocker once https://github.com/aio-libs/aiodocker/issues/696 is fixed
        client = docker.from_env()
        client.images.prune({"dangling": True})

    @staticmethod
    def index() -> web.FileResponse:
        """Serve index.html"""
        return web.FileResponse(str(FRONTEND_FOLDER) + "/index.html", headers={"cache-control": "no-cache"})

    @staticmethod
    def get_current_image_and_tag() -> Optional[Tuple[str, str]]:
        with open(DOCKER_CONFIG_PATH, encoding="utf-8") as startup_file:
            try:
                core = json.load(startup_file)["core"]
                tag = core["tag"]
                image = core["image"]
                return image, tag
            except KeyError as error:
                logger.warning(f"Invalid version file: {error}")
            except Exception as e:
                logger.warning(f"Unable to load settings file: {e}")
        return None

    async def get_version(self) -> web.Response:
        """Fetches current version from config file

        Returns:
            web.Response: json with image name, tag, last modification date,
            sha and architecture of the image
        """
        version = self.get_current_image_and_tag()
        if version is None:
            return web.Response(status=500, text="Unable to load current version from settings. Check the log")
        image_name, tag = version
        full_name = f"{image_name}:{tag}"
        image = await self.client.images.get(full_name)
        output = {
            "repository": image_name,
            "tag": tag,
            "last_modified": image["Created"],
            "sha": image["Id"],
            "architecture": image["Architecture"],
        }
        return web.json_response(output)

    async def load(self, data: bytes) -> web.Response:
        """Load a docker image file.

        Args:
            data (bytes): Tar file from `docker save` output

        Returns:
            web.Response:
                200 - OK
                400 - Error while processing data
                500 - Internal server error while processing docker import image
                501 - Failed to handle docker result
        """
        response = {}
        try:
            # import_image only returns a single line
            response_list = await self.client.images.import_image(data)
            response = response_list[0]
        except Exception as error:
            logger.critical(f"Error: {type(error)}: {error}")
            return web.Response(status=500, text=f"Error: {type(error)}: {error}")

        if "errorDetail" in response:
            return web.Response(status=500, text=response["errorDetail"]["message"])
        if "stream" in response:
            return web.json_response(response)

        return web.Response(status=501, text=f"Response: {response}")

    async def is_valid_version(self, image: str) -> Tuple[bool, str]:
        """
        Check if the image exists locally.

        Args:
            image (str): the repository of the image

        Returns:
            Tuple[bool, str]: (True, image) if the image exists, (False, error_msg) otherwise
        """

        try:
            await self.client.images.inspect(image)

            return True, image
        except Exception:
            error_msg = (
                f"Trying to update to {image} but this image doesn't exist locally. "
                + "Please pull this image before trying to update the container image."
            )
            logger.critical(error_msg)
            return False, error_msg

    async def pull_version(self, request: web.Request, repository: str, tag: str) -> web.StreamResponse:
        """Applies a new version.

        Pulls the image from dockerhub, streaming the output as a StreamResponse

        Args:
            request (web.Request): http request from aiohttp
            repository (str): name of the image, such as bluerobotics/blueos-core
            tag (str): image tag

        Returns:
            web.StreamResponse: Streams the 'docker pull' output
        """
        response = web.StreamResponse()
        response.headers["Content-Type"] = "application/x-www-form-urlencoded"
        # This step actually starts the chunked response
        await response.prepare(request)

        # Stream every line of the output back to the client
        try:
            async for line in self.client.images.pull(f"{repository}:{tag}", repo=repository, tag=tag, stream=True):
                await response.write(json.dumps(line).encode("utf-8"))
        except Exception as e:
            logger.error(f"pull of {repository}:{tag}  failed: {e}")
            await response.write(json.dumps({"error": f"error while pulling image: {e}"}).encode("utf-8"))
        await response.write_eof()
        # TODO: restore pruning
        return response

    async def get_bootstrap_version(self) -> str:
        """Get the current bootstrap container image version.

        Retrieves the bootstrap container and returns the image version
        from the container configuration.

        Returns:
            str: The image version string for the bootstrap container.
        """
        try:
            bootstrap = await self.client.containers.get(self.bootstrap_name)  # type: ignore
            return str(bootstrap["Config"]["Image"])
        except Exception as e:
            logger.critical(f"unable to read bootstrap version: {e}")
            return "Unknown"

    async def set_bootstrap_version(self, tag: str) -> web.StreamResponse:
        """Set the bootstrap container to a new version.

        Stops the current bootstrap container, renames it to a backup,
        creates a new bootstrap container with the provided image tag,
        starts the new container, and returns a response.

        Args:
            tag (str): The image tag for the new bootstrap container.

        Returns:
            web.StreamResponse: Response indicating success.
        """

        bootstrap = None
        logger.info(f"Setting new bootstrap version: {tag}")
        try:
            bootstrap = await self.client.containers.get(self.bootstrap_name)  # type: ignore
            logger.info("Got bootstrap..")
        except Exception as error:
            logger.critical(f"Warning: {type(error)}: {error}")

        new_image_name = f"bluerobotics/blueos-bootstrap:{tag}"

        image_check = await self.is_valid_version(new_image_name)
        if not image_check[0]:
            return web.Response(status=412, text=image_check[1])

        backup_name = "bootstrap-backup"
        try:
            backup = None
            backup = await self.client.containers.get(backup_name)  # type: ignore
            logger.info(f"Got {backup_name}, going to delete and create a new one..")
            # We are going to remove backup even if it's running somehow
            await backup.delete(force=True, noprune=False)  # type: ignore
        except Exception as error:
            logger.critical(f"Warning: {type(error)}: {error}")

        if bootstrap:
            logger.info(f"Setting current {await self.get_bootstrap_version()} as {backup_name}")
            await bootstrap.rename(backup_name)
            logger.info(f"Stop {self.bootstrap_name}")
            await bootstrap.kill()
            result = await bootstrap.wait()  # type: ignore
            logger.info(f"Response after waiting for {self.bootstrap_name} to be stopped: {result}")

        HOME = "/root"
        bootstrap_config = {
            "Image": new_image_name,
            "HostConfig": {
                "RestartPolicy": {"Name": "unless-stopped"},
                "NetworkMode": "host",
                "Binds": [
                    f"{HOME}/.config/blueos/bootstrap:/root/.config/bootstrap",
                    "/var/run/docker.sock:/var/run/docker.sock",
                    "/var/logs/blueos:/var/logs/blueos",
                ],
                "LogConfig": {
                    "Type": "json-file",
                    "Config": {"max-size": "30m", "max-file": "3"},
                },
            },
            "Env": [f"BLUEOS_CONFIG_PATH={HOME}/.config/blueos"],
        }

        container = await self.client.containers.create(bootstrap_config, name=self.bootstrap_name)  # type: ignore
        await container.start()
        logger.info(f"Bootstrap updated to {bootstrap_config['Image']}")
        return web.Response(status=200, text=f"Bootstrap update to {tag}")

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

        image_check = await self.is_valid_version(f"{image}:{tag}")
        if not image_check[0]:
            return web.Response(status=412, text=image_check[1])

        with open(DOCKER_CONFIG_PATH, "r+", encoding="utf-8") as startup_file:
            try:
                data = json.load(startup_file)
                data["core"]["image"] = image
                data["core"]["tag"] = tag

                # overwrite file contents
                startup_file.seek(0)
                startup_file.write(json.dumps(data, indent=2))
                startup_file.truncate()

                logger.info("Stopping core...")
                core = await self.client.containers.get("blueos-core")  # type: ignore
                if core:
                    await core.kill()
                    result = await core.wait()  # type: ignore
                    logger.info(f"Response after waiting for core to be killed: {result}")
                return web.Response(status=200, text=f"Changed to version {image}:{tag}, restarting...")

            except KeyError:
                return web.Response(status=500, text="Invalid version file")

            except Exception as error:
                logger.critical(f"Error: {type(error)}: {error}")
                return web.Response(status=500, text=f"Error: {type(error)}: {error}")

    async def delete_version(self, image: str, tag: str) -> web.StreamResponse:
        """Deletes the selected version.

        Args:
            image (str): the repository of the image
            tag (str): the desired tag

        Returns:
            web.Response:
                200 - OK
                400 - Invalid image/tag
                403 - image cannot be deleted
                500 - Internal error (unable to read config file/docker refused to delete image)
        """
        full_name = f"{image}:{tag}"
        # refuse if it is the current image
        if (image, tag) == self.get_current_image_and_tag():
            return web.Response(status=500, text=f"Image {full_name} is in use and cannot be deleted.")
        # check if image exists
        try:
            await self.client.images.get(full_name)
        except Exception as error:
            logger.warning(f"Image not found: {full_name} ({error})")
            return web.Response(status=404, text=f"image '{full_name}' not found ({error})")

        # actually attempt to delete it
        logger.info(f"Deleting image {image}:{tag}...")
        try:
            await self.client.images.delete(full_name, force=True, noprune=False)
            logger.info("Image deleted successfully")
            return web.Response(status=200)
        except Exception as e:
            logger.warning(f"Error deleting image: {e}")
            return web.Response(status=500, text=f"Unable do delete image: {e}")

    async def set_local_versions(self, output: Dict[str, Optional[Union[str, List[Dict[str, Any]]]]]) -> None:
        for image in await self.client.images.list():
            if not image["RepoTags"]:
                continue
            if not any("/blueos-core:" in tag for tag in image["RepoTags"]):
                continue
            for image_tag in image["RepoTags"]:
                image_repository, tag = image_tag.split(":")
                assert isinstance(output["local"], list)
                output["local"].append(
                    {
                        "repository": image_repository,
                        "tag": tag,
                        "last_modified": datetime.fromtimestamp(image["Created"]).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "sha": image["Id"],
                    }
                )

    async def set_remote_versions(
        self, output: Dict[str, Optional[Union[str, List[Dict[str, Any]]]]], repository: str
    ) -> None:
        try:
            assert isinstance(output["local"], list)
            output["error"], online_tags = await TagFetcher().fetch_remote_tags(
                repository, [image["tag"] for image in output["local"]]
            )
        except Exception as error:
            logger.critical(f"error fetching online tags: {error}")
            online_tags = []
            output["error"] = f"error fetching online tags: {error}"
        assert isinstance(output["remote"], list)
        output["remote"].extend([asdict(tag) for tag in online_tags])

    async def get_available_local_versions(self) -> web.Response:
        output: Dict[str, Optional[Union[str, List[Dict[str, Any]]]]] = {"local": [], "error": None}
        await self.set_local_versions(output)
        return web.json_response(output)

    async def get_available_versions(self, repository: str) -> web.Response:
        """Returns versions available locally and in the remote

        Args:
            repository (str): repository name (such as bluerobotics/blueos-core)
            tag (str): tag (such as "master" or "latest")

        Returns:
            web.Response: json described in the openapi file
        """
        output: Dict[str, Optional[Union[str, List[Dict[str, Any]]]]] = {"local": [], "remote": [], "error": None}
        await self.set_local_versions(output)
        await self.set_remote_versions(output, repository)
        return web.json_response(output)

    async def restart(self) -> web.Response:
        """Returns versions available locally and in the remote
        Returns:
            web.Response: always 200
        """
        logger.info("Stopping core...")
        core = await self.client.containers.get("blueos-core")  # type: ignore
        await core.kill()
        return web.Response(status=200, text="Restarting...")
