import pathlib
import shutil
import subprocess
from typing import Any, List, Optional, Union

import psutil
from loguru import logger


class Dnsmasq:
    def __init__(self, config_path: pathlib.Path, interface: str) -> None:
        self._subprocess: Optional[Any] = None

        if interface not in psutil.net_if_stats():
            raise ValueError(f"Interface '{interface}' not found. Available interfaces are {psutil.net_if_stats()}.")
        self._interface = interface

        binary_path = shutil.which(self.binary_name())
        if binary_path is None:
            logger.error("Dnsmasq binary not found on system's PATH.")
            raise ValueError

        self._binary = pathlib.Path(binary_path)
        assert self.is_binary_working()

        self._config_path = config_path
        assert self.is_valid_config()

    @staticmethod
    def binary_name() -> str:
        return "dnsmasq"

    def binary(self) -> pathlib.Path:
        return self._binary

    def is_binary_working(self) -> bool:
        if self.binary() is None:
            return False

        try:
            subprocess.check_output([self.binary(), "--test"])
            return True
        except subprocess.CalledProcessError as error:
            logger.error(f"Invalid binary: {error}")
            return False

    def config_path(self) -> pathlib.Path:
        return self._config_path

    def is_valid_config(self) -> bool:
        try:
            subprocess.check_output([*self.command_list(), "--test"])
            return True
        except subprocess.CalledProcessError as error:
            logger.error(f"Invalid configuration file: {error}")
            return False

    def command_list(self) -> List[Union[str, pathlib.Path]]:
        return [self.binary(), "--no-daemon", f"--interface={self._interface}", f"--conf-file={self.config_path()}"]

    def start(self) -> None:
        try:
            # pylint: disable=consider-using-with
            self._subprocess = subprocess.Popen(self.command_list(), shell=False, encoding="utf-8", errors="ignore")
            logger.info("DHCP Server started.")
        except Exception as error:
            raise RuntimeError(f"Unable to start DHCP Server: {error}") from error

    def stop(self) -> None:
        if self.is_running():
            assert self._subprocess is not None
            self._subprocess.kill()
            logger.info("DHCP Server stopped.")
        else:
            logger.info("Tried to stop DHCP Server, but it was already not running.")

    def restart(self) -> None:
        self.stop()
        self.start()

    def is_running(self) -> bool:
        return self._subprocess is not None and self._subprocess.poll() is None

    @property
    def interface(self) -> str:
        return self._interface

    def __del__(self) -> None:
        self.stop()
