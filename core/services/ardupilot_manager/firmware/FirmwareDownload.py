import asyncio
import gzip
import json
import pathlib
import random
import ssl
import string
import tempfile
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from aiocache import cached
from exceptions import (
    FirmwareDownloadFail,
    InvalidManifest,
    ManifestUnavailable,
    NoCandidate,
    NoVersionAvailable,
)
from loguru import logger
from packaging.version import Version
from typedefs import Firmware, FirmwareFormat, FlightController, PlatformType, Vehicle

# Builds sharing a board id with the main platform but meant for specific setups
PLATFORM_VARIANT_SUFFIXES = ("-bdshot", "-odid", "-1m", "-heli", "-simonhardware", "-periph", "-oem")
# Simulated sensors on real hardware and AP_Periph nodes are never firmwares for a flight controller
EXCLUDED_PLATFORM_MARKERS = ("simonhardware", "periph")


def is_platform_variant(platform: str) -> bool:
    return any(suffix in platform.lower() for suffix in PLATFORM_VARIANT_SUFFIXES)


def is_excluded_platform(platform: str) -> bool:
    return any(marker in platform.lower() for marker in EXCLUDED_PLATFORM_MARKERS)


def order_platforms(platforms: List[str], board_platform: str) -> List[str]:
    """Order platforms with the preferred one for the board first.

    The preferred platform is the one named like the board's platform, otherwise the shortest (then alphabetical)
    platform that is not a variant. The remaining platforms follow in alphabetical order. Comparisons ignore case.
    """
    unique_platforms = list(dict.fromkeys(platforms))
    exact_matches = [platform for platform in unique_platforms if platform.lower() == board_platform.lower()]
    main_platforms = sorted(
        (platform for platform in unique_platforms if not is_platform_variant(platform)),
        key=lambda platform: (len(platform), platform.lower(), platform),
    )
    candidates = exact_matches or main_platforms
    preferred = candidates[0] if candidates else None
    remaining = sorted(
        (platform for platform in unique_platforms if platform != preferred),
        key=lambda platform: (platform.lower(), platform),
    )
    return [preferred, *remaining] if preferred else remaining


