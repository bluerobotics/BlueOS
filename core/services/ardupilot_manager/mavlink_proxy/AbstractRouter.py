import abc
import pathlib
import shlex
import shutil
import subprocess
import tempfile
from typing import Any, List, Optional, Set, Type

from loguru import logger

from mavlink_proxy.Endpoint import Endpoint


class AbstractRouter(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self._endpoints: Set[Endpoint] = set()
        self._subprocess: Optional[Any] = None

        # Since this methods can fail we need to have the other variables defined
        # to avoid any problem in __del__
        self._binary = shutil.which(self.binary_name())
        self._logdir = pathlib.Path(tempfile.gettempdir())
        self._version = self._get_version()

    @staticmethod
    @abc.abstractclassmethod
    def name() -> str:
        pass

    @staticmethod
    @abc.abstractclassmethod
    def binary_name() -> str:
        pass

    @abc.abstractclassmethod
    def _get_version(cls) -> Optional[str]:
        pass

    @staticmethod
    @abc.abstractclassmethod
    def is_ok() -> bool:
        pass

    @staticmethod
    @abc.abstractclassmethod
    def _validate_endpoint(endpoint: Endpoint) -> None:
        pass

    @abc.abstractclassmethod
    def assemble_command(cls, master: Endpoint) -> str:
        pass

    @staticmethod
    def possible_interfaces() -> List[str]:
        return [subclass.name() for subclass in AbstractRouter.__subclasses__()]

    @staticmethod
    def available_interfaces() -> List[Type["AbstractRouter"]]:
        return [subclass for subclass in AbstractRouter.__subclasses__() if subclass.is_ok()]

    @staticmethod
    def get_interface(name: str) -> Type["AbstractRouter"]:
        for interface in AbstractRouter.__subclasses__():
            if interface.is_ok() and interface.name() == name:
                return interface
        raise RuntimeError("Interface is not ok or does not exist.")

    def binary(self) -> Optional[str]:
        return self._binary

    def version(self) -> Optional[str]:
        return self._version

    def start(self, vehicle_endpoint: Optional[Endpoint] = None, _verbose: bool = False) -> None:
        if vehicle_endpoint is not None:
            self._master_endpoint = vehicle_endpoint
        command = self.assemble_command(self._master_endpoint)
        # pylint: disable=consider-using-with
        self._subprocess = subprocess.Popen(shlex.split(command), shell=False, encoding="utf-8", errors="ignore")

    def exit(self) -> None:
        if self.is_running():
            assert self._subprocess is not None
            self._subprocess.kill()
        else:
            logger.info("Tried to stop router, but it was already not running.")

    def restart(self) -> None:
        self.exit()
        self.start()

    def is_running(self) -> bool:
        return self._subprocess is not None and self._subprocess.poll() is None

    def process(self) -> Any:
        assert self._subprocess is not None
        return self._subprocess

    def logdir(self) -> pathlib.Path:
        return self._logdir

    def set_logdir(self, directory: pathlib.Path) -> None:
        if not directory.exists():
            raise ValueError(f"Logging directory {directory} does not exist.")
        self._logdir = directory

    def add_endpoint(self, endpoint: Endpoint) -> None:
        self._validate_endpoint(endpoint)

        if endpoint in self._endpoints:
            raise ValueError("Endpoint already exists.")

        if endpoint.name in [endpoint.name for endpoint in self._endpoints]:
            raise ValueError("Name already being used by an existing endpoint.")

        self._endpoints.add(endpoint)

    def remove_endpoint(self, endpoint: Endpoint) -> None:
        if endpoint not in self._endpoints:
            raise ValueError("Endpoint not found.")

        self._endpoints.remove(endpoint)

    def endpoints(self) -> Set[Endpoint]:
        return self._endpoints

    def clear_endpoints(self) -> None:
        """Remove all output endpoints."""
        self._endpoints = set()

    def __del__(self) -> None:
        self.exit()
