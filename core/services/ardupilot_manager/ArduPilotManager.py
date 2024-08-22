import asyncio
import os
import pathlib
import select
import subprocess
import time
from copy import deepcopy
from typing import Any, List, Optional, Set

import psutil
from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from commonwealth.utils.Singleton import Singleton
from elftools.elf.elffile import ELFFile
from loguru import logger

from exceptions import (
    ArdupilotProcessKillFail,
    EndpointAlreadyExists,
    NoDefaultFirmwareAvailable,
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
    FlightControllerFlags,
    Parameters,
    Platform,
    PlatformType,
    Serial,
    SITLFrame,
    Vehicle,
)


class ArduPilotManager(metaclass=Singleton):
    # pylint: disable=too-many-instance-attributes
    def __init__(self) -> None:
        self.settings = Settings()
        self.settings.create_app_folders()
        self._current_board: Optional[FlightController] = None

        # Load settings and do the initial configuration
        if self.settings.load():
            logger.info(f"Loaded settings from {self.settings.settings_file}.")
            logger.debug(self.settings.content)
        else:
            self.settings.create_settings_file()

    async def setup(self) -> None:
        # This is the logical continuation of __init__(), extracted due to its async nature
        self.configuration = deepcopy(self.settings.content)
        self.mavlink_manager = MavlinkManager(self.load_preferred_router())
        if not self.load_preferred_router():
            await self.set_preferred_router(self.mavlink_manager.available_interfaces()[0].name())
            logger.info(f"Setting {self.mavlink_manager.available_interfaces()[0].name()} as preferred router.")
        self.mavlink_manager.set_logdir(self.settings.log_path)

        self._load_endpoints()
        self.ardupilot_subprocess: Optional[Any] = None
        self.firmware_manager = FirmwareManager(
            self.settings.firmware_folder, self.settings.defaults_folder, self.settings.user_firmware_folder
        )
        self.vehicle_manager = VehicleManager()

        self.should_be_running = False
        self.remove_old_logs()
        self.current_sitl_frame = self.load_sitl_frame()

    def consume_output(self):
        # logger.debug("Consuming output...")
        if self.ardupilot_subprocess is not None and self.ardupilot_subprocess.poll() is None:
            output_streams = [self.ardupilot_subprocess.stdout, self.ardupilot_subprocess.stderr]
            fd_list = [stream.fileno() for stream in output_streams]

            # Use select to check for available data on the file descriptors
            ready_fds, _, _ = select.select(fd_list, [], [], 0)

            for fd in ready_fds:
                # Find the corresponding stream and read the available data
                for stream in output_streams:
                    if stream.fileno() == fd:
                        logger.debug(f"Reading from {stream.name}")
                        line = os.read(fd, 1024)  # read up to 1024 bytes
                        if line:
                            # Process the line of output
                            logger.info(f"Autopilot: {line}")
        # logger.debug(f"done")

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

    async def auto_restart_ardupilot(self) -> None:
        """Auto-restart Ardupilot when it's not running but was supposed to."""
        while True:
            self.consume_output()
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
            return [
                Serial(port="C", endpoint="/dev/ttyS0"),
                Serial(port="B", endpoint="/dev/ttyAMA1"),
                Serial(port="E", endpoint="/dev/ttyAMA2"),
                Serial(port="F", endpoint="/dev/ttyAMA3"),
            ]
        serials = []
        for entry in self.configuration["serials"]:
            try:
                serials.append(Serial(port=entry["port"], endpoint=entry["endpoint"]))
            except Exception as e:
                logger.error(f"Entry is invalid! {entry['port']}:{entry['endpoint']}")
                logger.error(e)
        return serials

    def get_serial_cmdlines(self) -> List[str]:
        cmdlines = [[f"-{entry.port}", f"{entry.endpoint}"] for entry in self.get_serials()]
        flattened_array = [element for tup in cmdlines for element in tup]
        return flattened_array

    def get_default_params_cmdline(self, platform: Platform) -> List[str]:
        # check if file exists and return it's path as --defaults parameter
        default_params_path = self.firmware_manager.default_user_params_path(platform)
        if default_params_path.is_file():
            return ["--defaults", f"{default_params_path}"]
        return ""

    async def start_linux_board(self, board: FlightController) -> None:
        self._current_board = board
        if not self.firmware_manager.is_firmware_installed(self._current_board):
            if board.platform == Platform.Navigator:
                self.firmware_manager.install_firmware_from_file(
                    pathlib.Path("/root/blueos-files/ardupilot-manager/default/ardupilot_navigator"),
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

        command_line = [
            f"{firmware_path}",
            f"-A",
            f"udp:{master_endpoint.place}:{master_endpoint.argument}",
            f"--log-directory",
            f"{self.settings.firmware_folder}/logs/",
            f"--storage-directory",
            f"{self.settings.firmware_folder}/storage/",
            *self.get_serial_cmdlines(),
            *self.get_default_params_cmdline(board.platform),
        ]

        if self.firmware_has_debug_symbols(firmware_path):
            logger.info("Debug symbols found, launching with gdb server...")
            command_line = ["gdbserver", "0.0.0.0:5555", *command_line]

        logger.info(f"Using command line: '{command_line}'")
        self.ardupilot_subprocess = subprocess.Popen(
            command_line,
            shell=False,
            encoding="utf-8",
            errors="ignore",
            cwd=self.settings.firmware_folder,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        await self.start_mavlink_manager(master_endpoint)

    async def start_serial(self, board: FlightController) -> None:
        if not board.path:
            raise ValueError(f"Could not find device path for board {board.name}.")
        self._current_board = board
        baudrate = 115200
        if "px4" in board.name.lower():
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

    def set_sitl_frame(self, frame: SITLFrame) -> None:
        self.current_sitl_frame = frame
        self.configuration["sitl_frame"] = frame
        self.settings.save(self.configuration)

    def load_sitl_frame(self) -> SITLFrame:
        if self.settings.sitl_frame != SITLFrame.UNDEFINED:
            return self.settings.sitl_frame
        frame = SITLFrame.VECTORED
        logger.warning(f"SITL frame is undefined. Setting {frame} as current frame.")
        self.set_sitl_frame(frame)
        return frame

    async def set_preferred_router(self, router: str) -> None:
        self.settings.preferred_router = router
        self.configuration["preferred_router"] = router
        self.settings.save(self.configuration)
        await self.mavlink_manager.set_preferred_router(router)

    def load_preferred_router(self) -> Optional[str]:
        try:
            return self.configuration["preferred_router"]  # type: ignore
        except KeyError:
            return None

    def get_available_routers(self) -> List[str]:
        return [router.name() for router in self.mavlink_manager.available_interfaces()]

    async def start_sitl(self) -> None:
        self._current_board = BoardDetector.detect_sitl()
        if not self.firmware_manager.is_firmware_installed(self._current_board):
            self.firmware_manager.install_firmware_from_params(Vehicle.Sub, self._current_board)
        frame = self.settings.sitl_frame
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            encoding="utf-8",
            errors="ignore",
            cwd=self.settings.firmware_folder,
        )

        await self.start_mavlink_manager(master_endpoint)

    async def start_mavlink_manager(self, device: Endpoint) -> None:
        default_endpoints = [
            Endpoint(
                name="GCS Server Link",
                owner=self.settings.app_name,
                connection_type=EndpointType.UDPServer,
                place="0.0.0.0",
                argument=14550,
                persistent=True,
                enabled=False,
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
                name="MAVLink2Rest",
                owner=self.settings.app_name,
                connection_type=EndpointType.UDPClient,
                place="127.0.0.1",
                argument=14000,
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
        await self.mavlink_manager.start(device)

    @staticmethod
    async def available_boards(include_bootloaders: bool = False) -> List[FlightController]:
        all_boards = await BoardDetector.detect(True)
        if include_bootloaders:
            return all_boards
        return [board for board in all_boards if FlightControllerFlags.is_bootloader not in board.flags]

    async def change_board(self, board: FlightController) -> None:
        logger.info(f"Trying to run with '{board.name}'.")
        if board not in await self.available_boards():
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
        real_boards = [board for board in boards if board.type != PlatformType.SITL]
        if not real_boards:
            raise RuntimeError("Only available board is SITL, and it wasn't explicitly chosen.")
        real_boards.sort(key=lambda board: board.platform)
        return real_boards[0]

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
            except Exception as error:
                logger.debug(f"Could not kill Ardupilot: {error}")

            try:
                process.wait(3)
                continue
            except Exception as error:
                logger.debug(f"Ardupilot appears to be running.. going to call pkill: {error}")

            try:
                subprocess.run(["pkill", "-9", process.pid], check=True)
            except Exception as error:
                raise ArdupilotProcessKillFail(f"Failed to kill {process.name()}::{process.pid}.") from error

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
        await self.mavlink_manager.stop()
        logger.info("Mavlink manager stopped.")

    async def start_ardupilot(self) -> None:
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
                await self.start_linux_board(flight_controller)
            elif flight_controller.platform.type == PlatformType.Serial:
                await self.start_serial(flight_controller)
            elif flight_controller.platform == Platform.SITL:
                await self.start_sitl()
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

    def get_available_firmwares(self, vehicle: Vehicle, platform: Platform) -> List[Firmware]:
        return self.firmware_manager.get_available_firmwares(vehicle, platform)

    def install_firmware_from_file(
        self, firmware_path: pathlib.Path, board: FlightController, default_parameters: Optional[Parameters] = None
    ) -> None:
        self.firmware_manager.install_firmware_from_file(firmware_path, board, default_parameters)

    def install_firmware_from_url(
        self,
        url: str,
        board: FlightController,
        make_default: bool = False,
        default_parameters: Optional[Parameters] = None,
    ) -> None:
        self.firmware_manager.install_firmware_from_url(url, board, make_default, default_parameters)

    def restore_default_firmware(self, board: FlightController) -> None:
        self.firmware_manager.restore_default_firmware(board)
