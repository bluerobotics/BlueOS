from typing import Dict, Any
from urllib.request import urlopen
import json
import docker
from utils.dockerhub import TagFetcher


VERSIONS_URL = (
    "https://gist.githubusercontent.com/Williangalvani/54858292a29f4f6f39b078c961864e61"
    "/raw/92428cd920f8182cdef559ca9bc398fa0ad745dd/versions.json"
)


class Updater:
    """Responsible for managing the Companion Versions"""

    all_versions: Dict["str", Any]
    tag_fetcher: TagFetcher
    client = docker.client.from_env()

    def __init__(self) -> None:
        self.all_versions = {}
        self.tag_fetcher = TagFetcher()

    def _fetch_available_versions(self) -> None:
        """Fetches the data from VERSIONS_URL"""
        with urlopen(VERSIONS_URL) as resource:
            versions = json.load(resource)
            self.all_versions = versions

    def is_available_offline(self, image: str, tag: str) -> bool:
        """Checks if a image:tag is available offline

        Args:
            image (str): image name (such as "bluerobotics/core")
            tag (str): tag name (such as latest/master or a semver name)

        Returns:
            bool: If the image available offline
        """
        try:
            self.client.images.get(f"{image}:{tag}")
            return True
        except docker.errors.ImageNotFound:
            print(f"{image}:{tag} is not available offline!")
            return False

    def get_all_versions(self) -> Dict[str, Any]:
        """Returns versions.json augmented with a "availableOffline" field"""
        self._fetch_available_versions()

        for version, version_config in self.all_versions.items():
            missing = False
            for _docker, config in version_config["dockers"].items():
                if not self.is_available_offline(config["image"], config["tag"]):
                    missing = True
            self.all_versions[version]["available"] = not missing
        return self.all_versions

    def get_running_version(self, services: Dict[str, Any]) -> str:
        """Cross-checks all running containers against the versions.json data to detect
        What Companion version is currently running

        Args:
            services (Dict[str, Any]): Content of dockers.json

        Returns:
            str: [description]
        """
        for version_name, version_config in self.all_versions.items():
            found_match = True
            for service_name, service in services.items():
                if service.version != version_config["dockers"][service_name]["tag"]:
                    found_match = False
                    break
            if found_match:
                return version_name
        return "custom"
