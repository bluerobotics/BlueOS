import asyncio
import pathlib
import shutil
import subprocess
from typing import Awaitable, Callable, Optional

from loguru import logger

from exceptions import FirmwareUploadFail, InvalidUploadTool, UploadToolNotFound


class StreamReader:
    """Reads a stream byte-by-byte, treating both \\n and \\r as line delimiters.

    Automatically sends buffered data after 1 second of inactivity.
    """

    def __init__(
        self,
        stream: asyncio.StreamReader,
        stream_name: str,
        output_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
        timeout: float = 1.0,
    ) -> None:
        self.stream = stream
        self.stream_name = stream_name
        self.output_callback = output_callback
        self.timeout = timeout
        self.buffer = b""
        self.lines: list[str] = []

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
        while True:
            try:
                # Try to read one byte with timeout
                chunk = await asyncio.wait_for(self.stream.read(1), timeout=self.timeout)
                if not chunk:
                    # End of stream - send any remaining buffer
                    await self._flush_buffer()
                    break

                self.buffer += chunk

                # Check if we hit a line delimiter (\n or \r)
                if chunk in (b"\n", b"\r"):
                    decoded_line = self.buffer.decode().rstrip("\r\n")
                    await self._send_line(decoded_line)
                    self.buffer = b""
            except asyncio.TimeoutError:
                # Timeout passed without new data - send buffer if non-empty
                await self._flush_buffer()


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
        stdout_reader = StreamReader(process.stdout, "stdout", output_callback) if process.stdout else None
        stderr_reader = StreamReader(process.stderr, "stderr", output_callback) if process.stderr else None

        async def read_stdout() -> None:
            if stdout_reader:
                await stdout_reader.read_all()

        async def read_stderr() -> None:
            if stderr_reader:
                await stderr_reader.read_all()

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
            errors = stderr_reader.lines if stderr_reader else []
            if errors and return_code != 0:
                raise FirmwareUploadFail(f"Upload process returned errors: {errors} return code: {return_code}")
            if return_code != 0:
                raise FirmwareUploadFail(f"Upload process returned non-zero code {return_code}.")

            # Give some time for the board to reboot (preventing fail reconnecting to it)
            await asyncio.sleep(10)
