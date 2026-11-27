# pylint: disable=too-many-lines
import asyncio
import os
import pathlib
import subprocess
import time
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, AsyncIterator, List, Optional, Set, Tuple, Union
from uuid import uuid4

import psutil
from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from commonwealth.settings.manager import PydanticManager
from commonwealth.utils.Singleton import Singleton
from config import SERVICE_NAME
from elftools.elf.elffile import ELFFile
from exceptions import (
    AutoPilotProcessKillFail,
    NoDefaultFirmwareAvailable,
    NoPreferredBoardSet,
)
from firmware.FirmwareManagement import FirmwareManager
from flight_controller_detector.Detector import Detector as BoardDetector
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from flight_controller_detector.serial_by_id import SerialById
from loguru import logger
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.exceptions import EndpointAlreadyExists
from mavlink_proxy.Manager import Manager as MavlinkManager
from settings import SettingsV1
from typedefs import (
    Firmware,
    FlightController,
    FlightControllerFlags,
    Parameters,
    Platform,
    PlatformType,
    Serial,
    SITLFrame,
    TLogMode,
    Vehicle,
)


class RebootWait(Enum):
    BACK = "back"
    NEVER_LEFT = "never_left"
    STILL_GONE = "still_gone"


class AutoPilotManager(metaclass=Singleton):
    # pylint: disable=too-many-instance-attributes
    HEARTBEAT_BURST_MAX_RETRIES = 12
    SERIAL_POLL_INTERVAL = 0.5
    SERIAL_LEAVE_TIMEOUT = 10.0
    SERIAL_RETURN_TIMEOUT = 40.0

    def __init__(self) -> None:
        self._settings_manager: PydanticManager[SettingsV1] = PydanticManager(SERVICE_NAME, SettingsV1)
        self._settings_manager.settings.create_app_folders()
        self._current_board: Optional[FlightController] = None
        self._serial: Optional[SerialById] = None
        self._serial_absence_reported = False
        self._serial_paths: Set[str] = set()
        self._heartbeat_burst_pending = False
        self._heartbeat_burst_retries = 0
        self.should_be_running = False
        self._lifecycle_lock = asyncio.Lock()
        self.mavlink_manager = MavlinkManager()

        # Kept out of setup() because that runs on every start attempt, which would reset the counter
        self._start_fail_count = 0
        self._max_start_failures = 10

        # Kept out of setup(), a new one per start downloads and parses the whole ArduPilot manifest again
        self.firmware_manager = FirmwareManager(
            self._settings_manager.settings.firmware_folder,
            self._settings_manager.settings.defaults_folder,
            self._settings_manager.settings.user_firmware_folder,
        )

        self.autopilot_default_endpoints = [
            Endpoint(
                name="GCS Server Link",
                owner=SERVICE_NAME,
                connection_type=EndpointType.UDPServer,
                place="0.0.0.0",
                argument=14550,
                persistent=True,
                enabled=True,
            ),
            Endpoint(
                name="GCS Client Link",
                owner=SERVICE_NAME,
                connection_type=EndpointType.UDPClient,
                place="192.168.2.1",
                argument=14550,
                persistent=True,
                enabled=True,
            ),
            Endpoint(
                name="MAVLink2RestServer",
                owner=SERVICE_NAME,
                connection_type=EndpointType.UDPServer,
                place="127.0.0.1",
                argument=14001,
                persistent=True,
                protected=True,
            ),
            Endpoint(
                name="MAVLink2Rest",
                owner=SERVICE_NAME,
                connection_type=EndpointType.UDPClient,
                place="127.0.0.1",
                argument=14000,
                persistent=True,
                protected=True,
                overwrite_settings=True,
            ),
            Endpoint(
                name="Zenoh Deamon",
                owner=SERVICE_NAME,
                connection_type=EndpointType.Zenoh,
                place="0.0.0.0",
                argument=7117,
                persistent=True,
                protected=True,
            ),
            Endpoint(
                name="ZenohRaw",
                owner=SERVICE_NAME,
                connection_type=EndpointType.ZenohRaw,
                place="0.0.0.0",
                argument=7117,
                persistent=True,
                protected=True,
            ),
            Endpoint(
                name="Internal Link",
                owner=SERVICE_NAME,
                connection_type=EndpointType.TCPServer,
                place="127.0.0.1",
                argument=5777,
                persistent=True,
                protected=True,
                overwrite_settings=True,
            ),
            Endpoint(
                name="Ping360 Heading",
                owner=SERVICE_NAME,
                connection_type=EndpointType.UDPServer,
                place="0.0.0.0",
                argument=14660,
                persistent=True,
                protected=False,
            ),
        ]

    async def setup(self) -> None:
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
            await self._set_preferred_router_locked(self.mavlink_manager.tool.name())
            logger.info(f"Setting {self.mavlink_manager.tool.name()} as preferred router.")
        self.mavlink_manager.set_logdir(self._settings_manager.settings.log_path)
        self.mavlink_manager.set_tlog_mode(self.load_tlog_mode())

        self._load_endpoints()
        self.ardupilot_subprocess: Optional[Any] = None
        self.vehicle_manager = VehicleManager()
        self._heartbeat_fail_count = 0  # Consecutive heartbeat failures
        self._max_heartbeat_failures = 10  # Threshold for restarting Ardupilot after consecutive heartbeat failures
        # A new start looks the board up again, and nothing else clears these while the router is not meant to run
        self._serial = None
        self._serial_paths = set()
        self._serial_absence_reported = False
        self._heartbeat_burst_pending = False

        self.should_be_running = False
        self.remove_old_logs()
        self.current_sitl_frame = self.load_sitl_frame()

    def remove_old_logs(self) -> None:
        def need_to_remove_file(file: pathlib.Path) -> bool:
            now = time.time()
            week_old = now - 7 * 24 * 60 * 60
            return file.stat().st_size == 0 and file.stat().st_mtime < week_old

        try:
            firmware_log_files = list((self._settings_manager.settings.firmware_folder / "logs").iterdir())
            router_log_files = list(self._settings_manager.settings.log_path.iterdir())

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

    async def auto_restart_ardupilot(self) -> None:  # pylint: disable=too-many-branches
        """Auto-restart Ardupilot when it's not running but was supposed to."""
        while True:
            needs_restart = self.should_be_running and not self.is_running() and not self._lifecycle_lock.locked()
            if needs_restart:
                logger.debug("Restarting ardupilot...")
                async with self._lifecycle_lock:
                    try:
                        await self._kill_ardupilot_locked()
                    except Exception as error:
                        logger.warning(f"Could not kill Ardupilot: {error}")
                    try:
                        await self._start_ardupilot_locked()
                    except Exception as error:
                        self._start_fail_count += 1
                        logger.warning(
                            f"Could not start Ardupilot ({self._start_fail_count}/{self._max_start_failures}): {error}"
                        )
                        if self._start_fail_count >= self._max_start_failures:
                            self.should_be_running = False
                            logger.error(
                                "Consecutive start failures threshold reached, not retrying automatically. "
                                "Start the autopilot or change the board to try again."
                            )
            elif self.is_running():
                self._start_fail_count = 0

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

                if self._heartbeat_fail_count >= self._max_heartbeat_failures and not self._lifecycle_lock.locked():
                    # A board that is gone cannot answer, the router watchdog follows it when it comes back
                    if not self._serial_absence_reported:
                        logger.warning("Consecutive heartbeat failures threshold reached — restarting Ardupilot.")
                        try:
                            await self.restart_ardupilot()
                        except Exception as error:
                            logger.warning(f"Failed to restart Ardupilot after heartbeat failures: {error}")
                    self._heartbeat_fail_count = 0

            await asyncio.sleep(5.0)

    async def start_mavlink_manager_watchdog(self, interval: float = 5.0) -> None:
        """Auto-restart the MAVLink router if it dies while it should be running."""
        while True:
            await asyncio.sleep(interval)
            try:
                await self._restart_router_if_dead()
            except Exception as error:
                logger.error(f"Failed to restart Mavlink router. {error}")

    async def _restart_router_if_dead(self) -> None:
        # Lifecycle operations leave the router the way they want it, check again on the next tick
        if self._lifecycle_lock.locked():
            return
        async with self._lifecycle_lock:
            # setup() replaces the manager on every start, so always act on the current one
            mavlink_manager = self.mavlink_manager
            if not mavlink_manager.should_be_running:
                return
            # Looking for the board is blocking I/O
            left, moved_board = await asyncio.to_thread(self._locate_serial_board)
            if left:
                if not await self._follow_serial_board_locked(moved_board) or moved_board is None:
                    return
                self._arm_heartbeat_burst(moved_board)
            else:
                self._serial_absence_reported = False
                if not await mavlink_manager.is_running():
                    logger.warning("Mavlink router stopped. Trying to restart it.")
                    await mavlink_manager.restart()
                    if self._current_board is not None:
                        self._arm_heartbeat_burst(self._current_board)
        # The burst waits on mavlink2rest, up to its timeout, so it does not hold the lock
        if self._heartbeat_burst_pending:
            await self._retry_heartbeat_burst()

    def _serial_master_place(self, board: FlightController) -> str:
        master_endpoint = self.mavlink_manager.master_endpoint
        # The router can hold another node of the board than its latest, but never one that is not the board's
        if (
            master_endpoint is not None
            and master_endpoint.connection_type == EndpointType.Serial
            and master_endpoint.place in self._serial_paths
        ):
            return master_endpoint.place
        return board.path or ""

    def _locate_serial_board(self) -> Tuple[bool, Optional[FlightController]]:
        # A serial board that reboots or reconnects behind our back re-enumerates on a new device path while the
        # router keeps a handle to the old one
        board = self._current_board
        master_endpoint = self.mavlink_manager.master_endpoint
        if (
            board is None
            or board.type != PlatformType.Serial
            or master_endpoint is None
            or master_endpoint.connection_type != EndpointType.Serial
            # Another serial master is not ours to follow
            or master_endpoint.place not in self._serial_paths
        ):
            return False, None
        return self._locate_serial_board_at(board, master_endpoint.place)

    def _locate_serial_board_at(self, board: FlightController, place: str) -> Tuple[bool, Optional[FlightController]]:
        place = os.path.realpath(place)
        serial = self._serial
        if serial is not None and serial.link:
            current = serial.current_path()
            if current == place:
                return False, None
            return True, board.model_copy(update={"path": current}) if current else None
        if os.path.exists(place):
            return False, None
        # Without a by-id link, only a single candidate is known to be the same board
        candidates = [
            detected
            for detected in BoardDetector.detect_serial_flight_controllers()
            if detected.platform == board.platform
            and detected.path
            and FlightControllerFlags.is_bootloader not in detected.flags
        ]
        if len(candidates) > 1 and not self._serial_absence_reported:
            logger.warning(
                f"Several {board.platform.name} boards and no unique USB serial number, cannot tell which one is "
                "ours, waiting. Use Stop then Start to choose."
            )
        return True, candidates[0] if len(candidates) == 1 else None

    async def _follow_serial_board_locked(self, moved_board: Optional[FlightController]) -> bool:
        mavlink_manager = self.mavlink_manager
        if moved_board is None:
            if not self._serial_absence_reported:
                self._serial_absence_reported = True
                logger.warning("The serial board left its device path. Waiting for it to come back.")
            # Never keep a router on a path that is gone or that another board took over
            if await mavlink_manager.is_running():
                await mavlink_manager.tool.exit()
            return False
        logger.warning(f"Serial board moved to {moved_board.path}. Restarting Mavlink router on it.")
        # The restart points the master endpoint there even if the router fails to start
        await self._set_serial_board(moved_board, following=True)
        # A failed start leaves a new manager that only has the saved endpoints, restarting keeps what it has
        self._add_default_endpoints()
        await mavlink_manager.restart(self._serial_master_endpoint(moved_board))
        return True

    async def _set_serial_board(self, board: FlightController, following: bool = False) -> None:
        if not board.path:
            raise ValueError(f"Could not find device path for board {board.name}.")
        self._current_board = board
        # The device paths this board had since it was started, to tell it from another board of the same platform
        self._serial_paths = (self._serial_paths if following else set()) | {board.path}
        # Looked up again every time the board is started, never saved
        self._serial = await asyncio.to_thread(SerialById, board.path)
        self._serial_absence_reported = False

    @property
    def settings(self) -> SettingsV1:
        return self._settings_manager.settings

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
        self._settings_manager.settings.serials = serials
        self._settings_manager.save()

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
        serials = self._settings_manager.settings.serials
        if serials:
            return serials
        if isinstance(self._current_board, LinuxFlightController):
            return self._current_board.get_serials()
        return []

    def get_serial_cmdline(self) -> str:
        return " ".join([f"-{entry.port} {entry.endpoint}" for entry in self.get_serials()])

    def get_default_params_cmdline(self, platform: Platform) -> str:
        # check if file exists and return it's path as --defaults parameter
        default_params_path = self.firmware_manager.default_user_params_path(platform)
        if default_params_path.is_file():
            return f"--defaults {default_params_path}"
        return ""

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
            owner=SERVICE_NAME,
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

        command_line = (
            f"{firmware_path}"
            f" -A udp:{master_endpoint.place}:{master_endpoint.argument}"
            f" --log-directory {self._settings_manager.settings.firmware_folder}/logs/"
            f" --storage-directory {self._settings_manager.settings.firmware_folder}/storage/"
            f" {self.get_serial_cmdline()}"
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
            cwd=self._settings_manager.settings.firmware_folder,
        )

        await self.start_mavlink_manager(master_endpoint)

    @staticmethod
    def _is_px4(board: FlightController) -> bool:
        return "px4" in board.name.lower()

    @staticmethod
    def _serial_master_endpoint(board: FlightController) -> Endpoint:
        if not board.path:
            raise ValueError(f"Could not find device path for board {board.name}.")
        return Endpoint(
            name="Master",
            owner=SERVICE_NAME,
            connection_type=EndpointType.Serial,
            place=board.path,
            argument=57600 if AutoPilotManager._is_px4(board) else 115200,
            protected=True,
        )

    async def start_serial(self, board: FlightController) -> None:
        master_endpoint = self._serial_master_endpoint(board)
        await self._set_serial_board(board)
        await self.start_mavlink_manager(master_endpoint)
        await self._wake_up_px4(board)

    async def _wake_up_px4(self, board: FlightController) -> None:
        # PX4 needs at least one initial heartbeat to start sending data. It stays pending until the vehicle is
        # heard, so the router watchdog repeats it: a request that went through does not mean PX4 received it
        self._arm_heartbeat_burst(board)
        if self._heartbeat_burst_pending:
            await self._burst_heartbeat()

    def _arm_heartbeat_burst(self, board: FlightController) -> None:
        self._heartbeat_burst_pending = self._is_px4(board)
        self._heartbeat_burst_retries = 0

    async def _retry_heartbeat_burst(self) -> None:
        if await self.vehicle_manager.is_heart_beating():
            self._heartbeat_burst_pending = False
            return
        if self._heartbeat_burst_retries >= self.HEARTBEAT_BURST_MAX_RETRIES:
            self._heartbeat_burst_pending = False
            logger.warning("The vehicle did not answer the initial heartbeats, giving up on them.")
            return
        self._heartbeat_burst_retries += 1
        await self._burst_heartbeat()

    async def _burst_heartbeat(self) -> None:
        try:
            await self.vehicle_manager.burst_heartbeat()
        except Exception as error:
            logger.warning(f"Could not send the initial heartbeats: {error}")

    def set_sitl_frame(self, frame: SITLFrame) -> None:
        self.current_sitl_frame = frame
        self._settings_manager.settings.sitl_frame = frame
        self._settings_manager.save()

    def load_sitl_frame(self) -> SITLFrame:
        if self._settings_manager.settings.sitl_frame != SITLFrame.UNDEFINED:
            return SITLFrame(self._settings_manager.settings.sitl_frame)
        frame = SITLFrame.VECTORED
        logger.warning(f"SITL frame is undefined. Setting {frame} as current frame.")
        self.set_sitl_frame(frame)
        return frame

    async def set_preferred_router(self, router: str, tlog_mode: Optional[TLogMode] = None) -> None:
        async with self._lifecycle_lock:
            await self._set_preferred_router_locked(router, tlog_mode)

    async def _set_preferred_router_locked(self, router: str, tlog_mode: Optional[TLogMode] = None) -> None:
        self._settings_manager.settings.preferred_router = router
        if tlog_mode is not None:
            self._settings_manager.settings.tlog_mode = tlog_mode
            self.mavlink_manager.set_tlog_mode(tlog_mode)
        self._settings_manager.save()
        await self.mavlink_manager.set_preferred_router(router, self.autopilot_default_endpoints)

    def load_preferred_router(self) -> Optional[str]:
        try:
            return self._settings_manager.settings.preferred_router
        except KeyError:
            return None

    def load_tlog_mode(self) -> TLogMode:
        return self._settings_manager.settings.tlog_mode

    def set_start_on_boot(self, enabled: bool) -> None:
        self._settings_manager.settings.start_on_boot = enabled
        self._settings_manager.save()

    def should_start_on_boot(self) -> bool:
        return self._settings_manager.settings.start_on_boot

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
            owner=SERVICE_NAME,
            connection_type=EndpointType.TCPClient,
            place="127.0.0.1",
            argument=5760,
            protected=True,
        )
        # The default spawn location (Florianópolis) is provided as SIM_OPOS_* parameter
        # defaults instead of --home, which would lock the location and prevent users
        # from overriding it with the SIM_OPOS_* parameters.
        sitl_defaults = "SIM_OPOS_LAT -27.563\nSIM_OPOS_LNG -48.459\nSIM_OPOS_ALT 0.0\nSIM_OPOS_HDG 270.0\n"
        sitl_defaults_path = pathlib.Path(self._settings_manager.settings.firmware_folder, "sitl_defaults.parm")
        try:
            current_defaults = sitl_defaults_path.read_text(encoding="utf-8") if sitl_defaults_path.is_file() else None
            if current_defaults != sitl_defaults:
                # Unique temporary name plus atomic replace so concurrent calls cannot
                # race each other or expose a partially written file.
                temp_defaults_path = sitl_defaults_path.with_name(f"sitl_defaults.parm.{uuid4().hex}.tmp")
                temp_defaults_path.write_text(sitl_defaults, encoding="utf-8")
                os.replace(temp_defaults_path, sitl_defaults_path)
            defaults_args = ["--defaults", str(sitl_defaults_path)]
        except OSError as error:
            logger.warning(
                f"Failed to write SITL defaults file, falling back to --home "
                f"(SIM_OPOS_* position overrides will not apply): {error}"
            )
            defaults_args = ["--home", "-27.563,-48.459,0.0,270.0"]

        # pylint: disable=consider-using-with
        self.ardupilot_subprocess = subprocess.Popen(
            [
                firmware_path,
                "--model",
                self.current_sitl_frame.value,
                "--base-port",
                str(master_endpoint.argument),
                *defaults_args,
            ],
            shell=False,
            encoding="utf-8",
            errors="ignore",
            cwd=self._settings_manager.settings.firmware_folder,
        )

        await self.start_mavlink_manager(master_endpoint)

    def _add_default_endpoints(self) -> None:
        for endpoint in self.autopilot_default_endpoints:
            try:
                self.mavlink_manager.add_endpoint(endpoint)
            except EndpointAlreadyExists:
                pass
            except Exception as error:
                logger.warning(str(error))

    async def start_mavlink_manager(self, device: Endpoint) -> None:
        self._add_default_endpoints()
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
        async with self._lifecycle_lock:
            self.set_preferred_board(board)
            await self._kill_ardupilot_locked()
            await self._start_ardupilot_locked()

    def set_preferred_board(self, board: FlightController) -> None:
        logger.info(f"Setting {board.name} as preferred flight-controller.")
        self._settings_manager.settings.preferred_board = board
        self._settings_manager.save()

    def get_preferred_board(self) -> FlightController:
        preferred_board = self._settings_manager.settings.preferred_board
        if not preferred_board:
            raise NoPreferredBoardSet("Preferred board not set yet.")
        return preferred_board

    def get_board_to_be_used(self, boards: List[FlightController]) -> FlightController:
        """Check if preferred board exists and is connected. If so, use it, otherwise, choose by priority."""
        try:
            preferred_board = self.get_preferred_board()
            logger.debug(f"Preferred flight-controller is {preferred_board.name}.")
            for board in boards:
                # Compare connected boards with saved board, excluding path (which can change between sessions)
                if preferred_board.model_dump(exclude={"path"}).items() <= board.model_dump().items():
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

            # terminate() only asks. A wedged process would otherwise keep the serial ports and
            # the firmware file busy, blocking the install or restart that called this.
            logger.warning("Ardupilot subprocess ignored SIGTERM, sending SIGKILL.")
            self.ardupilot_subprocess.kill()
            for _ in range(10):
                if self.ardupilot_subprocess.poll() is not None:
                    logger.info("Ardupilot subprocess killed.")
                    return
                logger.debug("Waiting for the killed process to be reaped...")
                await asyncio.sleep(0.5)
            raise AutoPilotProcessKillFail("Could not kill Ardupilot subprocess.")
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
        async with self._lifecycle_lock:
            await self._kill_ardupilot_locked()

    async def _kill_ardupilot_locked(self) -> None:
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
        async with self._lifecycle_lock:
            await self._start_ardupilot_locked()

    async def _start_ardupilot_locked(self) -> None:
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
                await asyncio.to_thread(flight_controller.setup)
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
        async with self._lifecycle_lock:
            board = self.current_board
            # Serial boards are the only ones rebooted through MAVLink; everything else (SITL,
            # Linux, Manual, unknown) is a process/router we can just bounce.
            if board is None or board.type != PlatformType.Serial:
                await self._kill_ardupilot_locked()
                await self._start_ardupilot_locked()
                return

            # A start that failed forgets the board, which has to be recorded while its by-id link still exists
            if self._serial is None:
                await self._set_serial_board(board)
            await self.vehicle_manager.reboot_vehicle()

            # A serial board re-enumerates on USB after rebooting, so its device path changes and the router
            # keeps a stale handle. Follow the board like the router watchdog does, which keeps running the
            # autopilot if the board takes long to come back, or never comes back, and follows it later.
            result = await self._wait_for_serial_reboot(board)
            if isinstance(result, FlightController):
                await self._follow_serial_board_locked(result)
                self.should_be_running = True
                await self._wake_up_px4(result)
                return
            if result == RebootWait.STILL_GONE:
                # The follow state stays as it was, the error is for whoever asked for the restart
                message = f"{board.name} did not come back after reboot."
                if self.should_be_running:
                    message += " Following it when it does."
                logger.warning(message)
                raise RuntimeError(message)
            if result == RebootWait.NEVER_LEFT:
                logger.warning(f"{board.name} did not disconnect after reboot. Restarting its link anyway.")
            # Back on the same path, or never gone: the router still holds a handle that may be stale
            self._add_default_endpoints()
            await self.mavlink_manager.restart(self._serial_master_endpoint(board))
            self.should_be_running = True
            self._serial_absence_reported = False
            await self._wake_up_px4(board)

    async def _wait_for_serial_reboot(self, board: FlightController) -> Union[RebootWait, FlightController]:
        """Waits for a board that was just rebooted to leave its device path and come back, and tells how it ended.

        The result is the board with its new device path if it came back on another one.

        The router is released the first time the board is seen gone and not already back on another node.

        Boards reached through a separate USB-serial adapter never leave, so waiting for that is best-effort.
        """
        place = self._serial_master_place(board)
        now = time.monotonic()
        leave_deadline, return_deadline = now + self.SERIAL_LEAVE_TIMEOUT, now + self.SERIAL_RETURN_TIMEOUT
        left = False
        while time.monotonic() < (return_deadline if left else leave_deadline):
            await asyncio.sleep(self.SERIAL_POLL_INTERVAL)
            gone, moved_board = await asyncio.to_thread(self._locate_serial_board_at, board, place)
            if gone and moved_board is None and not left:
                await self._follow_serial_board_locked(None)
            left = left or gone
            if moved_board is not None:
                return moved_board
            if left and not gone:
                return RebootWait.BACK
        return RebootWait.STILL_GONE if left else RebootWait.NEVER_LEFT

    def _get_configuration_endpoints(self) -> Set[Endpoint]:
        endpoints: Set[Endpoint] = set()
        for raw in self._settings_manager.settings.endpoints:
            endpoint = Endpoint.from_raw(raw)
            if endpoint is None:
                logger.warning(f"Ignoring invalid endpoint record {raw}")
                continue
            endpoints.add(endpoint)
        return endpoints

    def _save_endpoints_to_configuration(self, endpoints: Set[Endpoint]) -> None:
        self._settings_manager.settings.endpoints = endpoints
        self._settings_manager.save()

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
        except Exception as error:
            logger.error(f"Could not save endpoints. {error}")

    def get_endpoints(self) -> Set[Endpoint]:
        """Get all endpoints from the mavlink manager."""
        return self.mavlink_manager.endpoints()

    async def add_new_endpoints(self, new_endpoints: Set[Endpoint]) -> None:
        """Add multiple endpoints to the mavlink manager and save them on the configuration file."""
        logger.info(f"Adding endpoints {[e.name for e in new_endpoints]} and updating settings file.")
        async with self._lifecycle_lock:
            self.mavlink_manager.add_endpoints(new_endpoints)
            self._save_current_endpoints()
            await self._apply_router_changes_locked()

    async def remove_endpoints(self, endpoints_to_remove: Set[Endpoint]) -> None:
        """Remove multiple endpoints from the mavlink manager and save them on the configuration file."""
        logger.info(f"Removing endpoints {[e.name for e in endpoints_to_remove]} and updating settings file.")
        async with self._lifecycle_lock:
            self.mavlink_manager.remove_endpoints(endpoints_to_remove)
            self._save_current_endpoints()
            await self._apply_router_changes_locked()

    async def update_endpoints(self, endpoints_to_update: Set[Endpoint]) -> None:
        """Update multiple endpoints from the mavlink manager and save them on the configuration file."""
        logger.info(f"Modifying endpoints {[e.name for e in endpoints_to_update]} and updating settings file.")
        async with self._lifecycle_lock:
            self.mavlink_manager.update_endpoints(endpoints_to_update)
            self._save_current_endpoints()
            await self._apply_router_changes_locked()

    async def _apply_router_changes_locked(self) -> None:
        # A stopped router picks the saved changes up on its next start, restarting it here would
        # bring it back without the autopilot and the watchdog would keep it alive
        if self.mavlink_manager.should_be_running:
            await self.mavlink_manager.restart()

    async def get_available_firmwares(self, vehicle: Vehicle, platform: Platform) -> List[Firmware]:
        return await self.firmware_manager.get_available_firmwares(vehicle, platform)

    @asynccontextmanager
    async def _autopilot_paused(self) -> AsyncIterator[None]:
        async with self._lifecycle_lock:
            failed = True
            try:
                await self._kill_ardupilot_locked()
                yield
                failed = False
            except Exception as error:
                # The start below can fail too and its error would replace this one
                logger.error(f"Firmware operation failed: {error}")
                raise
            finally:
                # A failed flash leaves the board in its bootloader and an early failure has nothing to wait for
                if not failed:
                    try:
                        await self._wait_for_serial_board()
                    except Exception as error:
                        logger.warning(f"Could not wait for the serial board: {error}")
                await self._start_ardupilot_locked()

    async def _wait_for_serial_board(self) -> None:
        board = self._current_board
        if board is None or board.type != PlatformType.Serial:
            return
        # A flashed board can take a while to be back
        deadline = time.monotonic() + self.SERIAL_RETURN_TIMEOUT
        while time.monotonic() < deadline and not self._has_serial_board(await self.available_boards(), board.platform):
            await asyncio.sleep(self.SERIAL_POLL_INTERVAL)

    @staticmethod
    def _has_serial_board(boards: List[FlightController], platform: Platform) -> bool:
        # SITL and Manual boards are always listed, so look for the serial board itself
        return any(board.type == PlatformType.Serial and board.platform == platform for board in boards)

    def _live_board(self, board: FlightController) -> FlightController:
        """The board with the path it has now, if it was resolved before the board re-enumerated."""
        current, serial = self._current_board, self._serial
        if (
            not board.path
            or board.type != PlatformType.Serial
            or current is None
            or current.type != PlatformType.Serial
        ):
            return board
        if serial is None or board.path not in self._serial_paths or os.path.exists(board.path):
            return board
        path = serial.current_path()
        if path is None:
            return board
        return board.model_copy(update={"path": path})

    async def install_firmware_from_file(
        self, firmware_path: pathlib.Path, board: FlightController, default_parameters: Optional[Parameters] = None
    ) -> None:
        async with self._autopilot_paused():
            board = await asyncio.to_thread(self._live_board, board)
            await self.firmware_manager.install_firmware_from_file(firmware_path, board, default_parameters)

    async def install_firmware_from_url(
        self,
        url: str,
        board: FlightController,
        make_default: bool = False,
        default_parameters: Optional[Parameters] = None,
    ) -> None:
        async with self._autopilot_paused():
            board = await asyncio.to_thread(self._live_board, board)
            await self.firmware_manager.install_firmware_from_url(url, board, make_default, default_parameters)

    async def restore_default_firmware(self, board: FlightController) -> None:
        async with self._autopilot_paused():
            board = await asyncio.to_thread(self._live_board, board)
            await self.firmware_manager.restore_default_firmware(board)

    async def set_manual_board_master_endpoint(self, endpoint: Endpoint) -> bool:
        async with self._lifecycle_lock:
            self._settings_manager.settings.manual_board_master_endpoint = endpoint
            self._settings_manager.save()
            self.mavlink_manager.master_endpoint = endpoint
            await self._apply_router_changes_locked()
        return True

    def get_manual_board_master_endpoint(self) -> Endpoint:
        default_master_endpoint = Endpoint(
            name="Manual Board Master Endpoint",
            owner=SERVICE_NAME,
            connection_type=EndpointType.UDPServer,
            place="0.0.0.0",
            argument=14551,
            persistent=True,
            enabled=True,
        )
        endpoint = self._settings_manager.settings.manual_board_master_endpoint
        if endpoint is None:
            return default_master_endpoint
        return endpoint
