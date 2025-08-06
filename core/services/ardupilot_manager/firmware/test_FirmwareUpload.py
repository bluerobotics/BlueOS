import pathlib
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from exceptions import InvalidUploadTool, UploadToolNotFound
from firmware.FirmwareUpload import FirmwareUploader


class TestFirmwareUploader:
    """Test cases for FirmwareUploader class."""

    def test_binary_name(self) -> None:
        """Test that binary_name returns the correct name."""
        assert FirmwareUploader.binary_name() == "ardupilot_fw_uploader.py"

    @patch("shutil.which")
    def test_init_binary_not_found(self, mock_which: MagicMock) -> None:
        """Test that UploadToolNotFound is raised when binary is not found."""
        mock_which.return_value = None
        with pytest.raises(UploadToolNotFound, match="Uploader binary not found on system's PATH."):
            FirmwareUploader()

    @patch("shutil.which")
    @patch("subprocess.check_output")
    def test_init_binary_invalid(self, mock_check_output: MagicMock, mock_which: MagicMock) -> None:
        """Test that InvalidUploadTool is raised when binary validation fails."""
        mock_which.return_value = "/fake/path/ardupilot_fw_uploader.py"
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "test")

        with pytest.raises(InvalidUploadTool):
            FirmwareUploader()

    @patch("shutil.which")
    @patch("subprocess.check_output")
    def test_init_success(self, mock_check_output: MagicMock, mock_which: MagicMock) -> None:
        """Test successful initialization."""
        mock_which.return_value = "/fake/path/ardupilot_fw_uploader.py"
        mock_check_output.return_value = b"help output"

        uploader = FirmwareUploader()
        assert uploader.binary() == pathlib.Path("/fake/path/ardupilot_fw_uploader.py")

    @patch("shutil.which")
    @patch("subprocess.check_output")
    def test_set_autopilot_port(self, mock_check_output: MagicMock, mock_which: MagicMock) -> None:
        """Test setting autopilot port."""
        mock_which.return_value = "/fake/path/ardupilot_fw_uploader.py"
        mock_check_output.return_value = b"help output"

        uploader = FirmwareUploader()
        new_port = pathlib.Path("/dev/ttyUSB0")
        uploader.set_autopilot_port(new_port)
        assert uploader._autopilot_port == new_port

    @patch("shutil.which")
    @patch("subprocess.check_output")
    def test_set_baudrate_bootloader(self, mock_check_output: MagicMock, mock_which: MagicMock) -> None:
        """Test setting bootloader baudrate."""
        mock_which.return_value = "/fake/path/ardupilot_fw_uploader.py"
        mock_check_output.return_value = b"help output"

        uploader = FirmwareUploader()
        uploader.set_baudrate_bootloader(921600)
        assert uploader._baudrate_bootloader == 921600

    @patch("shutil.which")
    @patch("subprocess.check_output")
    def test_set_baudrate_flightstack(self, mock_check_output: MagicMock, mock_which: MagicMock) -> None:
        """Test setting flightstack baudrate."""
        mock_which.return_value = "/fake/path/ardupilot_fw_uploader.py"
        mock_check_output.return_value = b"help output"

        uploader = FirmwareUploader()
        uploader.set_baudrate_flightstack(115200)
        assert uploader._baudrate_flightstack == 115200
