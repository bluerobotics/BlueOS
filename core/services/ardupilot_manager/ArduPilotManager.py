import asyncio
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
    EndpointAlreadyExists,
    MavlinkRouterStartFail,
    NoPreferredBoardSet,
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
        self._current_board: Optional[FlightController] = None
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
                self.current_board is None
                or (self.current_board.type in [PlatformType.SITL, PlatformType.Linux] and process_not_running)
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
        if not self.start_board(BoardDetector.detect(include_sitl=False)):
            logger.warning("Flight controller board not detected.")

    @property
    def current_board(self) -> Optional[FlightController]:
        return self._current_board

    @property
    def current_sitl_frame(self) -> SITLFrame:
        return self._current_sitl_frame

    @current_sitl_frame.setter
    def current_sitl_frame(self, frame: SITLFrame) -> None:
        self._current_sitl_frame = frame
        logger.info(f"Setting {frame.value} as frame for SITL.")

    def start_navigator(self, board: FlightController) -> None:
        self._current_board = board
        if not self.firmware_manager.is_firmware_installed(self._current_board):
            if board.platform == Platform.Navigator:
                self.firmware_manager.install_firmware_from_file(
                    pathlib.Path("/root/blueos-files/ardupilot-manager/default/ardupilot_navigator"),
                    board,
                )

        firmware_path = self.firmware_manager.firmware_path(self._current_board.platform)
        self.firmware_manager.validate_firmware(firmware_path, self._current_board.platform)

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
            f"{firmware_path}"
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
            cwd=self.settings.firmware_folder,
        )

        self.start_mavlink_manager(master_endpoint)

    def start_serial(self, board: FlightController) -> None:
        if not board.path:
            raise ValueError(f"Could not find device path for board {board.name}.")
        self._current_board = board
        self.start_mavlink_manager(
            Endpoint("Master", self.settings.app_name, EndpointType.Serial, board.path, 115200, protected=True)
        )

    def run_with_sitl(self, frame: SITLFrame = SITLFrame.VECTORED) -> None:
        self._current_board = BoardDetector.detect_sitl()
        if not self.firmware_manager.is_firmware_installed(self._current_board):
            self.firmware_manager.install_firmware_from_params(Vehicle.Sub, self._current_board)
        if frame == SITLFrame.UNDEFINED:
            frame = SITLFrame.VECTORED
            logger.warning(f"SITL frame is undefined. Setting {frame} as current frame.")
        self.current_sitl_frame = frame

        firmware_path = self.firmware_manager.firmware_path(self._current_board.platform)
        self.firmware_manager.validate_firmware(firmware_path, self._current_board.platform)

        # ArduPilot SITL binary will bind TCP port 5760 (server) and the mavlink router will connect to it as a client
        master_endpoint = Endpoint(
            "Master", self.settings.app_name, EndpointType.TCPServer, "127.0.0.1", 5760, protected=True
        )
        # pylint: disable=consider-using-with
        self.ardupilot_subprocess = subprocess.Popen(
            [
                firmware_path,
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
            cwd=self.settings.firmware_folder,
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
                "MAVLink2Rest",
                self.settings.app_name,
                EndpointType.UDPClient,
                "127.0.0.1",
                14000,
                persistent=True,
                protected=True,
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
            Endpoint(
                "Ping360 Heading",
                self.settings.app_name,
                EndpointType.UDPServer,
                "0.0.0.0",
                14660,
                persistent=True,
                protected=True,
            ),
        ]
        for endpoint in default_endpoints:
            try:
                self.mavlink_manager.add_endpoint(endpoint)
            except EndpointAlreadyExists:
                pass
            except Exception as error:
                logger.warning(str(error))
        self.mavlink_manager.start(device)

    async def change_board(self, board: FlightController) -> None:
        logger.info(f"Trying to run with '{board.name}'.")
        if not board in BoardDetector.detect():
            raise ValueError(f"Cannot use '{board.name}'. Board not detected.")
        self.set_preferred_board(board)
        await self.kill_ardupilot()
        self._current_board = board
        await self.start_ardupilot()

    def set_preferred_board(self, board: FlightController) -> None:
        logger.info(f"Setting {board.name} as preferred flight-controller.")
        self.configuration["preferred_board"] = board.dict(exclude={"path"})
        self.settings.save(self.configuration)

    def get_preferred_board(self) -> FlightController:
        preferred_board = self.configuration.get("preferred_board")
        if not preferred_board:
            raise NoPreferredBoardSet("Preferred board not set yet.")
        return FlightController(**preferred_board)

    def get_board_to_be_used(self, boards: List[FlightController]) -> FlightController:
        """Check if preferred board exists and is connected. If so, use it, otherwise, choose by priority."""
        try:
            preferred_board = self.get_preferred_board()
            logger.debug(f"Preferred flight-controller is {preferred_board.name}.")
            for board in boards:
                # Compare connected boards with saved board, excluding path (which can change between sessions)
                if preferred_board.dict(exclude={"path"}).items() <= board.dict().items():
                    return board
            logger.debug(f"Flight-controller {preferred_board.name} not connected.")
        except NoPreferredBoardSet as error:
            logger.warning(error)

        boards.sort(key=lambda board: board.platform)
        preferred_board = boards[0]
        self.set_preferred_board(preferred_board)
        return preferred_board

    def start_board(self, boards: List[FlightController]) -> bool:
        if not boards:
            return False

        if len(boards) > 1:
            logger.warning(f"More than a single board detected: {boards}")

        flight_controller = self.get_board_to_be_used(boards)

        logger.info(f"Using {flight_controller.name} flight-controller.")

        if flight_controller.platform in [Platform.Navigator]:
            self.start_navigator(flight_controller)
            return True
        if flight_controller.platform.type == PlatformType.Serial:
            self.start_serial(flight_controller)
            return True
        raise RuntimeError("Invalid board type: {boards}")

    def running_ardupilot_processes(self) -> List[psutil.Process]:
        """Return list of all Ardupilot process running on system."""

        def is_ardupilot_process(process: psutil.Process) -> bool:
            """Checks if given process is using a Ardupilot's firmware file, for any known platform."""
            for platform in Platform:
                firmware_path = self.firmware_manager.firmware_path(platform)
                if str(firmware_path) in " ".join(process.cmdline()):
                    return True
            return False

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

        if not self.current_board or self.current_board.platform != Platform.SITL:
            try:
                logger.info("Disarming vehicle.")
                await self.vehicle_manager.disarm_vehicle()
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
            if self.current_board and self.current_board.platform == Platform.SITL:
                self.run_with_sitl(self.current_sitl_frame)
                return
            self.run_with_board()
        except MavlinkRouterStartFail as error:
            logger.warning(f"Failed to start Mavlink router. {error}")
        finally:
            self.should_be_running = True

    async def restart_ardupilot(self) -> None:
        if self.current_board is None or self.current_board.type in [PlatformType.SITL, PlatformType.Linux]:
            await self.kill_ardupilot()
            await self.start_ardupilot()
            return
        await self.vehicle_manager.reboot_vehicle()

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

    def _save_current_endpoints(self) -> None:
        try:
            persistent_endpoints = set(filter(lambda endpoint: endpoint.persistent, self.get_endpoints()))
            self._save_endpoints_to_configuration(persistent_endpoints)
            self.settings.save(self.configuration)
        except Exception as error:
            logger.error(f"Could not save endpoints. {error}")

    def get_endpoints(self) -> Set[Endpoint]:
        """Get all endpoints from the mavlink manager."""
        return self.mavlink_manager.endpoints()

    def add_new_endpoints(self, new_endpoints: Set[Endpoint]) -> None:
        """Add multiple endpoints to the mavlink manager and save them on the configuration file."""
        logger.info(f"Adding endpoints {[e.name for e in new_endpoints]} and updating settings file.")
        self.mavlink_manager.add_endpoints(new_endpoints)
        self._save_current_endpoints()
        self.mavlink_manager.restart()

    def remove_endpoints(self, endpoints_to_remove: Set[Endpoint]) -> None:
        """Remove multiple endpoints from the mavlink manager and save them on the configuration file."""
        logger.info(f"Removing endpoints {[e.name for e in endpoints_to_remove]} and updating settings file.")
        self.mavlink_manager.remove_endpoints(endpoints_to_remove)
        self._save_current_endpoints()
        self.mavlink_manager.restart()

    def update_endpoints(self, endpoints_to_update: Set[Endpoint]) -> None:
        """Update multiple endpoints from the mavlink manager and save them on the configuration file."""
        logger.info(f"Modifying endpoints {[e.name for e in endpoints_to_update]} and updating settings file.")
        self.mavlink_manager.update_endpoints(endpoints_to_update)
        self._save_current_endpoints()
        self.mavlink_manager.restart()

    def get_available_firmwares(self, vehicle: Vehicle, platform: Platform) -> List[Firmware]:
        return self.firmware_manager.get_available_firmwares(vehicle, platform)

    def install_firmware_from_file(self, firmware_path: pathlib.Path, board: FlightController) -> None:
        self.firmware_manager.install_firmware_from_file(firmware_path, board)

    def install_firmware_from_url(self, url: str, board: FlightController) -> None:
        self.firmware_manager.install_firmware_from_url(url, board)

    def restore_default_firmware(self, board: FlightController) -> None:
        self.firmware_manager.restore_default_firmware(board)
