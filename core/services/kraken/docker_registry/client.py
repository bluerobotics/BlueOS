import json
import re
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

import aiohttp
from docker_registry.exceptions import ManifestNotFound, RegistryError
from docker_registry.reference import (
    ImageReference,
    linux_platform_name,
    parse_image_reference,
)

_MANIFEST_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)
# Followed manually so a bearer token is not attached to a later hop on a CDN.
_REDIRECTS = {301, 302, 303, 307, 308}
# A token service and a blob CDN add a few hops. More than this is a redirect loop.
_MAX_REDIRECTS = 5
_CHALLENGE_PARAM = re.compile(r'(\w+)=(?:"([^"]*)"|([^,\s]+))')


class RegistryClient:
    """Read image manifests and config blobs from an OCI registry.

    Anonymous bearer tokens only. A stored Docker Hub refresh token is sent as Basic
    auth and the registry rejects it.
    """

    def __init__(self, timeout: float = 30) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None
        self._tokens: dict[str, str] = {}

    async def __aenter__(self) -> "RegistryClient":
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def linux_manifests(self, image: str, tag: str) -> list[tuple[str | None, dict[str, Any]]]:
        reference = parse_image_reference(f"{image}:{tag}")
        manifest = await self._get_manifest(reference, reference.reference)
        entries = manifest.get("manifests")
        if not isinstance(entries, list):
            return [(None, manifest)]

        resolved: list[tuple[str | None, dict[str, Any]]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            platform_name = linux_platform_name(entry)
            digest = entry.get("digest")
            if platform_name is None or not isinstance(digest, str):
                continue
            resolved.append((platform_name, await self._get_manifest(reference, digest)))
        return resolved

    async def image_config(self, image: str, tag: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
        config = manifest.get("config")
        if not isinstance(config, dict) or not isinstance(config.get("digest"), str):
            raise RegistryError(f"Manifest for {image}:{tag} has no config blob")
        reference = parse_image_reference(f"{image}:{tag}")
        url = f"{reference.registry}/v2/{reference.repository}/blobs/{config['digest']}"
        return await self._get_json(url, reference, {"Accept": "application/octet-stream"})

    async def _get_manifest(self, image: ImageReference, reference: str) -> dict[str, Any]:
        url = f"{image.registry}/v2/{image.repository}/manifests/{reference}"
        try:
            return await self._get_json(url, image, {"Accept": _MANIFEST_ACCEPT})
        except RegistryError as error:
            if error.status != 404:
                raise
            raise ManifestNotFound(f"Manifest not found for {image.repository}:{reference}") from error

    async def _get_json(self, url: str, image: ImageReference, headers: dict[str, str]) -> dict[str, Any]:
        body = await self._open(url, image, headers)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise RegistryError(f"Registry response from {url} was not JSON") from error
        if not isinstance(payload, dict):
            raise RegistryError(f"Registry response from {url} was not an object")
        return payload

    async def _open(self, url: str, image: ImageReference, headers: Mapping[str, str]) -> bytes:
        session = self._session
        if not isinstance(session, aiohttp.ClientSession):
            raise RegistryError("Registry client is not open")
        current = url
        forward_authorization = True
        auth_attempts = 0
        redirects = 0
        while True:
            status, location, www_authenticate, body = await _http_get(
                session,
                current,
                headers=_authorized_headers(headers, self._tokens.get(_token_key(image)), forward_authorization),
                allow_redirects=False,
            )
            if status in _REDIRECTS:
                redirects += 1
                current, forward_authorization = _redirect_target(url, current, location, redirects, image.registry)
                continue
            if status == 401 and auth_attempts < 1 and forward_authorization:
                auth_attempts += 1
                await self._authenticate(image, www_authenticate or "")
                continue
            if status >= 400:
                raise RegistryError(f"Registry request failed with {status} for {current}", status)
            return body

    async def _authenticate(self, image: ImageReference, www_authenticate: str) -> None:
        challenge = _parse_bearer_challenge(www_authenticate)
        query = {"scope": challenge.get("scope") or f"repository:{image.repository}:pull"}
        service = challenge.get("service")
        if service:
            query["service"] = service
        session = self._session
        if not isinstance(session, aiohttp.ClientSession):
            raise RegistryError("Registry client is not open")
        status, _location, _www_authenticate, body = await _http_get(session, challenge["realm"], params=query)
        if status >= 400:
            raise RegistryError(f"Registry authentication failed with {status}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise RegistryError("Registry authentication response was not JSON") from error
        if not isinstance(payload, dict):
            raise RegistryError("Registry authentication response did not include a token")
        token = payload.get("token") or payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise RegistryError("Registry authentication response did not include a token")
        self._tokens[_token_key(image)] = token


def _authorized_headers(headers: Mapping[str, str], token: str | None, forward_authorization: bool) -> dict[str, str]:
    request_headers = dict(headers)
    if token and forward_authorization:
        request_headers["Authorization"] = f"Bearer {token}"
    return request_headers


def _redirect_target(
    original: str, current: str, location: str | None, redirects: int, registry: str
) -> tuple[str, bool]:
    if redirects > _MAX_REDIRECTS or not location:
        raise RegistryError(f"Too many redirects requesting {original}")
    next_url = urljoin(current, location)
    # Compare with the registry, not the previous hop, so a later CDN request does not receive the token.
    return next_url, _same_origin(registry, next_url)


async def _http_get(
    session: aiohttp.ClientSession, url: str, **kwargs: Any
) -> tuple[int, str | None, str | None, bytes]:
    async with session.get(url, **kwargs) as response:
        body = await response.read()
        return response.status, response.headers.get("Location"), response.headers.get("WWW-Authenticate"), body


def _token_key(image: ImageReference) -> str:
    return f"{image.registry}/{image.repository}"


def _same_origin(left: str, right: str) -> bool:
    a, b = urlparse(left), urlparse(right)
    return a.scheme == b.scheme and a.netloc.lower() == b.netloc.lower()


def _parse_bearer_challenge(header: str) -> dict[str, str]:
    scheme, _, rest = header.strip().partition(" ")
    if scheme.lower() != "bearer":
        raise RegistryError("Registry did not offer bearer authentication")
    params: dict[str, str] = {}
    for match in _CHALLENGE_PARAM.finditer(rest):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        if value is not None:
            params[match.group(1)] = value
    if "realm" not in params:
        raise RegistryError("Registry authentication challenge has no realm")
    return params
