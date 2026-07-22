from typing import Any, Callable, List, cast

import pytest
from commonwealth.service.service import EventHandler, ReadModelUpdated, Service
from main import _make_on_start
from nmea_injector.commands import AddSock, RemoveSock, SocketKind
from nmea_injector.routes import build_nmea_router
from nmea_injector.schemas import SockRequest
from nmea_injector.TrafficController import NMEASocket, TrafficController
from nmea_injector.views import SockSummary, SocksView


def _cmd(
    kind: SocketKind = SocketKind.UDP,
    port: int = 27000,
    component_id: int = 220,
) -> AddSock:
    return AddSock(kind=kind, port=port, component_id=component_id)


def _remove(cmd: AddSock) -> RemoveSock:
    return RemoveSock(kind=cmd.kind, port=cmd.port, component_id=cmd.component_id)


class _FakeServer:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeListener:
    def __init__(self, fail_port: int | None = None) -> None:
        self.fail_port = fail_port
        self.listens: List[tuple[SocketKind | str, int, int]] = []
        self.servers: List[_FakeServer] = []

    async def listen(self, kind: SocketKind | str, port: int, component_id: int) -> _FakeServer:
        if port == self.fail_port:
            raise OSError(f"listen failed for {port}")
        self.listens.append((kind, port, component_id))
        server = _FakeServer()
        self.servers.append(server)
        return server


class _MemSettings:
    def __init__(self, initial: List[AddSock] | None = None) -> None:
        self._initial = list(initial or [])
        self.saves: List[SocksView] = []

    def load(self) -> List[AddSock]:
        return list(self._initial)

    def save(self, view: SocksView) -> None:
        self.saves.append(view)


def _service(
    listener: _FakeListener | None = None,
    settings: _MemSettings | None = None,
    *,
    handlers: list[EventHandler] | None = None,
) -> tuple[Service[TrafficController], TrafficController, _FakeListener, _MemSettings]:
    listener = listener or _FakeListener()
    settings = settings or _MemSettings()
    controller = TrafficController(settings, listener)
    service = Service("nmea-test", controller, event_handlers=handlers)
    return service, controller, listener, settings


@pytest.mark.asyncio
async def test_apply_add_after_listen_persists_and_updates_read_model() -> None:
    seen: list[object] = []
    service, controller, listener, settings = _service(handlers=[seen.append])
    cmd = _cmd()

    server = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))
    with service.write() as state:
        state.apply_add(cmd, server)

    assert listener.listens == [(cmd.kind, cmd.port, cmd.component_id)]
    assert len(settings.saves) == 1
    assert settings.saves[0].socks == (SockSummary(kind=cmd.kind, port=cmd.port, component_id=cmd.component_id),)
    assert len(seen) == 1
    assert isinstance(seen[0], ReadModelUpdated)
    with service.read() as view:
        assert view.socks == settings.saves[0].socks


@pytest.mark.asyncio
async def test_duplicate_add_closes_orphan_server() -> None:
    service, controller, listener, settings = _service()
    cmd = _cmd()

    first = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))
    with service.write() as state:
        state.apply_add(cmd, first)
    orphan = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))
    with pytest.raises(ValueError, match="already exists"):
        with service.write() as state:
            state.apply_add(cmd, orphan)

    assert first.closed is False
    assert orphan.closed is True
    assert len(listener.listens) == 2
    assert len(settings.saves) == 1


@pytest.mark.asyncio
async def test_apply_remove_closes_and_persists() -> None:
    service, controller, _, settings = _service()
    cmd = _cmd()
    server = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))
    with service.write() as state:
        state.apply_add(cmd, server)
    with service.write() as state:
        state.apply_remove(_remove(cmd))

    assert server.closed is True
    assert settings.saves[-1].socks == ()
    with service.read() as view:
        assert view.socks == ()


@pytest.mark.asyncio
async def test_remove_missing_raises() -> None:
    service, _, _, settings = _service()
    with pytest.raises(ValueError, match="does not exist"):
        with service.write() as state:
            state.apply_remove(_remove(_cmd()))
    assert not settings.saves


