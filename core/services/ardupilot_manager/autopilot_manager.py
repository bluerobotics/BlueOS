import asyncio
import os
import pathlib
import subprocess
import time
from copy import deepcopy
from typing import Any, List, Optional, Set

import psutil
from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from commonwealth.utils.Singleton import Singleton
from elftools.elf.elffile import ELFFile
from exceptions import (
    AutoPilotProcessKillFail,
    NoDefaultFirmwareAvailable,
    NoPreferredBoardSet,
)
from firmware.FirmwareManagement import FirmwareManager
from flight_controller_detector.Detector import Detector as BoardDetector
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from loguru import logger
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.exceptions import EndpointAlreadyExists
from mavlink_proxy.Manager import Manager as MavlinkManager
from settings import Settings
from typedefs import (
    Firmware,
    FlightController,
    FlightControllerFlags,
    Parameters,
    Platform,
    PlatformType,
    Serial,
    SITLFrame,
    Vehicle,
)


class AutoPilotManager(metaclass=Singleton):
    # pylint: disable=too-many-instance-attributes
    def __init__(self) -> None:
        self.settings = Settings()
        self.settings.create_app_folders()
        self._current_board: Optional[FlightController] = None
        self.should_be_running = False
        self.mavlink_manager = MavlinkManager()

        # Load settings and do the initial configuration
        if self.settings.load():
            logger.info(f"Loaded settings from {self.settings.settings_file}.")
            logger.debug(self.settings.content)
        else:
            self.settings.create_settings_file()

        self.autopilot_default_endpoints = [
            Endpoint(
                name="GCS Server Link",
                owner=self.settings.app_name,
                connection_type=EndpointType.UDPServer,
                place="0.0.0.0",
                argument=14550,
                persistent=True,
                enabled=True,
            ),
            Endpoint(
                name="GCS Client Link",
                owner=self.settings.app_name,
                connection_type=EndpointType.UDPClient,
                place="192.168.2.1",
                argument=14550,
                persistent=True,
                enabled=True,
            ),
            Endpoint(
                name="MAVLink2RestServer",
                owner=self.settings.app_name,
                connection_type=EndpointType.UDPServer,
                place="127.0.0.1",
                argument=14001,
                persistent=True,
                protected=True,
            ),
            Endpoint(
                name="MAVLink2Rest",
                owner=self.settings.app_name,
                connection_type=EndpointType.UDPClient,
                place="127.0.0.1",
                argument=14000,
                persistent=True,
                protected=True,
                overwrite_settings=True,
            ),
            Endpoint(
                name="Zenoh Deamon",
                owner=self.settings.app_name,
                connection_type=EndpointType.Zenoh,
                place="0.0.0.0",
                argument=7117,
                persistent=True,
                protected=True,
            ),
            Endpoint(
                name="Internal Link",
                owner=self.settings.app_name,
                connection_type=EndpointType.TCPServer,
                place="127.0.0.1",
                argument=5777,
                persistent=True,
                protected=True,
                overwrite_settings=True,
            ),
            Endpoint(
                name="Ping360 Heading",
                owner=self.settings.app_name,
                connection_type=EndpointType.UDPServer,
                place="0.0.0.0",
                argument=14660,
                persistent=True,
                protected=False,
            ),
        ]

    async def setup(self) -> None:
        # This is the logical continuation of __init__(), extracted due to its async nature
        self.configuration = deepcopy(self.settings.content)

        # Undesired state, only to avoid losing the reference to a running MavlinkManager
        if self.mavlink_manager is not None:
            await self.mavlink_manager.stop()

        self.mavlink_manager = MavlinkManager()
        preferred_router = self.load_preferred_router()
        try:
            self.mavlink_manager = MavlinkManager(preferred_router)
        except ValueError as error:
            logger.warning(
                f"Failed to start MavlinkManager[{preferred_router}]. Falling back to the first available router. Error details: {error}"
            )
            preferred_router = None

        if not preferred_router:
            await self.set_preferred_router(self.mavlink_manager.tool.name())
            logger.info(f"Setting {self.mavlink_manager.tool.name()} as preferred router.")
        self.mavlink_manager.set_logdir(self.settings.log_path)

        self._load_endpoints()
        self.ardupilot_subprocess: Optional[Any] = None
        self.firmware_manager = FirmwareManager(
            self.settings.firmware_folder, self.settings.defaults_folder, self.settings.user_firmware_folder
        )
        self.vehicle_manager = VehicleManager()
        self._heartbeat_fail_count = 0  # Consecutive heartbeat failures
        self._max_heartbeat_failures = 10  # Threshold for restarting Ardupilot after consecutive heartbeat failures

        self.should_be_running = False
        self.remove_old_logs()
        self.current_sitl_frame = self.load_sitl_frame()

    def remove_old_logs(self) -> None:
        def need_to_remove_file(file: pathlib.Path) -> bool:
            now = time.time()
            week_old = now - 7 * 24 * 60 * 60
            return file.stat().st_size == 0 and file.stat().st_mtime < week_old

        try:
            firmware_log_files = list((self.settings.firmware_folder / "logs").iterdir())
            router_log_files = list(self.settings.log_path.iterdir())

            # Get all files with zero bytes and more than 7 days older
            files = [file for file in firmware_log_files + router_log_files if need_to_remove_file(file)]
            for file in files:
                logger.debug(f"Removing invalid log file: {file}")
                os.remove(file)
        except Exception as error:
            logger.warning(f"Failed to remove logs: {error}")

    def is_running(self) -> bool:
        if self.current_board is None:
            return False

        if self.current_board.type in [PlatformType.SITL, PlatformType.Linux]:
            return (
                self.ardupilot_subprocess is not None
                and self.ardupilot_subprocess.poll() is None
                and len(self.running_ardupilot_processes()) != 0
            )

        # Serial or others that are not processes based
        return self.should_be_running

    async def auto_restart_ardupilot(self) -> None:
        """Auto-restart Ardupilot when it's not running but was supposed to."""
        while True:
            needs_restart = self.should_be_running and not self.is_running()
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

            # Monitor MAVLink heartbeat while autopilot is supposed to be running
            if self.should_be_running and self.is_running():
                try:
                    alive = await self.vehicle_manager.is_heart_beating()
                    if alive:
                        self._heartbeat_fail_count = 0
                    else:
                        self._heartbeat_fail_count += 1
                        logger.warning(
                            f"Heartbeat check False ({self._heartbeat_fail_count}/{self._max_heartbeat_failures})"
                        )
                except Exception as error:
                    self._heartbeat_fail_count += 1
                    logger.warning(
                        f"heartbeat check failed ({self._heartbeat_fail_count}/{self._max_heartbeat_failures}): {error}"
                    )

                if self._heartbeat_fail_count >= self._max_heartbeat_failures:
                    logger.warning("Consecutive heartbeat failures threshold reached — restarting Ardupilot.")
                    try:
                        await self.restart_ardupilot()
                    except Exception as error:
                        logger.warning(f"Failed to restart Ardupilot after heartbeat failures: {error}")
                    self._heartbeat_fail_count = 0

            await asyncio.sleep(5.0)

    async def start_mavlink_manager_watchdog(self) -> None:
        await self.mavlink_manager.auto_restart_router()

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

    @staticmethod
    def firmware_has_debug_symbols(firmware_path: pathlib.Path) -> bool:
        with open(firmware_path, "rb") as f:
            elffile = ELFFile(f)

            for section in elffile.iter_sections():
                if section.name.startswith(".debug_line"):
                    # 100k is Empirical data. non-debug binaries seem to have around 700 entries here,
                    # while debug ones have 28 million entries
                    if section.header.sh_size > 100000:
                        return True
                    return False
        return False

    def update_serials(self, serials: List[Serial]) -> None:
        self.configuration["serials"] = [vars(serial) for serial in serials]
        self.settings.save(self.configuration)

    def get_serials(self) -> List[Serial]:
        # The mapping of serial ports works as in the following table:
        #
        # |    ArduSub   |       Navigator         |
        # | -C = Serial1 | Serial1 => /dev/ttyS0   |
        # | -B = Serial3 | Serial3 => /dev/ttyAMA1 |
        # | -E = Serial4 | Serial4 => /dev/ttyAMA2 |
        # | -F = Serial5 | Serial5 => /dev/ttyAMA3 |
        #
        # The first column comes from https://ardupilot.org/dev/docs/sitl-serial-mapping.html

        if "serials" not in self.configuration:
            assert isinstance(self._current_board, LinuxFlightController)
            return self._current_board.get_serials()
        serials = []
        for entry in self.configuration["serials"]:
            try:
                serials.append(Serial(port=entry["port"], endpoint=entry["endpoint"]))
            except Exception as e:
                logger.error(f"Entry is invalid! {entry['port']}:{entry['endpoint']}")
                logger.error(e)
        return serials

    def get_serial_cmdline(self, supports_new_serial_mapping: bool) -> str:
        if supports_new_serial_mapping:
            return " ".join([f"--serial{entry.port} {entry.endpoint}" for entry in self.get_serials()])
        return " ".join([f"-{entry.port_as_letter} {entry.endpoint}" for entry in self.get_serials()])

    def get_default_params_cmdline(self, platform: Platform) -> str:
        # check if file exists and return it's path as --defaults parameter
        default_params_path = self.firmware_manager.default_user_params_path(platform)
        if default_params_path.is_file():
            return f"--defaults {default_params_path}"
        return ""

    def check_supports_new_serial_mapping(self, firmware: pathlib.Path) -> bool:
        """
        check if the firmware supports --serialN instead of --uartX by checking the output of --help
        """
        try:
            output = subprocess.check_output([firmware, "--help"], encoding="utf-8")
            return "--serial" in output
        except Exception as e:
            logger.warning(f"Failed to check if firmware supports new serial mapping: {e}")
            return False

    async def start_linux_board(self, board: LinuxFlightController) -> None:
        self._current_board = board
        if not self.firmware_manager.is_firmware_installed(self._current_board):
            if board.platform == Platform.Navigator:
                await self.firmware_manager.install_firmware_from_file(
                    pathlib.Path("/root/blueos-files/ardupilot-manager/default/ardupilot_navigator"),
                    board,
                )
            elif board.platform == Platform.Navigator64:
                await self.firmware_manager.install_firmware_from_file(
                    pathlib.Path("/root/blueos-files/ardupilot-manager/default/ardupilot_navigator64"),
                    board,
                )
            else:
                raise NoDefaultFirmwareAvailable(
                    f"No firmware installed for '{board.platform}' and no default firmware available. Please install the firmware manually."
                )

        firmware_path = self.firmware_manager.firmware_path(self._current_board.platform)
        self.firmware_manager.validate_firmware(firmware_path, self._current_board.platform)

        # ArduPilot process will connect as a client on the UDP server created by the mavlink router
        master_endpoint = Endpoint(
            name="Master",
            owner=self.settings.app_name,
            connection_type=EndpointType.UDPServer,
            place="127.0.0.1",
            argument=8852,
            protected=True,
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

        supports_new_serial_mapping = self.check_supports_new_serial_mapping(firmware_path)

        master_endpoint_str = (
            f" --serial0 udp:{master_endpoint.place}:{master_endpoint.argument}"
            if supports_new_serial_mapping
            else f" -A udp:{master_endpoint.place}:{master_endpoint.argument}"
        )

        command_line = (
            f"{firmware_path}"
            f"{master_endpoint_str}"
            f" --log-directory {self.settings.firmware_folder}/logs/"
            f" --storage-directory {self.settings.firmware_folder}/storage/"
            f" {self.get_serial_cmdline(supports_new_serial_mapping)}"
            f" {self.get_default_params_cmdline(board.platform)}"
        )

        if self.firmware_has_debug_symbols(firmware_path):
            logger.info("Debug symbols found, launching with gdb server...")
            command_line = f"gdbserver 0.0.0.0:5555 {command_line}"

        logger.info(f"Using command line: '{command_line}'")
        self.ardupilot_subprocess = subprocess.Popen(
            command_line,
            shell=True,
            encoding="utf-8",
            errors="ignore",
            cwd=self.settings.firmware_folder,
        )

        await self.start_mavlink_manager(master_endpoint)

    async def start_serial(self, board: FlightController) -> None:
        if not board.path:
            raise ValueError(f"Could not find device path for board {board.name}.")
        self._current_board = board
        baudrate = 115200
        is_px4 = "px4" in board.name.lower()
        if is_px4:
            baudrate = 57600
        await self.start_mavlink_manager(
            Endpoint(
                name="Master",
                owner=self.settings.app_name,
                connection_type=EndpointType.Serial,
                place=board.path,
                argument=baudrate,
                protected=True,
            )
        )
        if is_px4:
            # PX4 needs at least one initial heartbeat to start sending data
            await self.vehicle_manager.burst_heartbeat()

    def set_sitl_frame(self, frame: SITLFrame) -> None:
        self.current_sitl_frame = frame
        self.configuration["sitl_frame"] = frame
        self.settings.save(self.configuration)

    def load_sitl_frame(self) -> SITLFrame:
        if self.configuration.get("sitl_frame", SITLFrame.UNDEFINED) != SITLFrame.UNDEFINED:
            return SITLFrame(self.configuration["sitl_frame"])
        frame = SITLFrame.VECTORED
        logger.warning(f"SITL frame is undefined. Setting {frame} as current frame.")
        self.set_sitl_frame(frame)
        return frame

    async def set_preferred_router(self, router: str) -> None:
        self.settings.preferred_router = router
        self.configuration["preferred_router"] = router
        self.settings.save(self.configuration)
        await self.mavlink_manager.set_preferred_router(router, self.autopilot_default_endpoints)

    def load_preferred_router(self) -> Optional[str]:
        try:
            return self.configuration["preferred_router"]  # type: ignore
        except KeyError:
            return None

    def get_available_routers(self) -> List[str]:
        return [router.name() for router in self.mavlink_manager.available_interfaces()]

    async def start_manual_board(self, board: FlightController) -> None:
        self._current_board = board
        self.master_endpoint = self.get_manual_board_master_endpoint()
        self.ardupilot_subprocess = None
        await self.start_mavlink_manager(self.master_endpoint)

    async def start_sitl(self) -> None:
        self._current_board = BoardDetector.detect_sitl()
        if not self.firmware_manager.is_firmware_installed(self._current_board):
            await self.firmware_manager.install_firmware_from_params(Vehicle.Sub, self._current_board)
        frame = self.load_sitl_frame()
        if frame == SITLFrame.UNDEFINED:
            frame = SITLFrame.VECTORED
            logger.warning(f"SITL frame is undefined. Setting {frame} as current frame.")
        self.current_sitl_frame = frame

        firmware_path = self.firmware_manager.firmware_path(self._current_board.platform)
        self.firmware_manager.validate_firmware(firmware_path, self._current_board.platform)

        # ArduPilot SITL binary will bind TCP port 5760 (server) and the mavlink router will connect to it as a client
        master_endpoint = Endpoint(
            name="Master",
            owner=self.settings.app_name,
            connection_type=EndpointType.TCPClient,
            place="127.0.0.1",
            argument=5760,
            protected=True,
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

        await self.start_mavlink_manager(master_endpoint)

    async def start_mavlink_manager(self, device: Endpoint) -> None:
        for endpoint in self.autopilot_default_endpoints:
            try:
                self.mavlink_manager.add_endpoint(endpoint)
            except EndpointAlreadyExists:
                pass
            except Exception as error:
                logger.warning(str(error))
        await self.mavlink_manager.start(device)

    @staticmethod
    async def available_boards(include_bootloaders: bool = False) -> List[FlightController]:
        all_boards = await BoardDetector.detect(True)
        if include_bootloaders:
            return all_boards
        return [board for board in all_boards if FlightControllerFlags.is_bootloader not in board.flags]

    async def change_board(self, board: FlightController) -> None:
        logger.info(f"Trying to run with '{board.name}'.")
        boards = await self.available_boards()
        if not any(board.name == detectedboard.name for detectedboard in boards):
            logger.error(f"Attempted to change active board to {board} which is not detected.")
            logger.info(f"detected boards are: {boards}")
            raise ValueError(f"Cannot use '{board.name}'. Board not detected.")
        self.set_preferred_board(board)
        await self.kill_ardupilot()
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

        # SITL should only be used if explicitly set by user, in which case it's a preferred board and the
        # previous return logic will get it. We do this to prevent the user thinking that it's physical board
        # is correctly running when in fact it was SITL automatically starting.
        real_boards = [board for board in boards if board.type not in [PlatformType.SITL, PlatformType.Manual]]
        if not real_boards:
            raise RuntimeError("No physical board detected and SITL/Manual board aren't explicitly chosen.")
        real_boards.sort(key=lambda board: board.platform)
        return real_boards[0]

    def running_ardupilot_processes(self) -> List[psutil.Process]:
        """Return list of all Ardupilot process running on system."""

        def is_ardupilot_process(process: psutil.Process) -> bool:
            """Checks if given process is using a Ardupilot's firmware file, for any known platform."""
            for platform in Platform:
                firmware_path = self.firmware_manager.firmware_path(platform)
                try:
                    if str(firmware_path) in " ".join(process.cmdline()):
                        return True
                except psutil.NoSuchProcess:
                    # process may have died before we could call cmdline()
                    pass
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
            raise AutoPilotProcessKillFail("Could not terminate Ardupilot subprocess.")
        logger.warning("Ardupilot subprocess already not running.")

    async def prune_ardupilot_processes(self) -> None:
        """Kill all system processes using Ardupilot's firmware file."""
        for process in self.running_ardupilot_processes():
            try:
                logger.debug(f"Killing Ardupilot process {process.name()}::{process.pid}.")
                process.kill()
            except Exception as error:
                logger.debug(f"Could not kill Ardupilot: {error}")

            try:
                process.wait(3)
                continue
            except Exception as error:
                logger.debug(f"Ardupilot appears to be running.. going to call pkill: {error}")

            try:
                subprocess.run(["kill", "-9", f"{process.pid}"], check=True)
            except Exception as error:
                raise AutoPilotProcessKillFail(f"Failed to kill {process.name()}::{process.pid}.") from error

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
        try:
            await self.terminate_ardupilot_subprocess()
            logger.info("Ardupilot subprocess terminated.")
        except AutoPilotProcessKillFail as error:
            # If we cannot control the process, we should force kill to get a clean slate
            # This would ensure we don't sit with a zombie process, or have lost track of the process
            logger.error(f"Failed to terminate Ardupilot subprocess: {error}")

        logger.info("Pruning Ardupilot's system processes.")
        await self.prune_ardupilot_processes()
        logger.info("Ardupilot's system processes pruned.")

        logger.info("Stopping Mavlink manager.")
        await self.mavlink_manager.stop()
        logger.info("Mavlink manager stopped.")

    async def start_ardupilot(self) -> None:
        # This only applies to autopilot process itself, mavlink manager will check by itself
        if self.should_be_running and self.is_running():
            return

        await self.setup()
        try:
            available_boards = await self.available_boards()
            if not available_boards:
                raise RuntimeError("No boards available.")
            if len(available_boards) > 1:
                logger.warning(f"More than a single board detected: {available_boards}")

            flight_controller = self.get_board_to_be_used(available_boards)
            logger.info(f"Using {flight_controller.name} flight-controller.")

            if flight_controller.platform.type == PlatformType.Linux:
                assert isinstance(flight_controller, LinuxFlightController)
                flight_controller.setup()
                await self.start_linux_board(flight_controller)
            elif flight_controller.platform.type == PlatformType.Serial:
                await self.start_serial(flight_controller)
            elif flight_controller.platform == Platform.SITL:
                await self.start_sitl()
            elif flight_controller.platform == Platform.Manual:
                await self.start_manual_board(flight_controller)
            else:
                raise RuntimeError(f"Invalid board type: {flight_controller}")
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

    async def add_new_endpoints(self, new_endpoints: Set[Endpoint]) -> None:
        """Add multiple endpoints to the mavlink manager and save them on the configuration file."""
        logger.info(f"Adding endpoints {[e.name for e in new_endpoints]} and updating settings file.")
        self.mavlink_manager.add_endpoints(new_endpoints)
        self._save_current_endpoints()
        await self.mavlink_manager.restart()

    async def remove_endpoints(self, endpoints_to_remove: Set[Endpoint]) -> None:
        """Remove multiple endpoints from the mavlink manager and save them on the configuration file."""
        logger.info(f"Removing endpoints {[e.name for e in endpoints_to_remove]} and updating settings file.")
        self.mavlink_manager.remove_endpoints(endpoints_to_remove)
        self._save_current_endpoints()
        await self.mavlink_manager.restart()

    async def update_endpoints(self, endpoints_to_update: Set[Endpoint]) -> None:
        """Update multiple endpoints from the mavlink manager and save them on the configuration file."""
        logger.info(f"Modifying endpoints {[e.name for e in endpoints_to_update]} and updating settings file.")
        self.mavlink_manager.update_endpoints(endpoints_to_update)
        self._save_current_endpoints()
        await self.mavlink_manager.restart()

    async def get_available_firmwares(self, vehicle: Vehicle, platform: Platform) -> List[Firmware]:
        return await self.firmware_manager.get_available_firmwares(vehicle, platform)

    async def install_firmware_from_file(
        self, firmware_path: pathlib.Path, board: FlightController, default_parameters: Optional[Parameters] = None
    ) -> None:
        await self.firmware_manager.install_firmware_from_file(firmware_path, board, default_parameters)

    async def install_firmware_from_url(
        self,
        url: str,
        board: FlightController,
        make_default: bool = False,
        default_parameters: Optional[Parameters] = None,
    ) -> None:
        await self.firmware_manager.install_firmware_from_url(url, board, make_default, default_parameters)

    async def restore_default_firmware(self, board: FlightController) -> None:
        await self.firmware_manager.restore_default_firmware(board)

    async def set_manual_board_master_endpoint(self, endpoint: Endpoint) -> bool:
        self.configuration["manual_board_master_endpoint"] = endpoint.as_dict()
        self.settings.save(self.configuration)
        self.mavlink_manager.master_endpoint = endpoint
        await self.mavlink_manager.restart()
        return True

    def get_manual_board_master_endpoint(self) -> Endpoint:
        default_master_endpoint = Endpoint(
            name="Manual Board Master Endpoint",
            owner=self.settings.app_name,
            connection_type=EndpointType.UDPServer,
            place="0.0.0.0",
            argument=14551,
            persistent=True,
            enabled=True,
        )
        endpoint = self.configuration.get("manual_board_master_endpoint", None)
        if endpoint is None:
            return default_master_endpoint
        return Endpoint(**endpoint)
