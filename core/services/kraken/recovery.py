import json
import re
from typing import Any, Dict, Optional, Tuple

LABEL_IDENTIFIER = "blueos.extension.identifier"
LABEL_NAME = "blueos.extension.name"
LABEL_PERMISSIONS = "blueos.extension.permissions"
LABEL_USER_PERMISSIONS = "blueos.extension.user_permissions"

_HOST_CONFIG_KEYS = (
    "Binds",
    "NetworkMode",
    "Privileged",
    "ExtraHosts",
    "PortBindings",
    "Devices",
    "CapAdd",
)

_CONTAINER_NAME_SANITIZE = re.compile("[^a-zA-Z0-9]")


def split_image_name(image: str) -> Optional[Tuple[str, str]]:
    if not image or image.startswith("sha256:"):
        return None
    repo, sep, tag = image.rpartition(":")
    if not sep or not repo or "/" in tag:
        return None
    return repo, tag


def container_name_for(docker: str, tag: str) -> str:
    return "extension-" + _CONTAINER_NAME_SANITIZE.sub("", f"{docker}{tag}")


def permissions_from_inspect(inspect: Dict[str, Any]) -> str:
    config = inspect.get("Config") or {}
    host = inspect.get("HostConfig") or {}
    result: Dict[str, Any] = {}

    exposed = config.get("ExposedPorts")
    if exposed:
        result["ExposedPorts"] = exposed

    hostconfig: Dict[str, Any] = {}
    for key in _HOST_CONFIG_KEYS:
        value = host.get(key)
        if value in (None, "", [], {}, False):
            continue
        if key == "NetworkMode" and value == "default":
            continue
        hostconfig[key] = value
    if hostconfig:
        result["HostConfig"] = hostconfig

    return json.dumps(result)


def _identifier_and_name(
    labels: Dict[str, Any],
    docker: str,
    catalog_by_docker: Optional[Dict[str, Tuple[str, str]]],
) -> Tuple[str, str]:
    identifier = labels.get(LABEL_IDENTIFIER) or ""
    display_name = labels.get(LABEL_NAME) or ""
    if not identifier and catalog_by_docker and docker in catalog_by_docker:
        identifier, catalog_name = catalog_by_docker[docker]
        display_name = display_name or catalog_name
    if not identifier:
        identifier = docker.replace("/", ".")
    if not display_name:
        display_name = docker.rsplit("/", 1)[-1]
    return identifier, display_name


def recovered_extension_from_inspect(
    inspect: Dict[str, Any],
    catalog_by_docker: Optional[Dict[str, Tuple[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    names = inspect.get("Name") or ""
    if isinstance(names, list):
        name = names[0] if names else ""
    else:
        name = str(names)
    container_name = name.lstrip("/")
    if not container_name.startswith("extension-"):
        return None

    config = inspect.get("Config") or {}
    image = config.get("Image") or ""
    split = split_image_name(image)
    if not split:
        return None
    docker, tag = split
    if container_name_for(docker, tag) != container_name:
        return None

    labels = config.get("Labels") or {}
    identifier, display_name = _identifier_and_name(labels, docker, catalog_by_docker)
    permissions = labels.get(LABEL_PERMISSIONS) or ""
    user_permissions = labels.get(LABEL_USER_PERMISSIONS) or ""

    if not permissions:
        permissions = permissions_from_inspect(inspect)

    return {
        "identifier": identifier,
        "name": display_name,
        "docker": docker,
        "tag": tag,
        "permissions": permissions,
        "enabled": True,
        "user_permissions": user_permissions,
    }


def stamp_extension_labels(
    config: Dict[str, Any], identifier: str, name: str, permissions: str, user_permissions: str
) -> None:
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        labels = {}
        config["Labels"] = labels
    labels[LABEL_IDENTIFIER] = identifier
    labels[LABEL_NAME] = name
    labels[LABEL_PERMISSIONS] = permissions or ""
    labels[LABEL_USER_PERMISSIONS] = user_permissions or ""
