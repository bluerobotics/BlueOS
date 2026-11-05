from dataclasses import dataclass
from typing import Any, Mapping

from docker_registry.exceptions import RegistryError

_DOCKER_HUB_HOSTS = {"docker.io", "index.docker.io", "registry-1.docker.io"}
_DOCKER_HUB_REGISTRY = "https://registry-1.docker.io"


@dataclass(frozen=True)
class ImageReference:
    registry: str
    repository: str
    reference: str


def parse_image_reference(value: str) -> ImageReference:
    """Split an image name into a registry URL, repository, and tag or digest.

    Forms include name, name:tag, org/name:tag, host[:port]/org/name:tag, and any of those
    with @digest. Docker Hub names use registry-1.docker.io, and a single official image
    name is stored under library/.
    """
    name, digest = _split_digest(value)
    host, remote = _split_host(name)
    tag = "latest"
    if ":" in remote:
        remote, tag = remote.rsplit(":", 1)
        if not tag:
            raise RegistryError(f"Invalid image reference: {value}")
    if not remote or any(part in ("", ".", "..") for part in remote.split("/")):
        raise RegistryError(f"Invalid image reference: {value}")
    if host in _DOCKER_HUB_HOSTS and "/" not in remote:
        remote = f"library/{remote}"

    registry = _DOCKER_HUB_REGISTRY if host in _DOCKER_HUB_HOSTS else f"https://{host}"
    return ImageReference(registry=registry, repository=remote, reference=digest or tag)


def linux_platform_name(entry: Mapping[str, Any]) -> str | None:
    """Return arch or arch/variant for a Linux manifest entry. Other platforms return None."""
    platform = entry.get("platform")
    if not isinstance(platform, dict) or platform.get("os") != "linux":
        return None
    architecture = platform.get("architecture")
    if not isinstance(architecture, str):
        return None
    variant = platform.get("variant")
    return architecture + (f"/{variant}" if isinstance(variant, str) else "")


def _split_digest(value: str) -> tuple[str, str | None]:
    if "@" not in value:
        return value, None
    name, digest = value.rsplit("@", 1)
    if ":" not in digest or not name:
        raise RegistryError(f"Invalid image reference: {value}")
    return name, digest


def _split_host(name: str) -> tuple[str, str]:
    slash = name.find("/")
    if slash == -1:
        return "docker.io", name
    first = name[:slash]
    if "." in first or ":" in first or first == "localhost":
        if not name[slash + 1 :]:
            raise RegistryError(f"Invalid image reference: {name}")
        return first, name[slash + 1 :]
    return "docker.io", name
