import gzip
import json
import os
import pathlib
import random
import ssl
import stat
import string
import subprocess
import tempfile
from enum import Enum
from platform import machine
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import urlopen, urlretrieve

from loguru import logger
from packaging.version import Version

# TODO: This should be not necessary
# Disable SSL verification
if not os.environ.get("PYTHONHTTPSVERIFY", "") and getattr(ssl, "_create_unverified_context", None):
    ssl._create_default_https_context = ssl._create_unverified_context


def get_sitl_platform_name() -> str:
    if machine() == "x86_64":
        return "SITL_x86_64_linux_gnu"
    return "SITL_arm_linux_gnueabihf"


class Vehicle(str, Enum):
    """Valid vehicle types to download"""

    Sub = "Sub"
    Rover = "Rover"
    Plane = "Plane"
    Copter = "Copter"


class Platform(str, Enum):
    """Valid platform types to download
    The Enum values are 1:1 representations of the platforms available on the ArduPilot manifest,
    with the exception being Navigator, which is not on the manifest yet."""

    Pixhawk1 = "Pixhawk1"
    Navigator = "Navigator"
    SITL = get_sitl_platform_name()


class FirmwareFormat(str, Enum):
    """Valid firmware formats to download.
    The Enum values are 1:1 representations of the formats available on the ArduPilot manifest."""

    APJ = "apj"
    ELF = "ELF"


class FirmwareDownload:
    _manifest_remote = "https://firmware.ardupilot.org/manifest.json.gz"
    _supported_firmware_formats = {
        Platform.SITL: FirmwareFormat.ELF,
        Platform.Pixhawk1: FirmwareFormat.APJ,
        Platform.Navigator: FirmwareFormat.ELF,
    }

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
            logger.debug(f"Downloading: {url}")
            urlretrieve(url, filename)
        except Exception as error:
            logger.error(f"Failed to download {url}: {error}")
            return None
        return filename

    @staticmethod
    def _navigator_firmware_url() -> str:
        """This is a temporary method should be removed after navigator builds are provided
            by ArduPilot community.
            TODO: This function should not exist and be removed asap

        Returns:
            str: Navigator url
        """
        return "https://s3.amazonaws.com/downloads.bluerobotics.com/ardusub/navigator/ardusub"

    @staticmethod
    def _validate_firmware(firmware_path: pathlib.Path) -> bool:
        """A simple validation function for firmware files (apj)

        Args:
            firmware_path (pathlib.Path): Path of the firmware file;

        Returns:
            bool: True if valid, False if otherwise.
        """
        if FirmwareFormat.APJ.value in firmware_path.suffix:
            with open(firmware_path, "r") as firmware_file:
                data = json.load(firmware_file)
                keys = data.keys()
                if "image_size" in keys and "image" in keys:
                    return True
        else:
            try:
                subprocess.check_output([firmware_path, "--help"])
                return True
            except Exception as error:
                logger.error(f"Firmware help menu not available. Binary not validated. {error}")

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
            logger.error("Failed to fetch content of manifest file.")
            return False

        if self._manifest["format-version"] != "1.0.0":
            logger.warning("Firmware description file format changed, compatibility may be broken.")

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

    def get_available_versions(self, vehicle: Vehicle, platform: Platform) -> List[str]:
        """Get available firmware versions for the specific plataform and vehicle

        Args:
            vehicle (Vehicle): Desired vehicle.
            platform (Platform): Desired platform.

        Returns:
            List[str]: List of available versions that match the specific desired configuration.
        """
        available_versions: List[str] = []

        if not self._manifest_is_valid():
            return available_versions

        items = self._find_version_item(vehicletype=vehicle.value, platform=platform.value)

        for item in items:
            if item["format"] == FirmwareDownload._supported_firmware_formats[platform]:
                available_versions.append(item["mav-firmware-version-type"])

        return available_versions

    def get_download_url(self, vehicle: Vehicle, platform: Platform, version: str = "") -> Optional[str]:
        """Find a specific firmware URL from manifest that matches the arguments.

        Args:
            vehicle (Vehicle): Desired vehicle.
            platform (Platform): Desired platform.
            version (str, optional): Desired version, if None provided the latest stable will be used.
                Defaults to None.

        Returns:
            Optional[str]: URL of valid firmware or None if there is no such thing.
        """
        if platform == Platform.Navigator and vehicle == Vehicle.Sub:
            return FirmwareDownload._navigator_firmware_url()

        versions = self.get_available_versions(vehicle, platform)
        logger.debug(f"Got following versions for {vehicle} running {platform}: {versions}")

        if not versions:
            logger.error("No versions available")
            return None

        if version and version not in versions:
            logger.error(f"Specified version not found for this configuration ({vehicle} and {platform}).")
            return None

        firmware_format = FirmwareDownload._supported_firmware_formats[platform]

        # Autodetect the latest supported version.
        # For .apj firmwares (e.g. Pixhawk), we use the latest STABLE version while for the others (e.g. SITL and
        # Navigator) we use latest DEV. Specially on this development phase of the companion-docker/navigator, using
        # the DEV release allow us to track and fix introduced bugs faster.
        if not version:
            if firmware_format == FirmwareFormat.APJ:
                supported_versions = [version for version in versions if "STABLE" in version]
                newest_version: Optional[str] = None
                for supported_version in supported_versions:
                    semver_version = supported_version.split("-")[1]
                    if not newest_version or Version(newest_version) < Version(semver_version):
                        newest_version = semver_version
                if not newest_version:
                    logger.error(f"No firmware versions found for this configuration ({vehicle} and {platform}).")
                    return None
                version = f"STABLE-{newest_version}"
            else:
                version = "DEV"

        items = self._find_version_item(
            vehicletype=vehicle.value,
            platform=platform.value,
            mav_firmware_version_type=version,
            format=firmware_format,
        )

        if len(items) != 1:
            logger.error(f"Invalid number of candidates to download ({len(items)}): {items}")
            return None

        item = items[0]
        logger.debug(f"Downloading following firmware: {item}")
        return str(item["url"])

    def download(self, vehicle: Vehicle, platform: Platform, version: str = "") -> Optional[pathlib.Path]:
        """Download a specific firmware that matches the arguments.

        Args:
            vehicle (Vehicle): Desired vehicle.
            platform (Platform): Desired platform.
            version (str, optional): Desired version, if None provided the latest stable will be used.
                Defaults to None.

        Returns:
            Optional[pathlib.Path]: Temporary path for the firmware file, None if unable to download or validate file.
        """
        url = self.get_download_url(vehicle, platform, version)
        if not url:
            logger.error("No valid url to download.")
            return None

        path = FirmwareDownload._download(url)

        if not path:
            logger.error("Failed to download firmware.")
            return None

        firmware_format = FirmwareDownload._supported_firmware_formats[platform]
        if firmware_format == FirmwareFormat.ELF:
            # Make the binary executable
            ## S_IX: Execution permission for
            ##    OTH: Others
            ##    USR: User
            ##    GRP: Group
            ## For more information: https://www.gnu.org/software/libc/manual/html_node/Permission-Bits.html
            path.chmod(path.stat().st_mode | stat.S_IXOTH | stat.S_IXUSR | stat.S_IXGRP)

        if not FirmwareDownload._validate_firmware(path):
            logger.error("Unable to validate firmware file.")
            return None

        return path
