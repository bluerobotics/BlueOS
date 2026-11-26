import asyncio
import os
import platform
from typing import Any, Dict, List

import aiohttp
import pytest
from firmware.FirmwareDownload import FirmwareDownloader
from typedefs import FlightController, Platform, PlatformType, Vehicle


def manifest_item(board_id: int, platform_name: str, version: str = "STABLE-4.5.0") -> Dict[str, Any]:
    return {
        "board_id": board_id,
        "platform": platform_name,
        "vehicletype": "Sub",
        "format": "apj",
        "mav-firmware-version-type": version,
        "url": f"https://firmware.invalid/{platform_name}/{version}/ardusub.apj",
    }


FAKE_MANIFEST = {
    "format-version": "1.0.0",
    "firmware": [
        manifest_item(140, "CubeOrange-SimOnHardWare"),
        manifest_item(140, "CubeOrange-bdshot"),
        manifest_item(140, "CubeOrange-ODID"),
        manifest_item(140, "CubeOrange"),
        manifest_item(140, "CubeOrange", "BETA"),
        manifest_item(140, "CubeOrange-periph"),
        manifest_item(9, "fmuv3"),
        manifest_item(9, "Pixhawk1-1M"),
        manifest_item(9, "fmuv2"),
        manifest_item(9, "Pixhawk1"),
    ],
}


def serial_board(platform_name: str, board_id: int) -> FlightController:
    return FlightController(
        name=platform_name,
        platform=Platform(name=platform_name, platform_type=PlatformType.Serial),
        ardupilot_board_id=board_id,
    )


def fake_downloader() -> FirmwareDownloader:
    downloader = FirmwareDownloader()
    downloader._manifest = FAKE_MANIFEST
    return downloader


async def available_platforms(board: FlightController) -> List[str]:
    return [firmware.platform for firmware in await fake_downloader().get_available_versions(Vehicle.Sub, board)]


def test_available_versions_prefer_board_platform() -> None:
    assert asyncio.run(available_platforms(serial_board("CubeOrange", 140))) == [
        "CubeOrange",
        "CubeOrange",
        "CubeOrange-bdshot",
        "CubeOrange-ODID",
    ]
    assert asyncio.run(available_platforms(serial_board("CubeOrange-bdshot", 140)))[:2] == [
        "CubeOrange-bdshot",
        "CubeOrange",
    ]
    assert asyncio.run(available_platforms(serial_board("Pixhawk1", 9))) == [
        "Pixhawk1",
        "fmuv2",
        "fmuv3",
        "Pixhawk1-1M",
    ]


def test_available_versions_without_matching_platform_prefer_shortest_main_platform() -> None:
    assert asyncio.run(available_platforms(serial_board("GenericSerial", 140)))[0] == "CubeOrange"
    assert asyncio.run(available_platforms(serial_board("GenericSerial", 9))) == [
        "fmuv2",
        "fmuv3",
        "Pixhawk1",
        "Pixhawk1-1M",
    ]


def test_available_versions_keep_manifest_order_within_platform() -> None:
    versions = asyncio.run(fake_downloader().get_available_versions(Vehicle.Sub, serial_board("CubeOrange", 140)))
    assert [firmware.name for firmware in versions[:2]] == ["STABLE-4.5.0", "BETA"]


def test_download_url_uses_preferred_platform() -> None:
    async def url(board: FlightController) -> str:
        download_url: str = await fake_downloader().get_download_url(Vehicle.Sub, board)
        return download_url

    assert asyncio.run(url(serial_board("CubeOrange", 140))).startswith("https://firmware.invalid/CubeOrange/")
    assert asyncio.run(url(serial_board("CubeOrange-bdshot", 140))).startswith(
        "https://firmware.invalid/CubeOrange-bdshot/"
    )
    assert asyncio.run(url(serial_board("Pixhawk1", 9))).startswith("https://firmware.invalid/Pixhawk1/")


Pixhawk1 = FlightController(
    name="Pixhawk1",
    manufacturer="3DR",
    platform=Platform(name="Pixhawk1", platform_type=PlatformType.Serial),
    ardupilot_board_id=9,
)
Pixhawk4 = FlightController(
    name="Pixhawk4",
    manufacturer="Holybro",
    platform=Platform(name="Pixhawk4", platform_type=PlatformType.Serial),
    ardupilot_board_id=50,
)
SITL = FlightController(
    name="SITL",
    manufacturer="ArduPilot Team",
    platform=Platform.SITL(),
)
Navigator = FlightController(
    name="Navigator",
    manufacturer="Blue Robotics",
    platform=Platform(name="Navigator", platform_type=PlatformType.Linux),
)


