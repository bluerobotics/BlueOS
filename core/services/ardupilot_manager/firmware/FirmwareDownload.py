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

from commonwealth.utils.decorators import temporary_cache
from loguru import logger
from packaging.version import Version

from exceptions import (
    FirmwareDownloadFail,
    InvalidManifest,
    ManifestUnavailable,
    NoCandidate,
    NoVersionAvailable,
)
from typedefs import FirmwareFormat, Platform, PlatformType, Vehicle

# TODO: This should be not necessary
# Disable SSL verification
if not os.environ.get("PYTHONHTTPSVERIFY", "") and getattr(ssl, "_create_unverified_context", None):
    ssl._create_default_https_context = ssl._create_unverified_context


class FirmwareDownloader:
    _manifest_remote = "https://firmware.ardupilot.org/manifest.json.gz"
    _supported_firmware_formats = {
        PlatformType.SITL: FirmwareFormat.ELF,
        PlatformType.Serial: FirmwareFormat.APJ,
        PlatformType.Linux: FirmwareFormat.ELF,
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
    def _download(url: str) -> pathlib.Path:
        """Download a specific file for a temporary location.

        Args:
            url (str): Url to download the file.

        Returns:
            pathlib.Path: File of the temporary file.
        """

        # We append the url filename to the generated random name to avoid collisions and preserve extension
        name = pathlib.Path(urlparse(url).path).name
        filename = pathlib.Path(f"{FirmwareDownloader._generate_random_filename()}-{name}")
        try:
            logger.debug(f"Downloading: {url}")
            urlretrieve(url, filename)
        except Exception as error:
            raise FirmwareDownloadFail("Could not download firmware file.") from error
        return filename

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
        with urlopen(FirmwareDownloader._manifest_remote) as http_response:
            manifest_gzip = http_response.read()
            manifest = gzip.decompress(manifest_gzip)
            self._manifest = json.loads(manifest)

        if "format-version" not in self._manifest:
            raise InvalidManifest("Invalid Manifest file. Does not contain 'format-version' key.")

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
            raise ManifestUnavailable("Manifest file is not available. Cannot use it to find firmware candidates.")

        found_version_item = []

        # Make sure that the item matches all args value
        for item in self._manifest["firmware"]:
            for key, value in args.items():
                real_key = key.replace("_", "-")
                if real_key not in item or item[real_key] != value:
                    break
            else:
                found_version_item.append(item)

        return found_version_item

    @temporary_cache(timeout_seconds=3600)
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
            raise InvalidManifest("Manifest file is invalid. Cannot use it to find available versions.")

        items = self._find_version_item(vehicletype=vehicle.value, platform=platform.value)

        for item in items:
            if item["format"] == FirmwareDownloader._supported_firmware_formats[platform.type]:
                available_versions.append(item["mav-firmware-version-type"])

        return available_versions

    @temporary_cache(timeout_seconds=3600)
    def get_download_url(self, vehicle: Vehicle, platform: Platform, version: str = "") -> str:
        """Find a specific firmware URL from manifest that matches the arguments.

        Args:
            vehicle (Vehicle): Desired vehicle.
            platform (Platform): Desired platform.
            version (str, optional): Desired version, if None provided the latest stable will be used.
                Defaults to None.

        Returns:
            str: URL of valid firmware.
        """
        versions = self.get_available_versions(vehicle, platform)
        logger.debug(f"Got following versions for {vehicle} running {platform}: {versions}")

        if not versions:
            raise NoVersionAvailable(f"Could not find available firmware versions for {platform}/{vehicle}.")

        if version and version not in versions:
            raise NoVersionAvailable(f"Version {version} was not found for {platform}/{vehicle}.")

        firmware_format = FirmwareDownloader._supported_firmware_formats[platform.type]

        # Autodetect the latest supported version.
        # For .apj firmwares (e.g. Pixhawk), we use the latest STABLE version while for the others (e.g. SITL and
        # Navigator) we use latest BETA. Specially on this development phase of the blueos-docker/navigator, using
        # the BETA release allow us to track and fix introduced bugs faster.
        if not version:
            if firmware_format == FirmwareFormat.APJ:
                supported_versions = [version for version in versions if "STABLE" in version]
                newest_version: Optional[str] = None
                for supported_version in supported_versions:
                    semver_version = supported_version.split("-")[1]
                    if not newest_version or Version(newest_version) < Version(semver_version):
                        newest_version = semver_version
                if not newest_version:
                    raise NoVersionAvailable(f"No firmware versions found for {platform}/{vehicle}.")
                version = f"STABLE-{newest_version}"
            else:
                version = "BETA"

        items = self._find_version_item(
            vehicletype=vehicle.value,
            platform=platform.value,
            mav_firmware_version_type=version,
            format=firmware_format,
        )

        if len(items) == 0:
            raise NoCandidate(
                f"Found no candidate for configuration: {vehicle=}, {platform=}, {version=}, {firmware_format=}"
            )

        if len(items) != 1:
            logger.warning(f"Found a number of candidates different of one ({len(items)}): {items}.")

        item = items[0]
        logger.debug(f"Downloading following firmware: {item}")
        return str(item["url"])

    def download(self, vehicle: Vehicle, platform: Platform, version: str = "") -> pathlib.Path:
        """Download a specific firmware that matches the arguments.

        Args:
            vehicle (Vehicle): Desired vehicle.
            platform (Platform): Desired platform.
            version (str, optional): Desired version, if None provided the latest stable will be used.
                Defaults to None.

        Returns:
            pathlib.Path: Temporary path for the firmware file.
        """
        url = self.get_download_url(vehicle, platform, version)
        return FirmwareDownloader._download(url)
