import asyncio
import os
import pathlib
import subprocess
from copy import deepcopy
from typing import Any, List, Optional, Set

import psutil
from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from commonwealth.utils.Singleton import Singleton
from loguru import logger

from exceptions import (
    ArdupilotProcessKillFail,
    EndpointCreationFail,
    EndpointDeleteFail,
    EndpointUpdateFail,
    MavlinkRouterStartFail,
)
from firmware.FirmwareManagement import FirmwareManager
from flight_controller_detector.Detector import Detector as BoardDetector
from mavlink_proxy.Endpoint import Endpoint
from mavlink_proxy.Manager import Manager as MavlinkManager
from settings import Settings
from typedefs import (
    EndpointType,
    Firmware,
    FlightController,
    Platform,
    PlatformType,
    SITLFrame,
    Vehicle,
)


class ArduPilotManager(metaclass=Singleton):
    # pylint: disable=too-many-instance-attributes
    def __init__(self) -> None:
        self.settings = Settings()
        self.settings.create_app_folders()
        self.mavlink_manager = MavlinkManager()
        self.mavlink_manager.set_logdir(self.settings.log_path)
        self._current_platform: Platform = Platform.Undefined
        self._current_sitl_frame: SITLFrame = SITLFrame.UNDEFINED

        # Load settings and do the initial configuration
        if self.settings.load():
            logger.info(f"Loaded settings from {self.settings.settings_file}.")
            logger.debug(self.settings.content)
        else:
            self.settings.create_settings_file()

        self.configuration = deepcopy(self.settings.content)
        self._load_endpoints()
        self.ardupilot_subprocess: Optional[Any] = None
        self.firmware_manager = FirmwareManager(self.settings.firmware_folder, self.settings.defaults_folder)
        self.vehicle_manager = VehicleManager()

        self.should_be_running = False

    async def auto_restart_ardupilot(self) -> None:
        """Auto-restart Ardupilot when it's not running but was supposed to."""
        while True:
            process_not_running = (
                self.ardupilot_subprocess is not None and self.ardupilot_subprocess.poll() is not None
            ) or len(self.running_ardupilot_processes()) == 0
            needs_restart = self.should_be_running and (
                (self.current_platform.type in [PlatformType.SITL, PlatformType.Linux] and process_not_running)
                or self.current_platform == Platform.Undefined
            )
            if needs_restart:
                logger.debug("Restarting ardupilot...")
                try:
                    await self.kill_ardupilot()
                except Exception as error:
                    logger.warning(f"Could not kill Ardupilot: {error}")
                try:
                    await self.start_ardupilot()
                except Exception as error:
                    logger.warning(f"Could not start Ardupilot: {error}")
                self.should_be_running = True
            await asyncio.sleep(5.0)

    async def start_mavlink_manager_watchdog(self) -> None:
        await self.mavlink_manager.auto_restart_router()

    def run_with_board(self) -> None:
        if not self.start_board(BoardDetector.detect()):
            logger.warning("Flight controller board not detected.")

    @staticmethod
    def check_running_as_root() -> None:
        if os.geteuid() != 0:
            raise RuntimeError("ArduPilot manager needs to run with root privilege.")

    @property
    def current_platform(self) -> Platform:
        return self._current_platform

    @current_platform.setter
    def current_platform(self, platform: Platform) -> None:
        self._current_platform = platform
        logger.info(f"Setting {platform} as current platform.")

    @property
    def current_sitl_frame(self) -> SITLFrame:
        return self._current_sitl_frame

    @current_sitl_frame.setter
    def current_sitl_frame(self, frame: SITLFrame) -> None:
        self._current_sitl_frame = frame
        logger.info(f"Setting {frame.value} as frame for SITL.")

    def current_firmware_path(self) -> pathlib.Path:
        return self.firmware_manager.firmware_path(self.current_platform)

    def start_navigator(self, board: FlightController) -> None:
        self.current_platform = board.platform
        if not self.firmware_manager.is_firmware_installed(self.current_platform):
            if board.platform == Platform.NavigatorR3:
                self.firmware_manager.install_firmware_from_params(Vehicle.Sub, self.current_platform)
            else:
                self.install_firmware_from_file(
                    pathlib.Path("/root/companion-files/ardupilot-manager/default/ardupilot_navigator_r4")
                )

        self.firmware_manager.validate_firmware(self.current_firmware_path(), self.current_platform)

        # ArduPilot process will connect as a client on the UDP server created by the mavlink router
        master_endpoint = Endpoint(
            "Master", self.settings.app_name, EndpointType.UDPServer, "127.0.0.1", 8852, protected=True
        )

        # Run ardupilot inside while loop to avoid exiting after reboot command
        ## Can be changed back to a simple command after https://github.com/ArduPilot/ardupilot/issues/17572
        ## gets fixed.
        # pylint: disable=consider-using-with
        #
        # The mapping of serial ports works as in the following table:
        #
        # |    ArduSub   |       Navigator         |
        # | -C = Serial1 | Serial1 => /dev/ttyS0   |
        # | -B = Serial3 | Serial3 => /dev/ttyAMA1 |
        # | -E = Serial4 | Serial4 => /dev/ttyAMA2 |
        # | -F = Serial5 | Serial5 => /dev/ttyAMA3 |
        #
        # The first column comes from https://ardupilot.org/dev/docs/sitl-serial-mapping.html

        self.ardupilot_subprocess = subprocess.Popen(
            f"{self.current_firmware_path()}"
            f" -A udp:{master_endpoint.place}:{master_endpoint.argument}"
            f" --log-directory {self.settings.firmware_folder}/logs/"
            f" --storage-directory {self.settings.firmware_folder}/storage/"
            f" -C /dev/ttyS0"
            f" -B /dev/ttyAMA1"
            f" -E /dev/ttyAMA2"
            f" -F /dev/ttyAMA3",
            shell=True,
            encoding="utf-8",
            errors="ignore",
        )

        self.start_mavlink_manager(master_endpoint)

    def start_serial(self, board: FlightController) -> None:
        if not board.path:
            raise ValueError(f"Could not find device path for board {board.name}.")
        self.current_platform = board.platform
        self.start_mavlink_manager(
            Endpoint("Master", self.settings.app_name, EndpointType.Serial, board.path, 115200, protected=True)
        )

    def run_with_sitl(self, frame: SITLFrame = SITLFrame.VECTORED) -> None:
        self.current_platform = Platform.SITL
        if not self.firmware_manager.is_firmware_installed(self.current_platform):
            self.firmware_manager.install_firmware_from_params(Vehicle.Sub, self.current_platform)
        if frame == SITLFrame.UNDEFINED:
            frame = SITLFrame.VECTORED
            logger.warning(f"SITL frame is undefined. Setting {frame} as current frame.")
        self.current_sitl_frame = frame

        self.firmware_manager.validate_firmware(self.current_firmware_path(), self.current_platform)

        # ArduPilot SITL binary will bind TCP port 5760 (server) and the mavlink router will connect to it as a client
        master_endpoint = Endpoint(
            "Master", self.settings.app_name, EndpointType.TCPServer, "127.0.0.1", 5760, protected=True
        )
        # pylint: disable=consider-using-with
        self.ardupilot_subprocess = subprocess.Popen(
            [
                self.current_firmware_path(),
                "--model",
                self.current_sitl_frame.value,
                "--base-port",
                str(master_endpoint.argument),
                "--home",
                "-27.563,-48.459,0.0,270.0",
            ],
            shell=False,
            encoding="utf-8",
            errors="ignore",
        )

        self.start_mavlink_manager(master_endpoint)

    def start_mavlink_manager(self, device: Endpoint) -> None:
        default_endpoints = [
            Endpoint(
                "GCS Server Link",
                self.settings.app_name,
                EndpointType.UDPServer,
                "0.0.0.0",
                14550,
                persistent=True,
                enabled=False,
            ),
            Endpoint(
                "GCS Client Link",
                self.settings.app_name,
                EndpointType.UDPClient,
                "192.168.2.1",
                14550,
                persistent=True,
                enabled=True,
            ),
            Endpoint(
                "Internal Link",
                self.settings.app_name,
                EndpointType.UDPServer,
                "127.0.0.1",
                14001,
                persistent=True,
                protected=True,
            ),
        ]
        for endpoint in default_endpoints:
            try:
                self.add_new_endpoints({endpoint})
            except Exception as error:
                logger.warning(str(error))
        self.mavlink_manager.set_master_endpoint(device)
        self.mavlink_manager.start()

    def start_board(self, boards: List[FlightController]) -> bool:
        if not boards:
            return False

        if len(boards) > 1:
            logger.warning(f"More than a single board detected: {boards}")

        # Sort by priority
        boards.sort(key=lambda flight_controller: flight_controller.platform)

        flight_controller = boards[0]
        logger.info(f"Board in use: {flight_controller}.")

        if flight_controller.platform in [Platform.NavigatorR3, Platform.NavigatorR5]:
            self.start_navigator(flight_controller)
            return True
        if flight_controller.platform.type == PlatformType.Serial:
            self.start_serial(flight_controller)
            return True
        raise RuntimeError("Invalid board type: {boards}")

    def running_ardupilot_processes(self) -> List[psutil.Process]:
        """Return list of all Ardupilot process running on system."""

        def is_ardupilot_process(process: psutil.Process) -> bool:
            """Checks if given process is using Ardupilot's firmware file for current platform."""
            return str(self.current_firmware_path()) in " ".join(process.cmdline())

        return list(filter(is_ardupilot_process, psutil.process_iter()))

    async def terminate_ardupilot_subprocess(self) -> None:
        """Terminate Ardupilot subprocess."""
        if self.ardupilot_subprocess:
            self.ardupilot_subprocess.terminate()
            for _ in range(10):
                if self.ardupilot_subprocess.poll() is not None:
                    logger.info("Ardupilot subprocess terminated.")
                    return
                logger.debug("Waiting for process to die...")
                await asyncio.sleep(0.5)
            raise ArdupilotProcessKillFail("Could not terminate Ardupilot subprocess.")
        logger.warning("Ardupilot subprocess already not running.")

    async def prune_ardupilot_processes(self) -> None:
        """Kill all system processes using Ardupilot's firmware file."""
        for process in self.running_ardupilot_processes():
            try:
                logger.debug(f"Killing Ardupilot process {process.name()}::{process.pid}.")
                process.kill()
                await asyncio.sleep(0.5)
            except Exception as error:
                raise ArdupilotProcessKillFail(f"Could not kill {process.name()}::{process.pid}.") from error

    async def kill_ardupilot(self) -> None:
        self.should_be_running = False

        if self.current_platform != Platform.SITL:
            try:
                logger.info("Disarming vehicle.")
                self.vehicle_manager.disarm_vehicle()
                logger.info("Vehicle disarmed.")
            except Exception as error:
                logger.warning(f"Could not disarm vehicle: {error}. Proceeding with kill.")

        # TODO: Add shutdown command on HAL_SITL and HAL_LINUX, changing terminate/prune
        # logic with a simple "self.vehicle_manager.shutdown_vehicle()"
        logger.info("Terminating Ardupilot subprocess.")
        await self.terminate_ardupilot_subprocess()
        logger.info("Ardupilot subprocess terminated.")
        logger.info("Pruning Ardupilot's system processes.")
        await self.prune_ardupilot_processes()
        logger.info("Ardupilot's system processes pruned.")

        logger.info("Stopping Mavlink manager.")
        self.mavlink_manager.stop()
        logger.info("Mavlink manager stopped.")

    async def start_ardupilot(self) -> None:
        try:
            if self.current_platform == Platform.SITL:
                self.run_with_sitl(self.current_sitl_frame)
                return
            self.run_with_board()
        except MavlinkRouterStartFail as error:
            logger.warning(f"Failed to start Mavlink router. {error}")
        finally:
            self.should_be_running = True

    async def restart_ardupilot(self) -> None:
        if self.current_platform.type in [PlatformType.SITL, PlatformType.Linux]:
            await self.kill_ardupilot()
            await self.start_ardupilot()
            return
        self.vehicle_manager.reboot_vehicle()

    def _get_configuration_endpoints(self) -> Set[Endpoint]:
        return {Endpoint(**endpoint) for endpoint in self.configuration.get("endpoints") or []}

    def _save_endpoints_to_configuration(self, endpoints: Set[Endpoint]) -> None:
        self.configuration["endpoints"] = list(map(Endpoint.as_dict, endpoints))

    def _load_endpoints(self) -> None:
        """Load endpoints from the configuration file to the mavlink manager."""
        for endpoint in self._get_configuration_endpoints():
            try:
                self.mavlink_manager.add_endpoint(endpoint)
            except Exception as error:
                logger.error(f"Could not load endpoint {endpoint}: {error}")

    def reload_endpoints(self) -> None:
        try:
            persistent_endpoints = set(filter(lambda endpoint: endpoint.persistent, self.get_endpoints()))
            self._save_endpoints_to_configuration(persistent_endpoints)
            self.settings.save(self.configuration)
            self.mavlink_manager.restart()
        except Exception as error:
            logger.error(f"Error updating endpoints: {error}")

    def get_endpoints(self) -> Set[Endpoint]:
        """Get all endpoints from the mavlink manager."""
        return self.mavlink_manager.endpoints()

    def add_new_endpoints(self, new_endpoints: Set[Endpoint]) -> None:
        """Add multiple endpoints to the mavlink manager and save them on the configuration file."""
        for endpoint in new_endpoints:
            try:
                self.mavlink_manager.add_endpoint(endpoint)
                logger.info(f"Adding endpoint '{endpoint.name}' and saving it to the settings file.")
            except Exception as error:
                self.mavlink_manager.reset_endpoints()
                raise EndpointCreationFail(f"Failed to add endpoint '{endpoint.name}': {error}") from error

    def remove_endpoints(self, endpoints_to_remove: Set[Endpoint]) -> None:
        """Remove multiple endpoints from the mavlink manager and save them on the configuration file."""
        protected_endpoints = set(filter(lambda endpoint: endpoint.protected, endpoints_to_remove))
        if protected_endpoints:
            raise ValueError(f"Endpoints {[e.name for e in protected_endpoints]} are protected. Aborting operation.")

        for endpoint in endpoints_to_remove:
            try:
                self.mavlink_manager.remove_endpoint(endpoint)
                logger.info(f"Deleting endpoint '{endpoint.name}' and removing it from the settings file.")
            except Exception as error:
                self.mavlink_manager.reset_endpoints()
                raise EndpointDeleteFail(f"Failed to remove endpoint '{endpoint.name}': {error}") from error

    def update_endpoints(self, endpoints_to_update: Set[Endpoint]) -> None:
        """Update multiple endpoints from the mavlink manager and save them on the configuration file."""
        loaded_endpoints = self.get_endpoints()

        protected_endpoints = set(filter(lambda endpoint: endpoint.protected, endpoints_to_update))
        if protected_endpoints:
            raise ValueError(f"Endpoints {[e.name for e in protected_endpoints]} are protected. Aborting operation.")

        for updated_endpoint in endpoints_to_update:
            old_endpoint = next((e for e in loaded_endpoints if e.name == updated_endpoint.name), None)
            try:
                if not old_endpoint:
                    raise ValueError(f"Endpoint '{updated_endpoint.name}' does not exist.")
                logger.info(f"Updating endpoint '{updated_endpoint.name}'.")
                self.mavlink_manager.remove_endpoint(old_endpoint)
                self.mavlink_manager.add_endpoint(updated_endpoint)
            except Exception as error:
                self.mavlink_manager.reset_endpoints()
                raise EndpointUpdateFail(f"Failed to update endpoint '{updated_endpoint.name}': {error}") from error

    def get_available_firmwares(self, vehicle: Vehicle) -> List[Firmware]:
        return self.firmware_manager.get_available_firmwares(vehicle, self.current_platform)

    def install_firmware_from_file(self, firmware_path: pathlib.Path) -> None:
        self.firmware_manager.install_firmware_from_file(firmware_path, self.current_platform)

    def install_firmware_from_url(self, url: str) -> None:
        self.firmware_manager.install_firmware_from_url(url, self.current_platform)

    def restore_default_firmware(self) -> None:
        self.firmware_manager.restore_default_firmware(self.current_platform)
