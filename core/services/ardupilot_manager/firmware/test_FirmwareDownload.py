import asyncio
import os
import platform

import aiohttp
import pytest
from firmware.FirmwareDownload import FirmwareDownloader
from typedefs import Platform, Vehicle


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
            vehicletype="Sub", format="apj", mav_firmware_version_type="STABLE-4.0.1", platform=Platform.Pixhawk1
        )
        assert len(versions) == 1, "Failed to find a single firmware."

        versions = await firmware_download._find_version_item(
            vehicletype="Sub", mav_firmware_version_type="STABLE-4.0.1", platform=Platform.Pixhawk1
        )
        # There are two versions, one for the firmware and one with the bootloader
        assert len(versions) == 2, "Failed to find multiple versions."

        available_versions = await firmware_download.get_available_versions(Vehicle.Sub, Platform.Pixhawk1)
        assert len(available_versions) == len(set(available_versions)), "Available versions are not unique."

        test_available_versions = ["STABLE-4.0.1", "STABLE-4.0.0", "OFFICIAL", "DEV", "BETA"]
        assert len(set(available_versions)) >= len(
            set(test_available_versions)
        ), "Available versions are missing know versions."

        assert await firmware_download.download(
            Vehicle.Sub, Platform.Pixhawk1, "STABLE-4.0.1"
        ), "Failed to download a valid firmware file."

        assert await firmware_download.download(
            Vehicle.Sub, Platform.Pixhawk1
        ), "Failed to download latest valid firmware file."

        assert await firmware_download.download(
            Vehicle.Sub, Platform.Pixhawk4
        ), "Failed to download latest valid firmware file."

        assert await firmware_download.download(Vehicle.Sub, Platform.SITL), "Failed to download SITL."

        # skipt these tests for MacOS
        if platform.system() == "Darwin":
            pytest.skip("Skipping test for MacOS")
        # It'll fail if running in an arch different of ARM
        if "x86" in os.uname().machine:
            assert await firmware_download.download(
                Vehicle.Sub, Platform.Navigator
            ), "Failed to download navigator binary."
        else:
            with pytest.raises(Exception):
                await firmware_download.download(Vehicle.Sub, Platform.Navigator)

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