def test_static() -> None:
    async def static_wrapper() -> None:
        downloaded_file = await FirmwareDownloader._download(FirmwareDownloader._manifest_remote)
        assert downloaded_file, "Failed to download file."
        assert downloaded_file.exists(), "Download file does not exist."

        smaller_valid_size_bytes = 180 * 1024
        assert downloaded_file.stat().st_size > smaller_valid_size_bytes, "Download file size is not big enough."

    asyncio.run(static_wrapper())


def test_firmware_download() -> None:
    async def firmware_download_wrapper() -> None:
        firmware_download = FirmwareDownloader()
        assert await firmware_download.download_manifest(), "Failed to download/validate manifest file."

        versions = await firmware_download._find_version_item(
            vehicletype="Sub", format="apj", mav_firmware_version_type="STABLE-4.0.1", platform=Pixhawk1.platform.name
        )
        assert len(versions) == 1, "Failed to find a single firmware."

        versions = await firmware_download._find_version_item(
            vehicletype="Sub", mav_firmware_version_type="STABLE-4.0.1", platform=Pixhawk1.platform.name
        )
        # There are two versions, one for the firmware and one with the bootloader
        assert len(versions) == 2, "Failed to find multiple versions."

        available_versions = await firmware_download.get_available_versions(Vehicle.Sub, Pixhawk1)
        assert len(available_versions) == len(set(available_versions)), "Available versions are not unique."

        test_available_versions = ["STABLE-4.0.1", "STABLE-4.0.0", "OFFICIAL", "DEV", "BETA"]
        assert len(set(available_versions)) >= len(
            set(test_available_versions)
        ), "Available versions are missing know versions."

        assert await firmware_download.download(
            Vehicle.Sub, Pixhawk1, "STABLE-4.0.1"
        ), "Failed to download a valid firmware file."

        # Board id 9 is shared by Pixhawk1, fmuv2, fmuv3 and variants, the board's own platform must be picked
        assert "/Pixhawk1/" in await firmware_download.get_download_url(Vehicle.Sub, Pixhawk1)
        assert await firmware_download.download(Vehicle.Sub, Pixhawk1), "Failed to download latest valid firmware file."

        assert await firmware_download.download(Vehicle.Sub, Pixhawk4), "Failed to download latest valid firmware file."

        assert await firmware_download.download(Vehicle.Sub, SITL), "Failed to download SITL."

        # skipt these tests for MacOS
        if platform.system() == "Darwin":
            pytest.skip("Skipping test for MacOS")
        # It'll fail if running in an arch different of ARM
        if "x86" in os.uname().machine:
            assert await firmware_download.download(Vehicle.Sub, Navigator), "Failed to download navigator binary."
        else:
            with pytest.raises(Exception):
                await firmware_download.download(Vehicle.Sub, Navigator)

    asyncio.run(firmware_download_wrapper())


def test_fetch_retries_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    class FakeResponse:
        status = 200

        def raise_for_status(self) -> None:
            pass

        async def read(self) -> bytes:
            return b"data"

        async def __aenter__(self) -> "FakeResponse":
            calls["count"] += 1
            if calls["count"] < 3:
                raise aiohttp.ClientConnectionError()
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(aiohttp.ClientSession, "get", lambda *_, **__: FakeResponse())
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    assert asyncio.run(FirmwareDownloader._fetch("https://example.invalid/file")) == b"data"
    assert calls["count"] == 3


def test_fetch_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    class NotFoundResponse:
        async def __aenter__(self) -> "NotFoundResponse":
            calls["count"] += 1
            raise aiohttp.ClientResponseError(None, (), status=404)  # type: ignore[arg-type]

        async def __aexit__(self, *_: object) -> None:
            pass

    monkeypatch.setattr(aiohttp.ClientSession, "get", lambda *_, **__: NotFoundResponse())
    with pytest.raises(aiohttp.ClientResponseError):
        asyncio.run(FirmwareDownloader._fetch("https://example.invalid/file"))
    assert calls["count"] == 1


def test_fetch_gives_up_after_all_attempts_on_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0, "sleeps": 0}

    class ServerErrorResponse:
        async def __aenter__(self) -> "ServerErrorResponse":
            calls["count"] += 1
            raise aiohttp.ClientResponseError(None, (), status=503)  # type: ignore[arg-type]

        async def __aexit__(self, *_: object) -> None:
            pass

    async def counting_sleep(_: float) -> None:
        calls["sleeps"] += 1

    monkeypatch.setattr(aiohttp.ClientSession, "get", lambda *_, **__: ServerErrorResponse())
    monkeypatch.setattr(asyncio, "sleep", counting_sleep)
    with pytest.raises(aiohttp.ClientResponseError):
        asyncio.run(FirmwareDownloader._fetch("https://example.invalid/file", attempts=3))
    assert calls == {"count": 3, "sleeps": 2}
