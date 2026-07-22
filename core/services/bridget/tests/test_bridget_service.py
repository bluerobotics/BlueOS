from typing import Any, Callable, List, Tuple, cast

import pytest
from bridges.serialhelper import Baudrate
from commands import AddBridge, RemoveBridge
from commonwealth.service.service import EventHandler, ReadModelUpdated, Service
from routes import build_bridget_router
from schemas import BridgeRequest
from service import BridgeIdentity, BridgetState
from views import BridgeSummary, BridgesView


def _cmd(
    serial: str = "/dev/ttyUSB0",
    baud: int = 115200,
    ip: str = "192.168.2.1",
    target: int = 14550,
    listen: int = 14551,
) -> AddBridge:
    return AddBridge(
        serial_path=serial,
        baud=baud,
        ip=ip,
        udp_target_port=target,
        udp_listen_port=listen,
    )


def _remove(cmd: AddBridge) -> RemoveBridge:
    return RemoveBridge(
        serial_path=cmd.serial_path,
        baud=cmd.baud,
        ip=cmd.ip,
        udp_target_port=cmd.udp_target_port,
        udp_listen_port=cmd.udp_listen_port,
    )


class _FakeBridge:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _FakeRuntime:
    def __init__(self, fail_serial: str | None = None) -> None:
        self.fail_serial = fail_serial
        self.opened: List[Tuple[str, int, str, int, int]] = []
        self.bridges: List[_FakeBridge] = []

    # pylint: disable-next=too-many-arguments
    def open(
        self,
        serial_path: str,
        baud: int,
        ip: str,
        udp_target_port: int,
        udp_listen_port: int,
    ) -> _FakeBridge:
        if serial_path == self.fail_serial:
            raise OSError(f"open failed for {serial_path}")
        args = (serial_path, baud, ip, udp_target_port, udp_listen_port)
        self.opened.append(args)
        bridge = _FakeBridge()
        self.bridges.append(bridge)
        return bridge


class _MemSettings:
    def __init__(self, initial: List[AddBridge] | None = None) -> None:
        self._initial = list(initial or [])
        self.saves: List[BridgesView] = []

    def load(self) -> List[AddBridge]:
        return list(self._initial)

    def save(self, view: BridgesView) -> None:
        self.saves.append(view)


class _FakeCatalog:
    def __init__(self, ports: List[str]) -> None:
        self._ports = ports

    def list_ports(self) -> List[str]:
        return list(self._ports)


def _service(
    runtime: _FakeRuntime | None = None,
    settings: _MemSettings | None = None,
    *,
    handlers: list[EventHandler] | None = None,
) -> tuple[Service[BridgetState], _FakeRuntime, _MemSettings]:
    runtime = runtime or _FakeRuntime()
    settings = settings or _MemSettings()
    state = BridgetState(runtime, settings)
    service = Service("bridget-test", state, event_handlers=handlers)
    return service, runtime, settings


def test_apply_add_opens_runtime_and_updates_read_model() -> None:
    seen: list[object] = []
    service, runtime, settings = _service(handlers=[seen.append])
    cmd = _cmd()

    with service.write() as state:
        state.apply_add(cmd)

    assert runtime.opened == [(cmd.serial_path, cmd.baud, cmd.ip, cmd.udp_target_port, cmd.udp_listen_port)]
    assert len(settings.saves) == 1
    assert settings.saves[0].bridges == (
        BridgeSummary(
            serial_path=cmd.serial_path,
            baud=cmd.baud,
            ip=cmd.ip,
            udp_target_port=cmd.udp_target_port,
            udp_listen_port=cmd.udp_listen_port,
        ),
    )
    assert len(seen) == 1
    assert isinstance(seen[0], ReadModelUpdated)
    with service.read() as view:
        assert view.bridges == settings.saves[0].bridges


def test_duplicate_add_raises_without_second_open() -> None:
    service, runtime, settings = _service()
    cmd = _cmd()

    with service.write() as state:
        state.apply_add(cmd)
    with pytest.raises(RuntimeError, match="already exist"):
        with service.write() as state:
            state.apply_add(cmd)

    assert len(runtime.opened) == 1
    assert len(settings.saves) == 1


