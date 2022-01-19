import pathlib
import shutil
import subprocess
import threading
import time

from loguru import logger

from exceptions import FirmwareUploadFail, InvalidUploadTool, UploadToolNotFound


class FirmwareUploader:
    def __init__(self) -> None:
        self._autopilot_port: pathlib.Path = pathlib.Path("/dev/autopilot")
        self._baudrate_bootloader: int = 115200
        self._baudrate_flightstack: int = 57600

        binary_path = shutil.which(self.binary_name())
        if binary_path is None:
            raise UploadToolNotFound("Uploader binary not found on system's PATH.")
        self._binary = pathlib.Path(binary_path)

        self.validate_binary()

    @staticmethod
    def binary_name() -> str:
        return "ardupilot_fw_uploader.py"

    def binary(self) -> pathlib.Path:
        return self._binary

    def validate_binary(self) -> None:
        try:
            subprocess.check_output([self.binary(), "--help"])
        except subprocess.CalledProcessError as error:
            raise InvalidUploadTool(f"Binary returned {error.returncode} on '--help' call: {error.output}") from error

    def set_autopilot_port(self, port: pathlib.Path) -> None:
        self._autopilot_port = port

    def set_baudrate_bootloader(self, baudrate: int) -> None:
        self._baudrate_bootloader = baudrate

    def set_baudrate_flightstack(self, baudrate: int) -> None:
        self._baudrate_flightstack = baudrate

    def upload(self, firmware_path: pathlib.Path) -> None:
        logger.info("Starting upload of firmware to board.")
        # pylint: disable=consider-using-with
        process = subprocess.Popen(
            f"{self.binary()} {firmware_path}"
            f" --port {self._autopilot_port}"
            f" --baud-bootloader {self._baudrate_bootloader}"
            f" --baud-flightstack {self._baudrate_flightstack}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            encoding="utf-8",
        )

        # Using a timer of 180 seconds to prevent being stuck on upload. Upload usually takes 20-40 seconds.
        timer = threading.Timer(180, process.kill)
        try:
            timer.start()
            if process.stdout is not None:
                for line in iter(process.stdout.readline, b""):
                    logger.debug(line)
                    if process.poll() is not None:
                        break
            while process.poll() is None:
                logger.debug("Waiting for upload tool to finish its job.")
                time.sleep(0.5)
            if process.returncode != 0:
                raise FirmwareUploadFail(f"Upload process returned non-zero code {process.returncode}.")
            logger.info("Successfully uploaded firmware to board.")
        except Exception as error:
            process.kill()
            raise FirmwareUploadFail(f"Unable to upload firmware: {error}") from error
        finally:
            timer.cancel()
