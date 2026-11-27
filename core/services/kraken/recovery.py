import json
from typing import Any, Dict, List, Optional, Tuple

from config import DEFAULT_INJECTED_ENV_VARIABLES
from settings import ExtensionSettings

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
    "CapDrop",
    "DeviceCgroupRules",
    "DeviceRequests",
    "Dns",
    "GroupAdd",
    "Mounts",
    "PidMode",
    "RestartPolicy",
    "SecurityOpt",
    "ShmSize",
    "Sysctls",
    "Tmpfs",
    "Ulimits",
    "UsernsMode",
)

# Values docker reports for options that were never requested
_HOST_CONFIG_DEFAULTS = {
    "NetworkMode": "default",
    "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
    "ShmSize": 67108864,
}

# Same value as extension.extension.TEMP_EXTENSION_TAG_PREFIX, which cannot be imported here (circular)
TEMP_EXTENSION_TAG_PREFIX = "temp-"

# Major Tom is installed by the frontend, not by Kraken defaults, so its identifier cannot be learned from them
_KNOWN_EXTENSIONS_BY_DOCKER = {"public.ecr.aws/blueos/bcloud-agent": ("blueos.major_tom", "major_tom")}


def split_image_name(image: str) -> Optional[Tuple[str, str]]:
    if not image or image.startswith("sha256:"):
        return None
    repo, sep, tag = image.rpartition(":")
    if not sep or not repo or "/" in tag:
        return None
    return repo, tag


def permissions_from_inspect(inspect: Dict[str, Any]) -> str:
    config = inspect.get("Config") or {}
    host = inspect.get("HostConfig") or {}
    image_config = inspect.get("ImageConfig") or {}
    result: Dict[str, Any] = {}

    exposed = config.get("ExposedPorts")
    if exposed:
        result["ExposedPorts"] = exposed

    image_env = set(image_config.get("Env") or [])
    env = [
        entry
        for entry in config.get("Env") or []
        if entry not in image_env and entry.split("=", 1)[0] not in DEFAULT_INJECTED_ENV_VARIABLES
    ]
    if env:
        result["Env"] = env

    for key in ("Cmd", "Entrypoint", "User", "WorkingDir"):
        if config.get(key) and config.get(key) != image_config.get(key):
            result[key] = config[key]

    hostconfig: Dict[str, Any] = {}
    for key in _HOST_CONFIG_KEYS:
        value = host.get(key)
        if value in (None, "", [], {}, False) or value == _HOST_CONFIG_DEFAULTS.get(key):
            continue
        hostconfig[key] = value
    if hostconfig:
        result["HostConfig"] = hostconfig

    return json.dumps(result)


def _identifier_and_name(labels: Dict[str, Any], docker: str, catalog: Dict[str, Any]) -> Tuple[str, str]:
    identifier = labels.get(LABEL_IDENTIFIER) or ""
    display_name = labels.get(LABEL_NAME) or ""
    if not identifier:
        known = {key: (entry.identifier, entry.name) for key, entry in catalog.items()}
        # The frontend finds Major Tom by this identifier, so no catalog entry may override it
        known.update(_KNOWN_EXTENSIONS_BY_DOCKER)
        if docker in known:
            identifier, known_name = known[docker]
            display_name = display_name or known_name
    if not identifier:
        identifier = fallback_identifier(docker)
    if not display_name:
        display_name = docker.rsplit("/", 1)[-1]
    return identifier, display_name


def fallback_identifier(docker: str) -> str:
    return docker.replace("/", ".")


def _catalog_permissions(catalog: Dict[str, Any], docker: str, tag: str) -> str:
    entry = catalog.get(docker)
    version = entry and (entry.versions.get(tag) or entry.versions.get(f"v{tag}"))
    return json.dumps(version.permissions) if version and version.permissions is not None else ""


def recovered_extension_from_inspect(
    inspect: Dict[str, Any], catalog: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    catalog = catalog or {}
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
    if tag.startswith(TEMP_EXTENSION_TAG_PREFIX):
        return None
    if ExtensionSettings(docker=docker, tag=tag).container_name() != container_name:
        return None

    labels = config.get("Labels") or {}
    identifier, display_name = _identifier_and_name(labels, docker, catalog)
    permissions = (
        labels.get(LABEL_PERMISSIONS) or _catalog_permissions(catalog, docker, tag) or permissions_from_inspect(inspect)
    )
    user_permissions = labels.get(LABEL_USER_PERMISSIONS) or ""

    return {
        "identifier": identifier,
        "name": display_name,
        "docker": docker,
        "tag": tag,
        "permissions": permissions,
        "enabled": True,
        "user_permissions": user_permissions,
    }


def keep_one_enabled_per_identifier(recovered: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> List[ExtensionSettings]:
    """Prefer the running container, then the newest one, so two tags of an extension never run together."""
    ranked = sorted(
        recovered,
        key=lambda pair: (bool((pair[1].get("State") or {}).get("Running")), pair[1].get("Created") or ""),
        reverse=True,
    )
    seen = set()
    result = []
    for data, _ in ranked:
        data["enabled"] = data["identifier"] not in seen
        seen.add(data["identifier"])
        result.append(ExtensionSettings(**data))
    return result


def stamp_extension_labels(
    config: Dict[str, Any], identifier: str, name: str, permissions: str, user_permissions: str
) -> None:
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        labels = {}
        config["Labels"] = labels
    labels[LABEL_IDENTIFIER] = identifier
    labels[LABEL_NAME] = name
    labels[LABEL_PERMISSIONS] = permissions
    labels[LABEL_USER_PERMISSIONS] = user_permissions or ""
