#!/usr/bin/env python3
"""
Responsible for interacting with dockerhub
adapted from https://github.com/al4/docker-registry-list
"""

import platform
from dataclasses import dataclass
from typing import List, Optional, Tuple
from warnings import warn

import aiohttp
from loguru import logger


def get_current_arch() -> str:
    """Maps platform.machine() outputs to docker architectures"""
    arch_map = {"x86_64": "amd64", "aarch64": "arm64", "armv7l": "arm"}
    machine = platform.machine()
    arch = arch_map.get(machine, None)
    if not arch:
        raise RuntimeError(f"Unknown architecture! {machine}")
    return arch


@dataclass
class TagMetadata:
    """Class for keeping track of an item in inventory."""

    repository: str
    image: str
    tag: str
    last_modified: str
    sha: Optional[str]
    digest: str


class TagFetcher:
    """Fetches remote tags for a given image"""

    index_url: str = "https://index.docker.io"
    docker_url: str = "https://hub.docker.com/"

    @staticmethod
    async def _get_token(auth_url: str, image_name: str) -> str:
        """[summary]
        Gets a token for dockerhub.com
        Args:
            auth_url: authentication url, default to https://auth.docker.io
            image_name: image name, for example "bluerobotics/core"

        Raises:
            Exception: Raised if unable to get the token

        Returns:
            The token
        """
        payload = {
            "service": "registry.docker.io",
            "scope": f"repository:{image_name}:pull",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(auth_url + "/token", params=payload) as resp:
                if resp.status != 200:
                    warn(f"Error status {resp.status}")
                    raise RuntimeError("Could not get auth token")
                return str((await resp.json(content_type=None))["token"])

    async def fetch_sha(self, metadata: TagMetadata) -> str:
        """Fetches the digest sha from a tag. This returns the image id displayed by 'docker image ls'"""
        header = {
            "Authorization": f"Bearer {self.last_token}",
            "Accept": "application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.manifest.v1+json",
        }
        async with aiohttp.ClientSession() as session:
            url = f"{self.index_url}/v2/{metadata.repository}/manifests/{metadata.digest}"
            async with session.get(url, headers=header) as resp:
                if resp.status != 200:
                    warn(f"Error status {resp.status}")
                    raise RuntimeError(
                        f"Failed getting sha from DockerHub at {url} : {resp.status} : {await resp.text()}"
                    )
                data = await resp.json(content_type=None)
                return str(data["config"]["digest"])

    async def fetch_remote_tags(self, repository: str, local_images: List[str]) -> Tuple[str, List[TagMetadata]]:
        """Fetches the tags available for an image in DockerHub"""
        logger.info("fetching", repository)
        errors = []
        self.last_token = await self._get_token(auth_url="https://auth.docker.io", image_name=repository)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.docker_url}/v2/repositories/{repository}/tags/?page_size=200&page=1&ordering=last_updated"
            ) as resp:
                if resp.status != 200:
                    warn(f"Error status {resp.status}")
                    raise RuntimeError("Failed getting tags from DockerHub!")
                data = await resp.json(content_type=None)
                tags = data["results"]

                my_architecture = get_current_arch()
                valid_images = []
                for tag in tags:
                    for image in tag["images"]:
                        if image["architecture"] == my_architecture:
                            tag = TagMetadata(
                                repository=repository,
                                image=repository.split("/")[-1],
                                tag=tag["name"],
                                last_modified=image["last_pushed"],
                                sha=None,
                                digest=image["digest"],
                            )
                            if tag.tag in local_images:
                                try:
                                    tag.sha = await self.fetch_sha(tag)
                                except Exception as new_error:
                                    if str(new_error) not in errors:
                                        errors.append(str(f"Error fetching sha for {tag}: {new_error}"))
                            valid_images.append(tag)
                return "\n".join(errors), valid_images