def test_apply_remove_stops_bridge_and_persists() -> None:
    service, runtime, settings = _service()
    cmd = _cmd()

    with service.write() as state:
        state.apply_add(cmd)
    bridge = runtime.bridges[0]
    with service.write() as state:
        state.apply_remove(_remove(cmd))

    assert bridge.stopped is True
    assert settings.saves[-1].bridges == ()
    with service.read() as view:
        assert view.bridges == ()


def test_remove_missing_raises() -> None:
    service, _, settings = _service()
    with pytest.raises(RuntimeError, match="doesn't exist"):
        with service.write() as state:
            state.apply_remove(_remove(_cmd()))
    assert not settings.saves


def test_restore_from_settings_opens_without_save() -> None:
    cmd = _cmd()
    runtime = _FakeRuntime()
    settings = _MemSettings([cmd])
    state = BridgetState(runtime, settings)

    assert runtime.opened == [(cmd.serial_path, cmd.baud, cmd.ip, cmd.udp_target_port, cmd.udp_listen_port)]
    assert not settings.saves

    service = Service("bridget-test", state)
    assert not settings.saves
    with service.read() as view:
        assert len(view.bridges) == 1
        assert view.bridges[0].serial_path == cmd.serial_path


def test_restore_skips_failed_open_and_keeps_others() -> None:
    good = _cmd("/dev/ttyUSB0")
    bad = _cmd("/dev/ttyBAD")
    runtime = _FakeRuntime(fail_serial=bad.serial_path)
    settings = _MemSettings([bad, good])
    state = BridgetState(runtime, settings)

    assert runtime.opened == [(good.serial_path, good.baud, good.ip, good.udp_target_port, good.udp_listen_port)]
    assert not settings.saves
    service = Service("bridget-test", state)
    with service.read() as view:
        assert [b.serial_path for b in view.bridges] == [good.serial_path]


def test_emit_false_mutates_without_persist_or_snapshot() -> None:
    service, runtime, settings = _service()
    cmd = _cmd()

    with service.write() as state:
        state.apply_add(cmd, emit=False)

    assert len(runtime.opened) == 1
    assert not settings.saves
    with service.read() as view:
        assert view.bridges == ()


def test_stop_closes_all_without_persist() -> None:
    service, runtime, settings = _service()
    cmds = [_cmd("/dev/ttyUSB0"), _cmd("/dev/ttyUSB1")]

    with service.write() as state:
        for cmd in cmds:
            state.apply_add(cmd)
    saves_after_add = len(settings.saves)
    bridges = list(runtime.bridges)

    with service.write() as state:
        state.stop()

    assert all(b.stopped for b in bridges)
    assert len(settings.saves) == saves_after_add
    with service.write() as state:
        assert state.snapshot().bridges == ()


def test_identity_any_address_string_and_hash() -> None:
    any_addr = BridgeIdentity.from_command(_cmd(ip="0.0.0.0", listen=9000))
    targeted = BridgeIdentity.from_command(_cmd(ip="10.0.0.1", target=1, listen=9000))
    assert str(any_addr) == "/dev/ttyUSB0:115200//0.0.0.0:9000"
    assert str(targeted) == "/dev/ttyUSB0:115200//10.0.0.1:1:9000"
    assert hash(any_addr) == hash(str(any_addr))
    same = BridgeIdentity.from_command(_cmd(ip="0.0.0.0", listen=9000))
    assert {any_addr, same} == {any_addr}


def test_routes_serial_ports_and_bridge_crud() -> None:
    service, runtime, settings = _service()
    catalog = _FakeCatalog(["/dev/ttyUSB0", "/dev/ttyACM0"])
    router = build_bridget_router(service, catalog)

    def endpoint(path: str, method: str) -> Callable[..., Any]:
        for route in router.routes:
            if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
                return cast(Callable[..., Any], getattr(route, "endpoint"))
        raise KeyError(f"{method} {path}")

    assert endpoint("/serial_ports", "GET")() == ["/dev/ttyUSB0", "/dev/ttyACM0"]
    assert not endpoint("/bridges", "GET")()

    body = BridgeRequest(
        serial_path="/dev/ttyUSB0",
        baud=Baudrate.b115200,
        ip="192.168.2.1",
        udp_target_port=14550,
        udp_listen_port=14551,
    )
    endpoint("/bridges", "POST")(body)
    assert len(runtime.opened) == 1
    assert len(settings.saves) == 1
    bridges = endpoint("/bridges", "GET")()
    assert len(bridges) == 1
    assert bridges[0].serial_path == "/dev/ttyUSB0"
    assert bridges[0].baud == 115200

    endpoint("/bridges", "DELETE")(body)
    assert runtime.bridges[0].stopped is True
    assert not endpoint("/bridges", "GET")()
    assert settings.saves[-1].bridges == ()


