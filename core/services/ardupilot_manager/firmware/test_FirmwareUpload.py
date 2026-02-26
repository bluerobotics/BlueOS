import asyncio
import pathlib
import subprocess
from unittest.mock import AsyncMock, patch

import pytest
from exceptions import InvalidUploadTool, UploadToolNotFound
from firmware.FirmwareUpload import FirmwareUploader


class TestFirmwareUpload:
    def test_init_success(self) -> None:
        with patch("shutil.which", return_value="ardupilot_fw_uploader.py"):
            uploader = FirmwareUploader()
            assert uploader._autopilot_port == pathlib.Path("/dev/autopilot")
            assert uploader._baudrate_bootloader == 115200
            assert uploader._baudrate_flightstack == 57600
            assert uploader._binary == pathlib.Path("ardupilot_fw_uploader.py")

    def test_init_binary_not_found(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(UploadToolNotFound, match="Uploader binary not found on system's PATH."):
                FirmwareUploader()

    def test_binary_name(self) -> None:
        assert FirmwareUploader.binary_name() == "ardupilot_fw_uploader.py"

    def test_binary(self) -> None:
        with patch("shutil.which", return_value="ardupilot_fw_uploader.py"), patch.object(
            FirmwareUploader, "validate_binary"
        ):
            uploader = FirmwareUploader()
            assert uploader.binary() == pathlib.Path("ardupilot_fw_uploader.py")

    def test_validate_binary_success(self) -> None:
        with patch("shutil.which", return_value="ardupilot_fw_uploader.py"):
            uploader = FirmwareUploader()
            uploader.validate_binary()

    def test_validate_binary_failure(self) -> None:
        with patch("shutil.which", return_value="ardupilot_fw_uploader.py"):
            uploader = FirmwareUploader()

        with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(2, "cmd", "error output")):
            with pytest.raises(InvalidUploadTool, match="Binary returned 2 on '--help' call: error output"):
                uploader.validate_binary()

    def test_set_autopilot_port(self) -> None:
        with patch("shutil.which", return_value="ardupilot_fw_uploader.py"):
            uploader = FirmwareUploader()
            new_port = pathlib.Path("/dev/autopilot2")
            uploader.set_autopilot_port(new_port)
            assert uploader._autopilot_port == new_port

    def test_set_baudrate_bootloader(self) -> None:
        with patch("shutil.which", return_value="ardupilot_fw_uploader.py"):
            uploader = FirmwareUploader()
            new_baudrate = 57600
            uploader.set_baudrate_bootloader(new_baudrate)
            assert uploader._baudrate_bootloader == new_baudrate

    def test_set_baudrate_flightstack(self) -> None:
        with patch("shutil.which", return_value="ardupilot_fw_uploader.py"):
            uploader = FirmwareUploader()
            new_baudrate = 38400
            uploader.set_baudrate_flightstack(new_baudrate)
            assert uploader._baudrate_flightstack == new_baudrate

    @pytest.mark.asyncio
    async def test_upload_success(self) -> None:
        with patch("shutil.which", return_value="ardupilot_fw_uploader.py"), patch.object(
            FirmwareUploader, "validate_binary"
        ):
            uploader = FirmwareUploader()

        firmware_path = pathlib.Path("/tmp/test_firmware.bin")

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[b"Upload starting...\n", b"Progress: 50%\n", b"Upload complete!\n", b""]
        )
        mock_process.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_shell", return_value=mock_process) as mock_create_subprocess, patch(
            "asyncio.sleep"
        ) as mock_sleep, patch("loguru.logger.info") as mock_info, patch("loguru.logger.debug") as mock_debug:

            await uploader.upload(firmware_path)

        expected_command = (
            f"ardupilot_fw_uploader.py {firmware_path}"
            f" --port /dev/autopilot"
            f" --baud-bootloader 115200"
            f" --baud-flightstack 57600"
        )

        mock_create_subprocess.assert_called_once_with(
            expected_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True,
        )

        mock_info.assert_any_call("Starting upload of firmware to board.")
        mock_info.assert_any_call("Successfully uploaded firmware to board.")
        mock_debug.assert_any_call("Upload starting...")
        mock_debug.assert_any_call("Progress: 50%")
        mock_debug.assert_any_call("Upload complete!")

        mock_sleep.assert_called_with(10)
