import abc
import pathlib
import shlex
import shutil
import subprocess
import tempfile
from typing import Any, List, Optional, Type

from mavlink_proxy.Endpoint import Endpoint


class AbstractRouter(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self._endpoints: List[Endpoint] = []
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
    def _validate_endpoint(endpoint: Endpoint) -> bool:
        pass

    @abc.abstractclassmethod
    def assemble_command(cls, master: Endpoint) -> str:
        pass

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

    def start(self, vehicle_endpoint: Optional[Endpoint] = None, _verbose: bool = False) -> bool:
        if vehicle_endpoint is not None:
            self._master_endpoint = vehicle_endpoint
        command = self.assemble_command(self._master_endpoint)
        self._subprocess = subprocess.Popen(shlex.split(command), shell=False, encoding="utf-8", errors="ignore")
        return True

    def exit(self) -> bool:
        if self.is_running():
            assert self._subprocess is not None
            self._subprocess.kill()
        return True

    def restart(self) -> bool:
        return self.exit() and self.start()

    def is_running(self) -> bool:
        return self._subprocess is not None and self._subprocess.poll() is None

    def process(self) -> Any:
        assert self._subprocess is not None
        return self._subprocess

    def logdir(self) -> pathlib.Path:
        return self._logdir

    def set_logdir(self, directory: pathlib.Path) -> bool:
        if directory.exists():
            self._logdir = directory
            return True
        return False

    def add_endpoint(self, endpoint: Endpoint) -> bool:
        if not self._validate_endpoint(endpoint):
            raise NotImplementedError

        if endpoint in self._endpoints:
            return False

        self._endpoints.append(endpoint)
        return True

    def remove_endpoint(self, endpoint: Endpoint) -> bool:
        if endpoint in self._endpoints:
            self._endpoints.remove(endpoint)
            return True
        return False

    def endpoints(self) -> List[Endpoint]:
        return self._endpoints

    def __del__(self) -> None:
        self.exit()
