#!/usr/bin/env python3
"""
Responsible for interacting with dockerhub
adapted from https://github.com/al4/docker-registry-list
"""

from typing import Optional, List, Dict
from warnings import warn
import requests


class TagFetcher:
    """Fetches remote tags for a given image"""

    # Holds the information once it is fetched so we don't do it multiple times
    cache: Dict[str, List[str]]

    def _get_token(self, auth_url: str, image_name: str) -> str:
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
            "scope": "repository:{image}:pull".format(image=image_name),
        }

        request = requests.get(auth_url + "/token", params=payload)
        if not request.status_code == 200:
            warn("Error status {}".format(request.status_code))
            raise Exception("Could not get auth token")
        return str(request.json()["token"])

    def fetch_remote_versions(
        self,
        image_name: str,
        index_url: str = "https://index.docker.io",
        token: Optional[str] = None,
    ) -> List[str]:
        """[summary]

        Args:
            image_name (str): Image to fetch tags for, for example "bluerobotics/core"
            index_url (str, optional): [description]. Defaults to "https://index.docker.io".
            token (Optional[str], optional): Token to use. Gets a new one if None is supplied

        Returns:
            List[str]: A list of tags available on dockerhub
        """
        if image_name in self.cache:
            return self.cache[image_name]

        if token is None:
            token = self._get_token(
                auth_url="https://auth.docker.io", image_name=image_name
            )
        header = {"Authorization": "Bearer {}".format(token)}
        request = requests.get(
            "{}/v2/{}/tags/list".format(index_url, image_name), headers=header
        )
        tags = list(request.json()["tags"])
        self.cache[image_name] = tags
        return tags
