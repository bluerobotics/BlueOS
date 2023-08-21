import http
from functools import cached_property
from typing import List, Optional

import psutil
import requests
from loguru import logger

from src.typedefs import ExtensionInfo, VersionInfo


class Metrics:
    @cached_property
    def installed_extensions(self) -> Optional[List[ExtensionInfo]]:
        try:
            req = requests.get("http://localhost/kraken/v1.0/installed_extensions", timeout=3)
            if req.status_code == http.client.OK:
                return [ExtensionInfo(identifier=rec["identifier"], tag=rec["tag"]) for rec in req.json()]
        except Exception as error:
            logger.error(f"Error getting installed extensions: {error}")
            return None
        return []

    @cached_property
    def disk(self) -> psutil._common.sdiskusage:
        return psutil.disk_usage("/")

    @cached_property
    def memory(self) -> psutil._pslinux.svmem:
        return psutil.virtual_memory()

    @cached_property
    def installed_version(self) -> Optional[VersionInfo]:
        try:
            req = requests.get("http://localhost/version-chooser/v1.0/version/current", timeout=3)
            if req.status_code == http.client.OK:
                data = req.json()
                return VersionInfo(
                    repository=data["repository"],
                    tag=data["tag"],
                    last_modified=data["last_modified"],
                    sha=data["sha"],
                    architecture=data["architecture"],
                )

        except Exception as error:
            logger.error(f"Error getting version info: {error}")
        return None