@pytest.mark.asyncio
async def test_emit_false_mutates_without_persist_or_snapshot() -> None:
    service, controller, listener, settings = _service()
    cmd = _cmd()
    server = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))
    with service.write() as state:
        state.apply_add(cmd, server, emit=False)

    assert len(listener.listens) == 1
    assert not settings.saves
    with service.read() as view:
        assert view.socks == ()


@pytest.mark.asyncio
async def test_restore_pattern_opens_without_save() -> None:
    """Mirrors on_start: settings_socks → listen outside lock → apply emit=False."""
    cmd = _cmd()
    listener = _FakeListener()
    settings = _MemSettings([cmd])
    controller = TrafficController(settings, listener)
    service = Service("nmea-test", controller)

    with service.write() as state:
        pending = state.settings_socks()
    assert pending == [NMEASocket.from_command(cmd)]

    for sock in pending:
        server = cast(_FakeServer, await controller.listen(sock))
        with service.write() as state:
            state.apply_add(
                AddSock(kind=sock.kind, port=sock.port, component_id=sock.component_id),
                server,
                emit=False,
            )

    assert listener.listens == [(cmd.kind, cmd.port, cmd.component_id)]
    assert not settings.saves
    with service.read() as view:
        assert view.socks == ()
    with service.write() as state:
        assert len(state.snapshot().socks) == 1


@pytest.mark.asyncio
async def test_listen_failure_does_not_register() -> None:
    service, controller, listener, settings = _service(listener=_FakeListener(fail_port=27000))
    cmd = _cmd(port=27000)

    with pytest.raises(OSError, match="listen failed"):
        await controller.listen(NMEASocket.from_command(cmd))

    assert not listener.listens
    assert not settings.saves
    with service.read() as view:
        assert view.socks == ()


@pytest.mark.asyncio
async def test_str_ignores_component_id_but_map_keeps_full_identity() -> None:
    """__str__/__hash__ are kind:port only; dict keys still include component_id."""
    service, controller, listener, settings = _service()
    first = _cmd(component_id=220)
    second = _cmd(component_id=221)
    assert str(NMEASocket.from_command(first)) == str(NMEASocket.from_command(second))

    for cmd in (first, second):
        server = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))
        with service.write() as state:
            state.apply_add(cmd, server)

    assert len(listener.listens) == 2
    with service.read() as view:
        assert {sock.component_id for sock in view.socks} == {220, 221}
    assert len(settings.saves[-1].socks) == 2


@pytest.mark.asyncio
async def test_same_port_different_kind_are_distinct() -> None:
    service, controller, listener, settings = _service()
    udp = _cmd(kind=SocketKind.UDP, port=27000)
    tcp = _cmd(kind=SocketKind.TCP, port=27000)

    for cmd in (udp, tcp):
        server = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))
        with service.write() as state:
            state.apply_add(cmd, server)

    assert len(listener.listens) == 2
    with service.read() as view:
        assert {sock.kind for sock in view.socks} == {SocketKind.UDP, SocketKind.TCP}
    assert len(settings.saves[-1].socks) == 2


@pytest.mark.asyncio
async def test_write_exception_after_add_keeps_live_sock_without_persist() -> None:
    service, controller, _, settings = _service()
    cmd = _cmd()
    server = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))

    with pytest.raises(RuntimeError, match="boom"):
        with service.write() as state:
            state.apply_add(cmd, server)
            raise RuntimeError("boom")

    assert server.closed is False
    assert not settings.saves
    with service.read() as view:
        assert view.socks == ()
    with service.write() as state:
        assert len(state.snapshot().socks) == 1


@pytest.mark.asyncio
async def test_settings_save_failure_leaves_live_sock() -> None:
    class _ExplodingSettings(_MemSettings):
        def save(self, view: SocksView) -> None:
            raise OSError("disk full")

    service, controller, _, settings = _service(settings=_ExplodingSettings())
    cmd = _cmd()
    server = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))

    with pytest.raises(OSError, match="disk full"):
        with service.write() as state:
            state.apply_add(cmd, server)

    assert server.closed is False
    assert not settings.saves
    with service.read() as view:
        assert len(view.socks) == 1


