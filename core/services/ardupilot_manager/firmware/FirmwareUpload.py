import asyncio
import pathlib
import shutil
import subprocess
from typing import Awaitable, Callable, Optional

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

    async def upload(
        self,
        firmware_path: pathlib.Path,
        output_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> None:
        logger.info("Starting upload of firmware to board.")

        process = await asyncio.create_subprocess_shell(
            f"{self.binary()} {firmware_path}"
            f" --port {self._autopilot_port}"
            f" --baud-bootloader {self._baudrate_bootloader}"
            f" --baud-flightstack {self._baudrate_flightstack}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True,
        )
        errors = []

        async def read_stdout() -> None:
            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded_line = line.decode().rstrip("\n")
                    logger.debug(f"[stdout] {decoded_line}")
                    if output_callback:
                        await output_callback("stdout", decoded_line)

        async def read_stderr() -> None:
            if process.stderr:
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    decoded_line = line.decode().rstrip("\n")
                    logger.debug(f"[stderr] {decoded_line}")
                    errors.append(decoded_line)
                    if output_callback:
                        await output_callback("stderr", decoded_line)

        try:
            # Run both stream readers and process wait concurrently with a single timeout
            await asyncio.wait_for(asyncio.gather(read_stdout(), read_stderr(), process.wait()), timeout=180)

            logger.info("Successfully uploaded firmware to board.")
        except asyncio.TimeoutError as error:
            process.kill()
            raise FirmwareUploadFail("Firmware upload timed out after 180 seconds.") from error
        except Exception as error:
            process.kill()
            raise FirmwareUploadFail("Unable to upload firmware to board.") from error
        finally:
            return_code = process.returncode
            if errors and return_code != 0:
                raise FirmwareUploadFail(f"Upload process returned errors: {errors} return code: {return_code}")
            if return_code != 0:
                raise FirmwareUploadFail(f"Upload process returned non-zero code {return_code}.")

            # Give some time for the board to reboot (preventing fail reconnecting to it)
            await asyncio.sleep(10)
