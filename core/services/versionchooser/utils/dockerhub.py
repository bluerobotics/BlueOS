#!/usr/bin/env python3
"""
Responsible for interacting with dockerhub
adapted from https://github.com/al4/docker-registry-list
"""

import asyncio
import platform
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Any, List, Optional, Tuple
from warnings import warn

import aiohttp
from loguru import logger

RETRY_ATTEMPTS = 3
DNS_FAILURE_MESSAGE = (
    "Cannot resolve Docker Hub. The vehicle can still reach the internet by IP. "
    "Check DNS nameservers under Network, or use Manual Upload."
)


def get_current_arch() -> str:
    """Maps platform.machine() outputs to docker architectures"""
    machine = platform.machine()

    match machine:
        case "armv7l":
            return "arm"
        case "x86_64" | "amd64":
            return "amd64"
        case "aarch64" | "arm64":
            # catch the case of 64 bit kernel with 32bit userland on Pi 5
            if platform.architecture()[0] == "32bit":
                return "arm"
            return "arm64"
        case _:
            raise RuntimeError(f"Unknown architecture! {machine}")


def is_name_resolution_error(error: BaseException) -> bool:
    if isinstance(error, socket.gaierror):
        return True
    return isinstance(getattr(error, "os_error", None), socket.gaierror)


def remote_tags_error_message(error: BaseException) -> str:
    if is_name_resolution_error(error):
        return DNS_FAILURE_MESSAGE
    return f"error fetching online tags: {error}"


# getaddrinfo is not cancellable. Cap threads so leftover AAAA cannot fill the default pool.
_HUB_DNS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hub-dns")
_DNS_FAMILY_TIMEOUT_S = 2.0


class _FamilyRaceResolver(aiohttp.abc.AbstractResolver):
    """Resolve AF_INET and AF_INET6 in parallel. Keep every family that answers."""

    async def _resolve_family(self, host: str, port: int, family: int) -> List[Any]:
        loop = asyncio.get_running_loop()
        infos = await loop.run_in_executor(
            _HUB_DNS,
            partial(socket.getaddrinfo, host, port, family, socket.SOCK_STREAM, socket.IPPROTO_TCP),
        )
        hosts: List[Any] = []
        for address_family, _type, proto, _name, address in infos:
            hosts.append(
                {
                    "hostname": host,
                    "host": address[0],
                    "port": address[1],
                    "family": address_family,
                    "proto": proto,
                    "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
                }
            )
        return hosts

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC) -> List[Any]:
        if family != socket.AF_UNSPEC:
            return await self._resolve_family(host, port, family)

        last_error: Optional[BaseException] = None

        async def lookup(fam: int) -> List[Any]:
            nonlocal last_error
            try:
                return await asyncio.wait_for(
                    self._resolve_family(host, port, fam),
                    timeout=_DNS_FAMILY_TIMEOUT_S,
                )
            except OSError as error:
                last_error = error
                return []

        v4, v6 = await asyncio.gather(lookup(socket.AF_INET), lookup(socket.AF_INET6))
        hosts = [*v4, *v6]
        if hosts:
            return hosts
        if last_error is not None:
            raise last_error
        raise socket.gaierror(socket.EAI_NONAME, f"Name or service not known: {host}")

    async def close(self) -> None:
        pass


def _session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(
            resolver=_FamilyRaceResolver(),
            happy_eyeballs_delay=0.25,
        )
    )


async def get_json_with_retry(session: aiohttp.ClientSession, url: str, **kwargs: Any) -> Tuple[int, str, Any]:
    last_error: Optional[BaseException] = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            async with session.get(url, **kwargs) as resp:
                if resp.status != 200:
                    return resp.status, await resp.text(), None
                return resp.status, "", await resp.json(content_type=None)
        except Exception as error:
            if not (isinstance(error, aiohttp.ClientConnectorError) or is_name_resolution_error(error)):
                raise
            last_error = error
            if attempt == RETRY_ATTEMPTS:
                raise
            logger.warning(f"Docker Hub GET {url} failed: {error} (attempt {attempt}/{RETRY_ATTEMPTS})")
            await asyncio.sleep(0.5)
    assert last_error is not None
    raise last_error


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

        async with _session() as session:
            status, _text, data = await get_json_with_retry(session, auth_url + "/token", params=payload)
            if status != 200 or data is None:
                warn(f"Error status {status}")
                raise RuntimeError("Could not get auth token")
            return str(data["token"])

    async def fetch_sha(self, metadata: TagMetadata) -> str:
        """Fetches the digest sha from a tag. This returns the image id displayed by 'docker image ls'"""
        header = {
            "Authorization": f"Bearer {self.last_token}",
            "Accept": "application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.manifest.v1+json",
        }
        async with _session() as session:
            url = f"{self.index_url}/v2/{metadata.repository}/manifests/{metadata.digest}"
            status, text, data = await get_json_with_retry(session, url, headers=header)
            if status != 200 or data is None:
                warn(f"Error status {status}")
                raise RuntimeError(f"Failed getting sha from DockerHub at {url} : {status} : {text}")
            return str(data["config"]["digest"])

    async def fetch_remote_tags(self, repository: str, local_images: List[str]) -> Tuple[str, List[TagMetadata]]:
        """Fetches the tags available for an image in DockerHub"""
        logger.info("fetching", repository)
        errors = []
        self.last_token = await self._get_token(auth_url="https://auth.docker.io", image_name=repository)
        async with _session() as session:
            status, text, data = await get_json_with_retry(
                session,
                f"{self.docker_url}/v2/repositories/{repository}/tags/?page_size=200&page=1&ordering=last_updated",
            )
            if status != 200 or data is None:
                warn(f"Error status {status}")
                raise RuntimeError(f"Failed getting tags from DockerHub! {status} {text}")
            tags = data["results"]

            my_architecture = get_current_arch()
            valid_images = []
            for tag in tags:
                images = tag["images"]
                if len(images) == 0:
                    # this is a hack to deal with https://github.com/docker/hub-feedback/issues/2484
                    # we lost the ability to properly identify the images as we dont have the digest,
                    # and also the ability to filter for compatible architectures.
                    # so we just add the tag and hope for the best.
                    tag = TagMetadata(
                        repository=repository,
                        image=repository.split("/")[-1],
                        tag=tag["name"],
                        last_modified=tag["last_updated"],
                        sha=None,
                        digest="------",
                    )
                    valid_images.append(tag)
                    continue
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