def test_bridge_request_maps_baud_enum_to_int_commands() -> None:
    body = BridgeRequest(
        serial_path="/dev/ttyUSB0",
        baud=Baudrate.b57600,
        ip="0.0.0.0",
        udp_target_port=1,
        udp_listen_port=2,
    )
    assert body.to_add() == AddBridge("/dev/ttyUSB0", 57600, "0.0.0.0", 1, 2)
    assert body.to_remove() == RemoveBridge("/dev/ttyUSB0", 57600, "0.0.0.0", 1, 2)


def test_live_open_failure_leaves_no_bridge_and_does_not_persist() -> None:
    runtime = _FakeRuntime(fail_serial="/dev/ttyFAIL")
    service, _, settings = _service(runtime=runtime)
    cmd = _cmd("/dev/ttyFAIL")

    with pytest.raises(OSError, match="open failed"):
        with service.write() as state:
            state.apply_add(cmd)

    assert not runtime.opened
    assert not runtime.bridges
    assert not settings.saves
    with service.read() as view:
        assert view.bridges == ()


def test_any_address_str_omits_target_but_map_keeps_full_identity() -> None:
    """__str__/__hash__ drop udp_target_port for 0.0.0.0; dict keys still use all fields."""
    service, runtime, settings = _service()
    first = _cmd(ip="0.0.0.0", target=1, listen=9000)
    second = _cmd(ip="0.0.0.0", target=2, listen=9000)
    assert str(BridgeIdentity.from_command(first)) == str(BridgeIdentity.from_command(second))

    with service.write() as state:
        state.apply_add(first)
        state.apply_add(second)

    assert len(runtime.opened) == 2
    with service.read() as view:
        assert {b.udp_target_port for b in view.bridges} == {1, 2}
    assert len(settings.saves[-1].bridges) == 2


def test_same_serial_different_baud_are_distinct_bridges() -> None:
    service, runtime, settings = _service()
    a = _cmd(baud=115200)
    b = _cmd(baud=57600)

    with service.write() as state:
        state.apply_add(a)
        state.apply_add(b)

    assert len(runtime.opened) == 2
    with service.read() as view:
        assert {bridge.baud for bridge in view.bridges} == {115200, 57600}
    assert len(settings.saves[-1].bridges) == 2


def test_restore_duplicate_settings_keeps_one_bridge() -> None:
    cmd = _cmd()
    runtime = _FakeRuntime()
    settings = _MemSettings([cmd, cmd])
    state = BridgetState(runtime, settings)

    assert len(runtime.opened) == 1
    assert not settings.saves
    service = Service("bridget-test", state)
    with service.read() as view:
        assert len(view.bridges) == 1


def test_write_exception_after_add_keeps_live_bridge_without_persist() -> None:
    """IO under write runs before event dispatch; a later raise drops the save."""
    service, runtime, settings = _service()
    cmd = _cmd()

    with pytest.raises(RuntimeError, match="boom"):
        with service.write() as state:
            state.apply_add(cmd)
            raise RuntimeError("boom")

    assert len(runtime.opened) == 1
    assert not settings.saves
    with service.read() as view:
        assert view.bridges == ()
    with service.write() as state:
        assert len(state.snapshot().bridges) == 1


def test_settings_save_failure_leaves_live_bridge() -> None:
    class _ExplodingSettings(_MemSettings):
        def save(self, view: BridgesView) -> None:
            raise OSError("disk full")

    service, runtime, settings = _service(settings=_ExplodingSettings())
    cmd = _cmd()

    with pytest.raises(OSError, match="disk full"):
        with service.write() as state:
            state.apply_add(cmd)

    # Snapshot updates before subscribers; persist fails after the live mutate.
    assert len(runtime.opened) == 1
    assert not settings.saves
    with service.read() as view:
        assert len(view.bridges) == 1
