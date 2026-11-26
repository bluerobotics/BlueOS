import asyncio
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional

import flight_controller_detector.Detector as detector_module
import pytest
import serial
from flight_controller_detector.Detector import Detector
from flight_controller_detector.serial_identification import (
    is_plausible_autopilot,
    serial_platform_name,
)
from typedefs import FlightController, FlightControllerFlags, Platform, PlatformType

pytestmark = pytest.mark.asyncio

REAL_ASK_BOOTLOADER = Detector._ask_bootloader_for_board_id_sync


@dataclass
class FakePort:  # pylint: disable=too-many-instance-attributes
    device: str
    product: Optional[str] = None
    manufacturer: Optional[str] = None
    vid: Optional[int] = 0x1209
    pid: Optional[int] = 0x5741
    serial_number: Optional[str] = "1234"
    usb_device_path: Optional[str] = "/sys/devices/usb1/1-1"
    location: Optional[str] = "1-1:1.0"

    @property
    def name(self) -> str:
        return self.device.rsplit("/", 1)[-1]


class FakeProbes:
    """Board ids answered on each device, by MAVLink and by the bootloader protocol."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.mavlink: Dict[str, int] = {}
        self.bootloader: Dict[str, int] = {}
        self.probed: List[str] = []
        self.ports: List[FakePort] = []
        monkeypatch.setattr(detector_module, "comports", lambda: self.ports)
        monkeypatch.setattr(detector_module, "get_board_id", self.get_board_id)
        monkeypatch.setattr(Detector, "_ask_bootloader_for_board_id_sync", self.ask_bootloader)

    async def get_board_id(self, device: str) -> Optional[int]:
        self.probed.append(device)
        return self.mavlink.get(device)

    def ask_bootloader(self, device: str) -> Optional[int]:
        self.probed.append(device)
        return self.bootloader.get(device)


@pytest.fixture(name="probes")
def fixture_probes(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeProbes]:
    Detector.invalidate_caches()
    monkeypatch.setattr(Detector, "_port_identities", {})
    monkeypatch.setattr(Detector, "_last_serial_boards", [])
    # A lock that ever waited is bound to the event loop of that test
    monkeypatch.setattr(Detector, "_probing_lock", asyncio.Lock())
    yield FakeProbes(monkeypatch)
    Detector.invalidate_caches()


async def detect(*known_boards: FlightController) -> List[FlightController]:
    Detector.invalidate_caches()
    boards: List[FlightController] = await Detector.detect_serial_flight_controllers(tuple(known_boards))
    return boards


async def test_non_usb_ports_are_never_probed(probes: FakeProbes) -> None:
    probes.ports = [
        FakePort("/dev/ttyAMA0", vid=None, pid=None, usb_device_path=None, serial_number=None, location=None),
        FakePort("/dev/ttyS0", vid=None, pid=None, usb_device_path=None, serial_number=None, location=None),
        FakePort("/dev/rfcomm0", vid=None, pid=None, usb_device_path=None, serial_number=None, location=None),
    ]
    probes.mavlink = {port.device: 1 for port in probes.ports}
    assert not await detect()
    assert not probes.probed


async def test_unrelated_usb_devices_are_not_probed(probes: FakeProbes) -> None:
    probes.ports = [
        FakePort("/dev/ttyUSB0", product="FT232R USB UART", manufacturer="FTDI", vid=0x0403, pid=0x6001),
        FakePort(
            "/dev/ttyACM0",
            product="CUAV CAN Babel",
            manufacturer="CUAV",
            vid=0x0483,
            usb_device_path="/sys/devices/usb1/1-2",
        ),
    ]
    probes.mavlink = {port.device: 1 for port in probes.ports}
    assert not await detect()
    assert not probes.probed


async def test_composite_device_is_probed_once(probes: FakeProbes) -> None:
    probes.ports = [
        FakePort("/dev/ttyACM1", product="CubeOrange", location="1-1:1.2"),
        FakePort("/dev/ttyACM0", product="CubeOrange", location="1-1:1.0"),
    ]
    probes.mavlink = {"/dev/ttyACM0": 140, "/dev/ttyACM1": 140}
    boards = await detect()
    assert [board.path for board in boards] == ["/dev/ttyACM0"]
    assert probes.probed == ["/dev/ttyACM0"]


async def test_composite_device_tries_next_interface(probes: FakeProbes) -> None:
    probes.ports = [
        FakePort("/dev/ttyACM0", product="CubeOrange", location="1-1:1.0"),
        FakePort("/dev/ttyACM1", product="CubeOrange", location="1-1:1.2"),
    ]
    probes.mavlink = {"/dev/ttyACM1": 140}
    boards = await detect()
    assert [board.path for board in boards] == ["/dev/ttyACM1"]
    assert probes.probed == ["/dev/ttyACM0", "/dev/ttyACM1"]


async def test_known_running_board_is_reused_without_probing(probes: FakeProbes) -> None:
    running = FlightController(
        name="CubeOrange",
        platform=Platform(name="CubeOrange", platform_type=PlatformType.Serial),
        path="/dev/ttyACM0",
        ardupilot_board_id=140,
    )
    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange")]
    assert await detect(running) == [running]
    assert not probes.probed


async def test_known_board_is_reused_while_the_same_device_is_on_its_path(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange")]
    probes.mavlink = {"/dev/ttyACM0": 140}
    (running,) = await detect()
    probes.probed.clear()

    # The router now holds the port, the identity recorded by the first probe must survive cache invalidation
    probes.mavlink = {}
    assert await detect(running) == [running]
    assert not probes.probed


async def test_known_board_is_not_reused_for_another_device_on_its_path(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange")]
    probes.mavlink = {"/dev/ttyACM0": 140}
    (running,) = await detect()
    probes.probed.clear()

    probes.ports = [
        FakePort(
            "/dev/ttyACM0", product="MatekH743", vid=0x1209, pid=0x5740, serial_number="9999", manufacturer="ArduPilot"
        )
    ]
    probes.mavlink = {"/dev/ttyACM0": 1013}
    (board,) = await detect(running)
    assert board.ardupilot_board_id == 1013
    assert board.platform.name == "MatekH743"
    assert probes.probed == ["/dev/ttyACM0"]


async def test_known_board_is_probed_again_after_flashing_another_build(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="Pixhawk1", manufacturer="ArduPilot")]
    probes.mavlink = {"/dev/ttyACM0": 9}
    (running,) = await detect()
    probes.probed.clear()

    # Same hardware, VID/PID and MCU serial number, only the USB strings of the build change
    probes.ports = [FakePort("/dev/ttyACM0", product="fmuv3", manufacturer="ArduPilot")]
    (board,) = await detect(running)
    assert board.platform.name == "fmuv3"
    assert probes.probed == ["/dev/ttyACM0"]


async def test_paused_probing_reuses_last_detection(probes: FakeProbes) -> None:
    probes.ports = [
        FakePort("/dev/ttyACM0", product="CubeOrange"),
        FakePort("/dev/ttyACM1", product="MatekH743-BL", usb_device_path="/sys/devices/usb1/1-2"),
    ]
    probes.mavlink = {"/dev/ttyACM0": 140}
    probes.bootloader = {"/dev/ttyACM1": 1013}
    boards = await detect()
    assert len(boards) == 2
    probes.probed.clear()

    with Detector.pause_probing():
        assert Detector.is_probing_paused()
        assert await detect() == boards
    assert not probes.probed
    assert not Detector.is_probing_paused()

    await detect()
    assert sorted(probes.probed) == ["/dev/ttyACM0", "/dev/ttyACM1"]


async def test_paused_probing_without_previous_detection(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange-BL")]
    probes.bootloader = {"/dev/ttyACM0": 140}
    with Detector.pause_probing():
        assert not await detect()
    assert not probes.probed


async def test_pause_stops_probe_pass_in_flight(probes: FakeProbes, monkeypatch: pytest.MonkeyPatch) -> None:
    probes.ports = [
        FakePort("/dev/ttyACM0", product="CubeOrange"),
        FakePort("/dev/ttyACM1", product="MatekH743", usb_device_path="/sys/devices/usb1/1-2"),
    ]
    probes.mavlink = {"/dev/ttyACM0": 140, "/dev/ttyACM1": 1013}
    previous = await detect()
    probes.probed.clear()

    first_probe_started = asyncio.Event()
    release_first_probe = asyncio.Event()
    get_board_id = probes.get_board_id

    async def slow_get_board_id(device: str) -> Optional[int]:
        first_probe_started.set()
        await release_first_probe.wait()
        return await get_board_id(device)

    monkeypatch.setattr(detector_module, "get_board_id", slow_get_board_id)
    detection = asyncio.create_task(detect())
    await first_probe_started.wait()

    with Detector.pause_probing():
        idle = asyncio.create_task(Detector.wait_for_idle())
        await asyncio.sleep(0.01)
        assert not idle.done(), "the probe in flight still holds the port"
        release_first_probe.set()
        await idle
        assert await detection == previous
        assert probes.probed == ["/dev/ttyACM0"], "no port must be opened once paused"


async def test_wait_for_idle_returns_when_not_probing(probes: FakeProbes) -> None:
    with Detector.pause_probing():
        await asyncio.wait_for(Detector.wait_for_idle(), timeout=1)
    assert not probes.probed


async def test_probing_pause_is_released_on_errors(probes: FakeProbes) -> None:
    with pytest.raises(RuntimeError):
        with Detector.pause_probing():
            with Detector.pause_probing():
                raise RuntimeError("flash failed")
    assert not Detector.is_probing_paused()
    assert not probes.probed


async def test_known_board_is_not_reported_when_port_disappears(probes: FakeProbes) -> None:
    running = FlightController(
        name="CubeOrange",
        platform=Platform(name="CubeOrange", platform_type=PlatformType.Serial),
        path="/dev/ttyACM0",
        ardupilot_board_id=140,
    )
    probes.ports = [FakePort("/dev/ttyACM1", product="Other", vid=0x1234)]
    assert not await detect(running)
    assert not probes.probed


async def test_failing_probe_does_not_break_detection(probes: FakeProbes, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_serial(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("not a bootloader")

    monkeypatch.setattr(Detector, "_ask_bootloader_for_board_id_sync", REAL_ASK_BOOTLOADER)
    monkeypatch.setattr(serial, "Serial", broken_serial)
    probes.ports = [
        FakePort("/dev/ttyACM0", product="Weird-BL"),
        FakePort("/dev/ttyACM1", product="MatekH743", usb_device_path="/sys/devices/usb1/1-2"),
    ]
    probes.mavlink = {"/dev/ttyACM1": 1013}
    boards = await detect()
    assert [board.path for board in boards] == ["/dev/ttyACM1"]


async def test_bootloader_port_uses_manifest_platform(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="MatekH743-BL", manufacturer="ArduPilot")]
    probes.bootloader = {"/dev/ttyACM0": 1013}
    (board,) = await detect()
    assert board.name == "MatekH743-BL"
    assert board.platform == Platform(name="MatekH743", platform_type=PlatformType.Serial)
    assert board.ardupilot_board_id == 1013
    assert board.flags == [FlightControllerFlags.is_bootloader]


async def test_legacy_px4_products_use_legacy_platform(probes: FakeProbes) -> None:
    probes.ports = [
        FakePort("/dev/ttyACM0", product="PX4 FMU v2.x", manufacturer="3D Robotics", vid=0x26AC),
        FakePort("/dev/ttyACM1", product="PX4 BL FMU v2.x", vid=0x26AC, usb_device_path="/sys/devices/usb1/1-2"),
    ]
    probes.mavlink = {"/dev/ttyACM0": 9}
    probes.bootloader = {"/dev/ttyACM1": 255}
    app, bootloader = await detect()
    assert app.platform == Platform(name="Pixhawk1", platform_type=PlatformType.Serial)
    assert bootloader.platform == app.platform
    assert bootloader.ardupilot_board_id == 9
    assert FlightControllerFlags.is_bootloader in bootloader.flags


async def test_port_without_board_id_is_skipped(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange")]
    assert not await detect()
    assert probes.probed == ["/dev/ttyACM0"]


async def redetect() -> List[FlightController]:
    """Detect again, dropping only the detection list cache."""
    Detector._probe_serial_flight_controllers.invalidate()  # type: ignore[attr-defined]
    boards: List[FlightController] = await Detector.detect_serial_flight_controllers(())
    return boards


async def test_ports_without_board_are_not_probed_again(probes: FakeProbes) -> None:
    port = FakePort("/dev/ttyACM0", product="Arduino Uno", manufacturer="Arduino (www.arduino.cc)", vid=0x2341)
    probes.ports = [port]
    assert not await redetect()
    assert not await redetect()
    assert probes.probed == ["/dev/ttyACM0"]

    Detector.invalidate_caches()
    assert not await redetect()
    assert probes.probed == ["/dev/ttyACM0"] * 2


async def test_ports_without_board_are_probed_again_once_replugged(probes: FakeProbes) -> None:
    port = FakePort("/dev/ttyACM0", product="CubeOrange")
    probes.ports = [port]
    assert not await redetect()

    probes.ports = []
    assert not await redetect()
    probes.ports = [port]
    probes.mavlink = {"/dev/ttyACM0": 140}
    assert len(await redetect()) == 1
    assert probes.probed == ["/dev/ttyACM0"] * 2


async def test_ports_without_board_are_probed_again_when_the_device_changes(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange-BL")]
    assert not await redetect()

    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange")]
    probes.mavlink = {"/dev/ttyACM0": 140}
    assert len(await redetect()) == 1


async def test_ports_without_board_are_probed_again_after_a_while(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange")]
    assert not await redetect()

    for key in Detector._no_board_cache:
        Detector._no_board_cache[key] -= detector_module.NO_BOARD_CACHE_SECONDS
    assert not await redetect()
    assert probes.probed == ["/dev/ttyACM0"] * 2


async def test_only_successful_bootloader_probes_are_cached(probes: FakeProbes) -> None:
    port = FakePort("/dev/ttyACM0", product="CubeOrange-BL")
    assert await Detector.ask_bootloader_for_board_id(port) is None  # type: ignore[arg-type]
    probes.bootloader = {"/dev/ttyACM0": 140}
    assert await Detector.ask_bootloader_for_board_id(port) == 140  # type: ignore[arg-type]
    probes.bootloader = {}
    assert await Detector.ask_bootloader_for_board_id(port) == 140  # type: ignore[arg-type]
    assert probes.probed == ["/dev/ttyACM0", "/dev/ttyACM0"]

    Detector.invalidate_caches()
    assert await Detector.ask_bootloader_for_board_id(port) is None  # type: ignore[arg-type]


async def test_detection_list_is_cached_until_invalidated(probes: FakeProbes) -> None:
    probes.ports = [FakePort("/dev/ttyACM0", product="CubeOrange")]
    probes.mavlink = {"/dev/ttyACM0": 140}
    assert len(await detect()) == 1
    probes.ports = []
    assert len(await Detector.detect_serial_flight_controllers(())) == 1
    Detector.invalidate_caches()
    assert not await Detector.detect_serial_flight_controllers(())


def test_manual_board_is_not_serial() -> None:
    manual = Detector.detect_manual()
    assert manual.platform == Platform(name="Manual", platform_type=PlatformType.Manual)
    assert manual.path is None
    assert manual.ardupilot_board_id is None


def test_plausible_autopilot_by_legacy_identifiers() -> None:
    assert is_plausible_autopilot(FakePort("/dev/ttyACM0", product="Pixhawk4", vid=0x1234))
    assert is_plausible_autopilot(FakePort("/dev/ttyACM0", manufacturer="Hex/ProfiCNC", vid=0x1234))
    assert not is_plausible_autopilot(FakePort("/dev/ttyACM0", product="Other", vid=0x1234))


@pytest.mark.parametrize(
    "product, platform",
    [
        ("MatekH743", "MatekH743"),
        ("MatekH743-BL", "MatekH743"),
        ("CubeOrange BL", "CubeOrange"),
        ("CubeOrangePlus", "CubeOrangePlus"),
        ("CubeOrange+", "CubeOrangePlus"),
        ("CubeOrange+-BL", "CubeOrangePlus"),
        ("CubeRed", "CubeRedPrimary"),
        ("MatekH743-BL-v10", "MatekH743"),
        ("MatekH743-Secure-BL-v10", "MatekH743"),
        ("CubeOrange-Secure-BL", "CubeOrange"),
        ("PX4 FMU v5.x", "Pixhawk4"),
        ("PX4 BL FMU v6X.x", "Pixhawk6X"),
        ("PX4 FMU v6C.x", "Pixhawk6C"),
        ("PX4 FMU v3.x", "Pixhawk1"),
        (None, "GenericSerial"),
        ("", "GenericSerial"),
    ],
)
def test_serial_platform_name(product: Optional[str], platform: str) -> None:
    assert serial_platform_name(product) == platform
