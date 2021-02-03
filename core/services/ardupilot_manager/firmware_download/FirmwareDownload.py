import enum
import gzip
import json
import os
import pathlib
import random
import ssl
import string
import tempfile
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import urlopen, urlretrieve
from warnings import warn

from packaging.version import Version

# TODO: This should be not necessary
# Disable SSL verification
if not os.environ.get("PYTHONHTTPSVERIFY", "") and getattr(ssl, "_create_unverified_context", None):
    ssl._create_default_https_context = ssl._create_unverified_context


class Vehicle(enum.Enum):
    """Valid vehicle types to download"""

    Sub = 1
    Rover = 2
    Plane = 3
    Copter = 4


class FirmwareDownload:
    _manifest_remote = "https://firmware.ardupilot.org/manifest.json.gz"
    _supported_firmware_format = "apj"

    def __init__(self) -> None:
        self._manifest: Dict[str, Any] = {}

    @staticmethod
    def _generate_random_filename(length: int = 16) -> pathlib.Path:
        """Generate a random name for a temporary file.

        Args:
            length (int, optional): Size of the name. Defaults to 16.

        Returns:
            pathlib.Path: Path of the temporary file.
        """

        filename = "".join(random.sample(string.ascii_lowercase, length))
        folder = pathlib.Path(tempfile.gettempdir()).absolute()
        return pathlib.Path.joinpath(folder, filename)

    @staticmethod
    def _download(url: str) -> Optional[pathlib.Path]:
        """Download a specific file for a temporary location.

        Args:
            url (str): Url to download the file.

        Returns:
            pathlib.Path: File of the temporary file.
        """

        # We append the url filename to the generated random name to avoid collisions and preserve extension
        name = pathlib.Path(urlparse(url).path).name
        filename = pathlib.Path(f"{FirmwareDownload._generate_random_filename()}-{name}")
        try:
            urlretrieve(url, filename)
        except Exception as error:
            warn(f"Failed to download {url}: {error}", RuntimeWarning)
            return None
        return filename

    @staticmethod
    def _download_navigator() -> Optional[pathlib.Path]:
        """This is a temporary method should be removed after navigator builds are provided
            by ArduPilot community.
            TODO: This function should not exist and be removed asap

        Returns:
            Optional[pathlib.Path]: Path of the binary
        """
        url = "https://s3.amazonaws.com/downloads.bluerobotics.com/ardusub/navigator/ardusub"
        return FirmwareDownload._download(url)

    @staticmethod
    def _validate_firmware(firmware_path: pathlib.Path) -> bool:
        """A simple validation function for firmware files (apj)

        Args:
            firmware_path (pathlib.Path): Path of the firmware file;

        Returns:
            bool: True if valid, False if otherwise.
        """
        with open(firmware_path, "r") as firmware_file:
            data = json.load(firmware_file)
            keys = data.keys()
            if "image_size" in keys and "image" in keys:
                return True

        return False

    def _manifest_is_valid(self) -> bool:
        """Check if internal content is valid and update it if not.

        Returns:
            bool: True if valid, False if was unable to validate.
        """
        return "format-version" in self._manifest or self.download_manifest()

    def download_manifest(self) -> bool:
        """Download ArduPilot manifest file

        Returns:
            bool: True if file was downloaded and validated, False if not.
        """
        with urlopen(FirmwareDownload._manifest_remote) as http_response:
            manifest_gzip = http_response.read()
            manifest = gzip.decompress(manifest_gzip)
            self._manifest = json.loads(manifest)

        if "format-version" not in self._manifest:
            warn("Failed to fetch content of manifest file.", RuntimeWarning)
            return False

        if self._manifest["format-version"] != "1.0.0":
            warn("Firmware description file format changed, compatibility may be broken.", RuntimeWarning)

        return True

    def _find_version_item(self, **args: str) -> List[Dict[str, Any]]:
        """Find version objects in the manifest that match the specific case of **args

        The arguments should follow the same name described in the dictionary inside the manifest
        for firmware item. Valid arguments can be:
            mav_type, vehicletype, mav_firmware_version_minor, format, mav_firmware_version_type,
            platform, latest and others. `-` should be replaced by `_` to use valid python arguments.
            E.g: `self._find_version_item(vehicletype="Sub", platform="Pixhawk1", mav_firmware_version_type="4.0.1")`

        Returns:
            List[Dict[str, Any]]: A list of firmware items that match the arguments.
        """
        if not self._manifest and not self.download_manifest():
            return []

        found_version_item = []

        # Make sure that the item matches all args value
        for item in self._manifest["firmware"]:
            for key in args:
                real_key = key.replace("_", "-")
                if real_key not in item or item[real_key] != args[key]:
                    break
            else:
                found_version_item.append(item)

        return found_version_item

    def get_available_versions(self, vehicle: Vehicle, platform: str) -> List[str]:
        """Get available firmware versions for the specific plataform and vehicle

        Args:
            vehicle (Vehicle): Desired vehicle.
            platform (str): Desired platform.

        Returns:
            List[str]: List of available versions that match the specific desired configuration.
        """
        available_versions: List[str] = []

        if not self._manifest_is_valid():
            return available_versions

        items = self._find_version_item(
            vehicletype=vehicle.name, platform=platform, format=FirmwareDownload._supported_firmware_format
        )

        for item in items:
            available_versions.append(item["mav-firmware-version-type"])

        return available_versions

    def download(self, vehicle: Vehicle, platform: str, version: str = "") -> Optional[pathlib.Path]:
        """Download a specific firmware that matches the arguments.

        Args:
            vehicle (Vehicle): Desired vehicle.
            platform (str): Desired platform.
            version (str, optional): Desired version, if None provided the latest stable will be used.
                Defaults to None.

        Returns:
            Optional[pathlib.Path]: Temporary path for the firmware file, None if unable to download or validate file.
        """
        if platform.lower() == "navigator" and vehicle == Vehicle.Sub:
            return FirmwareDownload._download_navigator()

        versions = self.get_available_versions(vehicle, platform)
        if version and versions and version not in versions:
            return None

        # Autodetect the latest stable version
        if not version:
            stable_versions = [version for version in versions if "STABLE" in version]
            newest_version: Optional[str] = None
            for stable_version in stable_versions:
                semver_version = stable_version.split("-")[1]
                if not newest_version or Version(newest_version) < Version(semver_version):
                    newest_version = semver_version
            if not newest_version:
                return None
            version = f"STABLE-{newest_version}"

        items = self._find_version_item(
            vehicletype=vehicle.name,
            platform=platform,
            mav_firmware_version_type=version,
            format=FirmwareDownload._supported_firmware_format,
        )

        if len(items) != 1:
            warn(f"Invalid number of candidates to download: {len(items)}", RuntimeWarning)
            return None

        item = items[0]
        path = FirmwareDownload._download(item["url"])
        if not path or not FirmwareDownload._validate_firmware(path):
            warn("Unable to validate firmware file.", RuntimeWarning)
            return None

        return path
