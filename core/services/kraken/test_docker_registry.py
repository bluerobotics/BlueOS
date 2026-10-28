import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

# In-process imports so pytest can patch the client and serve a registry.
# test_kraken.py shells out because it only checks an import side effect.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from docker_registry.client import RegistryClient
from docker_registry.exceptions import ManifestNotFound, RegistryError
from docker_registry.reference import (
    ImageReference,
    linux_platform_name,
    parse_image_reference,
)

_MANIFEST = {"schemaVersion": 2, "mediaType": "application/vnd.docker.distribution.manifest.v2+json"}
_Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def test_parse_docker_hub_repository() -> None:
    parsed = parse_image_reference("bluerobotics/blueos-ping-viewer-next:1.0.0-beta.26")

    assert parsed.registry == "https://registry-1.docker.io"
    assert parsed.repository == "bluerobotics/blueos-ping-viewer-next"
    assert parsed.reference == "1.0.0-beta.26"


def test_parse_official_image_uses_library_namespace() -> None:
    parsed = parse_image_reference("ubuntu:22.04")

    assert parsed.repository == "library/ubuntu"
    assert parsed.reference == "22.04"


def test_parse_custom_registry() -> None:
    parsed = parse_image_reference("ghcr.io/org/image:tag")

    assert parsed.registry == "https://ghcr.io"
    assert parsed.repository == "org/image"
    assert parsed.reference == "tag"


def test_parse_localhost_with_port() -> None:
    parsed = parse_image_reference("localhost:5000/foo/bar:latest")

    assert parsed.registry == "https://localhost:5000"
    assert parsed.repository == "foo/bar"
    assert parsed.reference == "latest"


def test_parse_digest_reference() -> None:
    parsed = parse_image_reference("ubuntu:22.04@sha256:abc")

    assert parsed.repository == "library/ubuntu"
    assert parsed.reference == "sha256:abc"


def test_parse_rejects_empty_repository() -> None:
    with pytest.raises(RegistryError):
        parse_image_reference("ghcr.io/:tag")


@asynccontextmanager
async def _patched_registry(monkeypatch: pytest.MonkeyPatch, handler: _Handler) -> AsyncIterator[str]:
    app = web.Application()
    app.router.add_route("GET", "/{tail:.*}", handler)
    async with TestServer(app) as server:
        base = str(server.make_url("/")).rstrip("/")

        def parse(value: str) -> ImageReference:
            parsed = parse_image_reference(value)
            return ImageReference(registry=base, repository=parsed.repository, reference=parsed.reference)

        monkeypatch.setattr("docker_registry.client.parse_image_reference", parse)
        yield base


@pytest.mark.asyncio
async def test_linux_manifests_follows_bearer_auth_and_same_origin_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str | None]] = []
    challenge = {"header": ""}

    async def handle(request: web.Request) -> web.Response:
        calls.append((request.path, request.headers.get("Authorization")))
        if request.path == "/token":
            return web.json_response({"token": "secret-token"})
        if request.headers.get("Authorization") != "Bearer secret-token":
            return web.Response(status=401, headers={"WWW-Authenticate": challenge["header"]})
        if request.path.endswith("/manifests/1.0"):
            return web.Response(status=302, headers={"Location": "/v2/org/app/manifests/sha256:abc"})
        return web.json_response(_MANIFEST)

    async with _patched_registry(monkeypatch, handle) as base:
        challenge["header"] = f'Bearer realm="{base}/token",service="registry.test",scope="repository:org/app:pull"'
        async with RegistryClient() as client:
            resolved = await client.linux_manifests("org/app", "1.0")

    assert resolved == [(None, _MANIFEST)]
    assert calls == [
        ("/v2/org/app/manifests/1.0", None),
        ("/token", None),
        ("/v2/org/app/manifests/1.0", "Bearer secret-token"),
        ("/v2/org/app/manifests/sha256:abc", "Bearer secret-token"),
    ]


@pytest.mark.asyncio
async def test_missing_manifest_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handle(_request: web.Request) -> web.Response:
        return web.Response(status=404)

    async with _patched_registry(monkeypatch, handle):
        async with RegistryClient() as client:
            with pytest.raises(ManifestNotFound):
                await client.linux_manifests("org/app", "missing")


@pytest.mark.asyncio
async def test_redirect_does_not_send_token_to_a_later_cdn_hop(monkeypatch: pytest.MonkeyPatch) -> None:
    registry_calls: list[str | None] = []
    cdn_calls: list[tuple[str, str | None]] = []
    challenge = {"header": ""}

    async def registry_handle(request: web.Request) -> web.Response:
        registry_calls.append(request.headers.get("Authorization"))
        if request.path == "/token":
            return web.json_response({"token": "secret-token"})
        if request.headers.get("Authorization") != "Bearer secret-token":
            return web.Response(status=401, headers={"WWW-Authenticate": challenge["header"]})
        return web.Response(status=302, headers={"Location": cdn["base"] + "/layer"})

    async def cdn_handle(request: web.Request) -> web.Response:
        cdn_calls.append((request.path, request.headers.get("Authorization")))
        if request.path == "/layer":
            return web.Response(status=302, headers={"Location": "/layer/2"})
        return web.json_response(_MANIFEST)

    cdn_app = web.Application()
    cdn_app.router.add_route("GET", "/{tail:.*}", cdn_handle)
    cdn = {"base": ""}
    async with TestServer(cdn_app) as cdn_server:
        cdn["base"] = str(cdn_server.make_url("/")).rstrip("/")
        async with _patched_registry(monkeypatch, registry_handle) as base:
            challenge["header"] = f'Bearer realm="{base}/token",service="registry.test"'
            async with RegistryClient() as client:
                resolved = await client.linux_manifests("org/app", "1.0")

    assert resolved == [(None, _MANIFEST)]
    assert registry_calls == [None, None, "Bearer secret-token"]
    assert cdn_calls == [("/layer", None), ("/layer/2", None)]


def test_linux_platform_name_includes_variant_and_skips_attestations() -> None:
    assert linux_platform_name({"platform": {"os": "linux", "architecture": "amd64"}}) == "amd64"
    assert linux_platform_name({"platform": {"os": "linux", "architecture": "arm", "variant": "v7"}}) == "arm/v7"
    assert linux_platform_name({"platform": {"os": "unknown", "architecture": "unknown"}}) is None
    assert linux_platform_name({}) is None
