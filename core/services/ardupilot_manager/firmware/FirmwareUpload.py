import asyncio
import os
import pathlib
import shutil
import subprocess

import serial
from exceptions import FirmwareUploadFail, InvalidUploadTool, UploadToolNotFound
from loguru import logger

# PROTO_BOOT followed by PROTO_EOC, from ArduPilot's bootloader protocol
BOOTLOADER_BOOT_COMMAND = b"\x30\x20"


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

    def boot_existing_firmware(self) -> None:
        with serial.Serial(str(self._autopilot_port), self._baudrate_bootloader) as port:
            port.write(BOOTLOADER_BOOT_COMMAND)

    async def upload(self, firmware_path: pathlib.Path) -> None:
        logger.info("Starting upload of firmware to board.")

        # No shell in between, so killing the process stops the uploader itself instead of orphaning it (dash does not
        # exec), and unbuffered output, so the uploader's messages are read as they are printed
        process = await asyncio.create_subprocess_exec(
            self.binary(),
            firmware_path,
            "--port",
            str(self._autopilot_port),
            "--baud-bootloader",
            str(self._baudrate_bootloader),
            "--baud-flightstack",
            str(self._baudrate_flightstack),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        board_mismatch = False

        async def monitor_uploader_process() -> None:
            nonlocal board_mismatch
            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    output = line.decode().strip()
                    logger.debug(output)
                    # The uploader keeps retrying forever after refusing a firmware built for another board
                    if "Firmware not suitable for this board" in output:
                        board_mismatch = True
                        raise FirmwareUploadFail(output)

            while True:
                if process.returncode is not None:
                    break
                logger.debug("Waiting for upload process to finish.")
                await asyncio.sleep(1)

        try:
            await asyncio.wait_for(monitor_uploader_process(), timeout=180)

            return_code = await process.wait()
            if return_code != 0:
                uploader_error = (await process.stderr.read()).decode().strip() if process.stderr else ""
                raise FirmwareUploadFail(f"Upload process returned non-zero code {return_code}: {uploader_error}")

            logger.info("Successfully uploaded firmware to board.")
        except asyncio.TimeoutError as error:
            raise FirmwareUploadFail("Firmware upload timed out after 180 seconds.") from error
        except Exception as error:
            raise FirmwareUploadFail(f"Unable to upload firmware to board: {error}") from error
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if board_mismatch:
                # Nothing was flashed, but the uploader left the board in its bootloader, so ask it to boot the firmware
                try:
                    await asyncio.to_thread(self.boot_existing_firmware)
                except serial.SerialException as error:
                    logger.warning(f"Could not ask the bootloader to boot the existing firmware: {error}")
            # Give some time for the board to reboot (preventing fail reconnecting to it)
            await asyncio.sleep(10)
