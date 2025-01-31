import base64
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from aiohttp import web

DOCKER_USER_CONFIG_DIR = "/home/pi/.docker"
DOCKER_ROOT_CONFIG_DIR = "/root/.docker"

DOCKER_USER_CONFIG_FILE = os.path.join(DOCKER_USER_CONFIG_DIR, "config.json")
DOCKER_ROOT_CONFIG_FILE = os.path.join(DOCKER_ROOT_CONFIG_DIR, "config.json")

DEFAULT_DOCKER_REGISTRY = "https://index.docker.io/v1/"


@dataclass
class DockerLoginInfo:
    root: bool = True
    registry: str = DEFAULT_DOCKER_REGISTRY
    username: str = ""
    password: str = ""

    @staticmethod
    def from_json(data: Dict[str, Any]) -> "DockerLoginInfo":
        return DockerLoginInfo(
            root=data.get("root", True),
            registry=data.get("registry", DEFAULT_DOCKER_REGISTRY),
            username=data.get("username", ""),
            password=data.get("password", ""),
        )


def get_accounts_from_file(file_path: str, root: bool) -> List[DockerLoginInfo]:
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    login_infos: List[DockerLoginInfo] = []

    # Key is registry URL, value is a dict with key "auth" and the value is the auth info composed of a base64 encoded
    # string with "username:password"
    auths: Dict[str, Dict[str, str]] = config.get("auths", {})

    for registry, data in auths.items():
        auth = data.get("auth", None)
        if auth is not None:
            try:
                decoded_auth = base64.b64decode(auth).decode("utf-8")
                username, password = decoded_auth.split(":", 1)
                login_infos.append(DockerLoginInfo(root=root, registry=registry, username=username, password=password))
            except Exception:
                pass

    return login_infos


def login_to_file(info: DockerLoginInfo, file_path: str) -> None:
    # Make sure the directories exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            config = json.load(file)
    else:
        config = {}

    if "auths" not in config:
        config["auths"] = {}

    encoded_auth = base64.b64encode(f"{info.username}:{info.password}".encode("utf-8")).decode("utf-8")
    config["auths"][info.registry] = {"auth": encoded_auth}

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4)


def logout_from_file(info: DockerLoginInfo, file_path: str) -> None:
    if not os.path.exists(file_path):
        return

    with open(file_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    if "auths" not in config:
        return

    if info.registry in config["auths"]:
        del config["auths"][info.registry]

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4)


def get_docker_accounts() -> web.Response:
    root_accounts = get_accounts_from_file(DOCKER_ROOT_CONFIG_FILE, True)
    user_accounts = get_accounts_from_file(DOCKER_USER_CONFIG_FILE, False)

    for account in root_accounts:
        # If some root account with same registry and username is found in user accounts, remove it
        user_accounts = [x for x in user_accounts if x.registry != account.registry or x.username != account.username]

    accounts = root_accounts + user_accounts

    return web.json_response([asdict(account) for account in accounts])


def make_docker_login(info: DockerLoginInfo) -> None:
    login_to_file(info, DOCKER_USER_CONFIG_FILE)

    if info.root:
        login_to_file(info, DOCKER_ROOT_CONFIG_FILE)


def make_docker_logout(info: DockerLoginInfo) -> None:
    logout_from_file(info, DOCKER_USER_CONFIG_FILE)
    logout_from_file(info, DOCKER_ROOT_CONFIG_FILE)
