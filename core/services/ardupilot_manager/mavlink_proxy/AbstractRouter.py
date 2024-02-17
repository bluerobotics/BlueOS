import abc
import asyncio
import pathlib
import shlex
import shutil
import tempfile
from typing import Any, List, Optional, Set, Type

from loguru import logger

from exceptions import (
    DuplicateEndpointName,
    EndpointAlreadyExists,
    EndpointDontExist,
    MavlinkRouterStartFail,
    NoMasterMavlinkEndpoint,
)
from mavlink_proxy.Endpoint import Endpoint


class AbstractRouter(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self._endpoints: Set[Endpoint] = set()
        self._master_endpoint: Optional[Endpoint] = None
        self._subprocess: Optional[asyncio.subprocess.Process] = None

        # Since this methods can fail we need to have the other variables defined
        # to avoid any problem in __del__
        self._binary = shutil.which(self.binary_name())
        self._logdir = pathlib.Path(tempfile.gettempdir())
        self._version = self._get_version()

    @staticmethod
    @abc.abstractmethod
    def name() -> str:
        pass

    @staticmethod
    @abc.abstractmethod
    def binary_name() -> str:
        pass

    @abc.abstractmethod
    def _get_version(self) -> Optional[str]:
        pass

    @staticmethod
    @abc.abstractmethod
    def is_ok() -> bool:
        pass

    @staticmethod
    @abc.abstractmethod
    def _validate_endpoint(endpoint: Endpoint) -> None:
        pass

    @abc.abstractmethod
    def assemble_command(self, master_endpoint: Endpoint) -> str:
        pass

    @staticmethod
    def possible_interfaces() -> List[str]:
        return [subclass.name() for subclass in AbstractRouter.__subclasses__()]

    @staticmethod
    def available_interfaces() -> List[Type["AbstractRouter"]]:
        logger.debug(f"Possible interfaces: {AbstractRouter.possible_interfaces()}")

        def caller(subclass: Type["AbstractRouter"]) -> bool:
            # It's necessary to call __str__ since it uses static methods
            # pylint: disable=unnecessary-dunder-call
            logger.debug(subclass.__str__(subclass))  # type: ignore
            return subclass.is_ok()

        availables = list(filter(caller, AbstractRouter.__subclasses__()))
        logger.debug(f"Available interfaces: {availables}")
        return availables

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

    @property
    def master_endpoint(self) -> Optional[Endpoint]:
        return self._master_endpoint

    async def start(self, master_endpoint: Endpoint) -> None:
        self._master_endpoint = master_endpoint
        command = self.assemble_command(self._master_endpoint)
        logger.debug(f"Calling router using following command: '{command}'.")

        self._subprocess = await asyncio.create_subprocess_exec(
            *shlex.split(command), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        await asyncio.sleep(3)  # Non-blocking sleep
        if not await self.is_running():
            _stdout, _strerr = await self._subprocess.communicate()
            stdout = _stdout.decode("utf-8") if _stdout else "No stdout."
            stderr = _strerr.decode("utf-8") if _strerr else "No stderr."
            output = f"message: stdout: '{stdout}', stderr: '{stderr}'"
            returncode = self._subprocess.returncode
            raise MavlinkRouterStartFail(f"Failed to initialize Mavlink router, code: {returncode}, {output}")
        await self.start_house_keepers()

    async def exit(self) -> None:
        if await self.is_running():
            if self._subprocess is not None:
                logger.warning("Terminating process")
                self._subprocess.terminate()
                logger.warning("Termination done")
                await asyncio.sleep(3)  # Non-blocking sleep
                logger.warning("Checking if it's still running..")
                if await self.is_running():
                    logger.warning("Still running, going to kill it")
                    self._subprocess.kill()
                    logger.warning("Killing done")
                    await asyncio.sleep(3)
                await self._subprocess.wait()  # Wait for the subprocess to terminate
        else:
            logger.debug("Tried to stop router, but it was already not running.")

    async def start_house_keepers(self) -> None:
        if self._subprocess is None:
            return
        # Ensure that the logging tasks are awaited and executed
        asyncio.create_task(self._log_stdout())
        asyncio.create_task(self._log_stderr())

    async def _log_stdout(self) -> None:
        while self._subprocess is not None:
            if self._subprocess.stdout:
                stdout_line = await self._subprocess.stdout.readline()
                if stdout_line:
                    logger.debug(f"Router: {stdout_line.decode().strip()}")
                else:
                    break  # EOF reached
            await asyncio.sleep(0.01)

    async def _log_stderr(self) -> None:
        while self._subprocess is not None:
            if self._subprocess.stderr:
                stderr_line = await self._subprocess.stderr.readline()
                if stderr_line:
                    logger.debug(f"Router: {stderr_line.decode().strip()}")
                else:
                    break  # EOF reached
            await asyncio.sleep(0.01)

    async def restart(self) -> None:
        if self._master_endpoint is None:
            raise NoMasterMavlinkEndpoint("Mavlink master endpoint was not set. Cannot restart router.")
        await self.exit()
        await self.start(self._master_endpoint)

    async def is_running(self) -> bool:
        if not self._subprocess:
            return False

        # The 'poll' method is not available in asyncio's subprocess,
        # so we use 'returncode' to check if the process has exited
        return self._subprocess.returncode is None

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

        for current_endpoint in self._endpoints:
            if endpoint == current_endpoint:
                raise EndpointAlreadyExists(f"Endpoint '{endpoint}' already exists.")
            if endpoint.name == current_endpoint.name:
                if endpoint.overwrite_settings:
                    self._endpoints.remove(current_endpoint)
                    break
                raise DuplicateEndpointName(f"Name '{endpoint.name}' already being used by an existing endpoint.")

        self._endpoints.add(endpoint)

    def remove_endpoint(self, endpoint: Endpoint) -> None:
        if endpoint not in self._endpoints:
            raise EndpointDontExist(f"Endpoint '{endpoint.name}' not found.")

        self._endpoints.remove(endpoint)

    def endpoints(self) -> Set[Endpoint]:
        return self._endpoints

    def clear_endpoints(self) -> None:
        """Remove all output endpoints."""
        self._endpoints = set()

    def __str__(self) -> str:
        return f"""
{self.__class__.__name__}:
    name: {self.name()}
    binary_name: {self.binary_name()}
    is_ok: {self.is_ok()}
"""