@pytest.mark.asyncio
async def test_routes_sock_crud() -> None:
    service, controller, listener, settings = _service()
    router = build_nmea_router(service, controller)

    def endpoint(path: str, method: str) -> Callable[..., Any]:
        for route in router.routes:
            if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
                return cast(Callable[..., Any], getattr(route, "endpoint"))
        raise KeyError(f"{method} {path}")

    assert not endpoint("/socks", "GET")()

    body = SockRequest(kind=SocketKind.UDP, port=27000, component_id=220)
    await endpoint("/socks", "POST")(body)
    assert len(listener.listens) == 1
    assert len(settings.saves) == 1
    socks = endpoint("/socks", "GET")()
    assert len(socks) == 1
    assert socks[0].port == 27000

    endpoint("/socks", "DELETE")(body)
    assert listener.servers[0].closed is True
    assert not endpoint("/socks", "GET")()
    assert settings.saves[-1].socks == ()


def test_sock_request_maps_to_commands() -> None:
    body = SockRequest(kind=SocketKind.TCP, port=27001, component_id=221)
    assert body.to_add() == AddSock(SocketKind.TCP, 27001, 221)
    assert body.to_remove() == RemoveSock(SocketKind.TCP, 27001, 221)


@pytest.mark.asyncio
async def test_helper_add_remove_sock_bypass_service_write() -> None:
    _, controller, listener, settings = _service()
    sock = NMEASocket.from_command(_cmd())

    await controller.add_sock(sock)
    assert controller.get_socks() == [sock]
    assert not settings.saves
    assert len(listener.listens) == 1

    controller.remove_sock(sock)
    assert not controller.get_socks()
    assert listener.servers[0].closed is True
    assert not settings.saves


@pytest.mark.asyncio
async def test_on_start_closes_orphan_when_sock_already_present() -> None:
    cmd = _cmd()
    listener = _FakeListener()
    settings = _MemSettings([cmd])
    controller = TrafficController(settings, listener)
    service = Service("nmea-test", controller)

    existing = await controller.listen(NMEASocket.from_command(cmd))
    with service.write() as state:
        state.apply_add(cmd, existing, emit=False)

    await _make_on_start(controller)(service)

    assert len(listener.servers) == 2
    assert listener.servers[0].closed is False
    assert listener.servers[1].closed is True
    assert not settings.saves
    assert controller.get_socks() == [NMEASocket.from_command(cmd)]


@pytest.mark.asyncio
async def test_on_start_listen_failure_aborts_remaining_restores() -> None:
    """Current contract: a failed listen mid-restore stops the whole on_start loop."""
    first = _cmd(port=27000)
    second = _cmd(port=27001)
    listener = _FakeListener(fail_port=27000)
    settings = _MemSettings([first, second])
    controller = TrafficController(settings, listener)
    service = Service("nmea-test", controller)

    with pytest.raises(OSError, match="listen failed"):
        await _make_on_start(controller)(service)

    assert not listener.listens
    assert not controller.get_socks()
    assert not settings.saves


@pytest.mark.asyncio
async def test_listen_then_failed_write_before_apply_leaks_server() -> None:
    """Routes/on_start listen outside the lock; a write() failure before apply_add does not close."""
    service, controller, _, settings = _service()
    cmd = _cmd()
    server = cast(_FakeServer, await controller.listen(NMEASocket.from_command(cmd)))

    with pytest.raises(RuntimeError, match="boom"):
        with service.write():
            raise RuntimeError("boom")

    assert server.closed is False
    assert not controller.get_socks()
    assert not settings.saves


@pytest.mark.asyncio
async def test_on_start_cli_ports_persist_after_restore() -> None:
    restored = _cmd(kind=SocketKind.UDP, port=27000, component_id=220)
    listener = _FakeListener()
    settings = _MemSettings([restored])
    controller = TrafficController(settings, listener)
    service = Service("nmea-test", controller)

    await _make_on_start(controller, udp=27100, tcp=27200)(service)

    assert {(kind, port) for kind, port, _ in listener.listens} == {
        (SocketKind.UDP, 27000),
        (SocketKind.UDP, 27100),
        (SocketKind.TCP, 27200),
    }
    assert len(controller.get_socks()) == 3
    # Restore used emit=False; CLI adds publish and persist.
    assert len(settings.saves) == 2
    with service.read() as view:
        assert {sock.port for sock in view.socks} == {27000, 27100, 27200}
