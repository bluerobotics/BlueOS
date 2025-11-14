import asyncio
import os
import pathlib
import shutil
import subprocess
import time
from typing import Awaitable, Callable, Optional

import serial
from exceptions import FirmwareUploadFail, InvalidUploadTool, UploadToolNotFound
from loguru import logger

# PROTO_BOOT followed by PROTO_EOC, from ArduPilot's bootloader protocol
BOOTLOADER_BOOT_COMMAND = b"\x30\x20"


class SharedActivityTracker:
    """Tracks the last activity time across multiple stream readers."""

    def __init__(self) -> None:
        self.last_activity = time.monotonic()

    def mark_activity(self) -> None:
        """Mark that activity occurred on any stream."""
        self.last_activity = time.monotonic()

    def seconds_since_last_activity(self) -> float:
        """Return seconds since last activity on any stream."""
        return time.monotonic() - self.last_activity


class StreamReader:
    """Reads a stream byte-by-byte, treating both \\n and \\r as line delimiters.

    Automatically sends buffered data after 1 second of inactivity.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        stream: asyncio.StreamReader,
        stream_name: str,
        output_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
        timeout: float = 1.0,
        activity_tracker: Optional[SharedActivityTracker] = None,
    ) -> None:
        self.stream = stream
        self.stream_name = stream_name
        self.output_callback = output_callback
        self.timeout = timeout
        self.buffer = b""
        self.lines: list[str] = []
        self.activity_tracker = activity_tracker or SharedActivityTracker()

    async def _send_line(self, line: str) -> None:
        """Send a decoded line through the callback and logger."""
        if line:
            logger.debug(f"[{self.stream_name}] {line}")
            self.lines.append(line)
            if self.output_callback:
                await self.output_callback(self.stream_name, line)

    async def _flush_buffer(self) -> None:
        """Flush the current buffer and send as a line."""
        if self.buffer:
            decoded_line = self.buffer.decode().rstrip("\r\n")
            await self._send_line(decoded_line)
            self.buffer = b""

    async def read_all(self) -> None:
        """Read all data from the stream until it closes."""
        max_idle_seconds = 10

        while True:
            try:
                # Try to read one byte with timeout
                chunk = await asyncio.wait_for(self.stream.read(1), timeout=self.timeout)
                if not chunk:
                    # End of stream - send any remaining buffer
                    await self._flush_buffer()
                    break

                # Mark activity on successful read
                self.activity_tracker.mark_activity()
                self.buffer += chunk

                # Check if we hit a line delimiter (\n or \r)
                if chunk in (b"\n", b"\r"):
                    decoded_line = self.buffer.decode().rstrip("\r\n")
                    await self._send_line(decoded_line)
                    self.buffer = b""
            except asyncio.TimeoutError:
                # Timeout passed without new data - send buffer if non-empty
                await self._flush_buffer()

                # Check if BOTH streams have been idle (using shared tracker)
                idle_time = self.activity_tracker.seconds_since_last_activity()
                if idle_time >= max_idle_seconds:
                    logger.debug(
                        f"[{self.stream_name}] All streams inactive for {idle_time:.1f} seconds, assuming closed"
                    )
                    break


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

    async def _send_control_message(
        self,
        message: str,
        output_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> None:
        """Send a control message through the output callback."""
        if output_callback:
            await output_callback("control", message)

    async def upload(
        self,
        firmware_path: pathlib.Path,
        output_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> None:
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

        async def handle_output(stream_name: str, line: str) -> None:
            nonlocal board_mismatch
            if output_callback:
                await output_callback(stream_name, line)
            # The uploader keeps retrying forever after refusing a firmware built for another board
            if "Firmware not suitable for this board" in line:
                board_mismatch = True
                raise FirmwareUploadFail(line)

        # Create shared activity tracker for both streams
        activity_tracker = SharedActivityTracker()
        stdout_reader = (
            StreamReader(process.stdout, "stdout", handle_output, activity_tracker=activity_tracker)
            if process.stdout
            else None
        )
        stderr_reader = (
            StreamReader(process.stderr, "stderr", handle_output, activity_tracker=activity_tracker)
            if process.stderr
            else None
        )

        tasks = [asyncio.ensure_future(reader.read_all()) for reader in (stdout_reader, stderr_reader) if reader]
        try:
            # Run both stream readers and process wait concurrently with a single timeout
            await asyncio.wait_for(asyncio.gather(*tasks, process.wait()), timeout=180)

            return_code = process.returncode
            if return_code != 0:
                uploader_error = "\n".join(stderr_reader.lines) if stderr_reader else ""
                raise FirmwareUploadFail(f"Upload process returned non-zero code {return_code}: {uploader_error}")

            logger.info("Successfully uploaded firmware to board.")
            # Send control message indicating successful completion
            await self._send_control_message("done", output_callback)
        except asyncio.TimeoutError as error:
            await self._send_control_message("error", output_callback)
            raise FirmwareUploadFail("Firmware upload timed out after 180 seconds.") from error
        except Exception as error:
            await self._send_control_message("error", output_callback)
            raise FirmwareUploadFail(f"Unable to upload firmware to board: {error}") from error
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if board_mismatch:
                # Nothing was flashed, but the uploader left the board in its bootloader, so ask it to boot the firmware
                try:
                    await asyncio.to_thread(self.boot_existing_firmware)
                except serial.SerialException as error:
                    logger.warning(f"Could not ask the bootloader to boot the existing firmware: {error}")
            # Give some time for the board to reboot (preventing fail reconnecting to it)
            await asyncio.sleep(10)