def order_by_preferred_platform(firmwares: List[Firmware], board: FlightController) -> List[Firmware]:
    """Drop excluded platforms and sort by platform preference, keeping the manifest order within a platform."""
    firmwares = [firmware for firmware in firmwares if not is_excluded_platform(firmware.platform)]
    platform_order = order_platforms([firmware.platform for firmware in firmwares], board.platform.name)
    return sorted(firmwares, key=lambda firmware: platform_order.index(firmware.platform))


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
    def _create_ssl_context() -> ssl.SSLContext:
        """Create an SSL context with verification disabled for ArduPilot firmware server."""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

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
    async def _fetch(url: str, attempts: int = 5) -> bytes:
        for attempt in range(1, attempts + 1):
            try:
                connector = aiohttp.TCPConnector(ssl=FirmwareDownloader._create_ssl_context())
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        return await response.read()
            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                # Client errors (4xx) are permanent, only retry connection issues and server errors
                client_error = isinstance(error, aiohttp.ClientResponseError) and error.status < 500
                if attempt == attempts or client_error:
                    raise
                logger.warning(f"Download of {url} failed (attempt {attempt}/{attempts}): {error!r}, retrying...")
                await asyncio.sleep(2**attempt)
        raise AssertionError("unreachable")

    @staticmethod
    async def _download(url: str) -> pathlib.Path:
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
            with open(filename, "wb") as f:
                f.write(await FirmwareDownloader._fetch(url))
        except Exception as error:
            raise FirmwareDownloadFail("Could not download firmware file.") from error
        return filename

    async def _manifest_is_valid(self) -> bool:
        """Check if internal content is valid and update it if not.

        Returns:
            bool: True if valid, False if was unable to validate.
        """
        if "format-version" in self._manifest:
            return True
        return await self.download_manifest()

    async def download_manifest(self) -> bool:
        """Download ArduPilot manifest file

        Returns:
            bool: True if file was downloaded and validated, False if not.
        """
        manifest_gzip = await FirmwareDownloader._fetch(FirmwareDownloader._manifest_remote)
        self._manifest = json.loads(gzip.decompress(manifest_gzip))

        if "format-version" not in self._manifest:
            raise InvalidManifest("Invalid Manifest file. Does not contain 'format-version' key.")

        if self._manifest["format-version"] != "1.0.0":
            logger.warning("Firmware description file format changed, compatibility may be broken.")

        return True

    async def _find_version_item(self, **args: str | int) -> List[Firmware]:
        """Find version objects in the manifest that match the specific case of **args

        The arguments should follow the same name described in the dictionary inside the manifest
        for firmware item. Valid arguments can be:
            mav_type, vehicletype, mav_firmware_version_minor, format, mav_firmware_version_type,
            platform, latest and others. `-` should be replaced by `_` to use valid python arguments.
            E.g: `self._find_version_item(vehicletype="Sub", platform="Pixhawk1", mav_firmware_version_type="4.0.1")`

        Returns:
            List[Firmware]: A list of firmware items that match the arguments.
        """
        if not self._manifest and not await self.download_manifest():
            raise ManifestUnavailable("Manifest file is not available. Cannot use it to find firmware candidates.")

        found_version_item = []

        # Make sure that the item matches all args value
        for item in self._manifest["firmware"]:
            for key, value in args.items():
                real_key = key.replace("_", "-").lower() if key != "board_id" else "board_id"
                if real_key not in item or str(item[real_key]).lower() != str(value).lower():
                    break
            else:
                found_version_item.append(item)

        return [
            Firmware(
                board_id=item["board_id"] if "board_id" in item else None,
                platform=item["platform"],
                name=item["mav-firmware-version-type"],
                url=item["url"],
            )
            for item in found_version_item
        ]

    @cached(ttl=3600, namespace="firmware_versions")
    async def get_available_versions(self, vehicle: Vehicle, board: FlightController) -> List[Firmware]:
        """Get available firmware versions for the specific plataform and vehicle

        Boards with an ArduPilot board id get the firmwares of every platform built for that id, with the preferred
        platform for the board first (see `order_platforms`).

        Args:
            vehicle (Vehicle): Desired vehicle.
            board (FlightController): Desired Flight Controller.

        Returns:
            List[Firmware]: List of available versions that match the specific desired configuration.
        """
        if not await self._manifest_is_valid():
            raise InvalidManifest("Manifest file is invalid. Cannot use it to find available versions.")

        # file format (elf/apj)
        file_format = FirmwareDownloader._supported_firmware_formats[board.platform.platform_type].value
        if board.ardupilot_board_id is not None:
            firmwares = await self._find_version_item(
                vehicletype=vehicle.value,
                format=file_format,
                board_id=board.ardupilot_board_id,
            )
            return order_by_preferred_platform(firmwares, board)
        return await self._find_version_item(
            vehicletype=vehicle.value,
            platform=board.platform.name,
            format=file_format,
        )

    @cached(ttl=3600, namespace="firmware_url")
    async def get_download_url(self, vehicle: Vehicle, board: FlightController, version: str = "") -> str:
        """Find a specific firmware URL from manifest that matches the arguments.

        Args:
            vehicle (Vehicle): Desired vehicle.
            platform (Platform): Desired platform.
            version (str, optional): Desired version, if None provided the latest stable will be used.
                Defaults to None.

        Returns:
            str: URL of valid firmware.
        """
        versions = await self.get_available_versions(vehicle, board)
        logger.debug(f"Got following versions for {vehicle} running {board}: {versions}")

        if not versions:
            raise NoVersionAvailable(f"Could not find available firmware versions for {board}/{vehicle}.")

        # Versions come with the preferred platform first. For boards with a board id the others are variants built
        # for the same id, only installed when their firmware is chosen explicitly by URL.
        preferred_platform = versions[0].platform
        if board.ardupilot_board_id is not None:
            versions = [found_version for found_version in versions if found_version.platform == preferred_platform]

        if version and not any(version == found_version.name for found_version in versions):
            raise NoVersionAvailable(f"Version {version} was not found for {board}/{vehicle}.")

        firmware_format = FirmwareDownloader._supported_firmware_formats[board.platform.platform_type].value

        # Autodetect the latest supported version.
        # For .apj firmwares (e.g. Pixhawk), we use the latest STABLE version while for the others (e.g. SITL and
        # Navigator) we use latest BETA. Specially on this development phase of the BlueOS/navigator, using
        # the BETA release allow us to track and fix introduced bugs faster.
        if not version:
            if firmware_format == FirmwareFormat.APJ:
                supported_versions = [version for version in versions if "STABLE" in version.name]
                newest_version: Optional[str] = None
                for supported_version in supported_versions:
                    semver_version = supported_version.name.split("-")[1]
                    if not newest_version or Version(newest_version) < Version(semver_version):
                        newest_version = semver_version
                if not newest_version:
                    raise NoVersionAvailable(f"No firmware versions found for {board}/{vehicle}.")
                version = f"STABLE-{newest_version}"
            else:
                version = "BETA"
        board_id_filter = {"board_id": board.ardupilot_board_id} if board.ardupilot_board_id is not None else {}
        items = await self._find_version_item(
            vehicletype=vehicle.value,
            platform=preferred_platform,
            mav_firmware_version_type=version,
            format=firmware_format,
            **board_id_filter,
        )

        if len(items) == 0:
            raise NoCandidate(
                f"Found no candidate for configuration: {vehicle=}, {board=}, {version=}, {firmware_format=}"
            )

        if len(items) != 1:
            logger.warning(f"Found a number of candidates different of one ({len(items)}): {items}.")

        item = items[0]
        logger.debug(f"Downloading following firmware: {item}")
        return item.url

    async def download(self, vehicle: Vehicle, board: FlightController, version: str = "") -> pathlib.Path:
        """Download a specific firmware that matches the arguments.

        Args:
            vehicle (Vehicle): Desired vehicle.
            board (FlightController): Desired board.
            version (str, optional): Desired version, if None provided the latest stable will be used.
                Defaults to None.

        Returns:
            pathlib.Path: Temporary path for the firmware file.
        """
        url = await self.get_download_url(vehicle, board, version)
        return await FirmwareDownloader._download(url)
