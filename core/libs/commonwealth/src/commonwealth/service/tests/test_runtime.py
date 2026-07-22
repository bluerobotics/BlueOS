import asyncio
import time
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import commonwealth.service.runtime as gr
import pytest
from commonwealth.service.runtime import Runtime
from commonwealth.service.service import Service, ServiceState
from fastapi import APIRouter


class _State(ServiceState):
    pass


def _svc(name: str, port: int) -> Service[_State]:
    return Service.builder(name).state(_State()).routes(lambda _s: APIRouter()).http(port).build()


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gr, "_RESTART_BACKOFF_START_S", 0.01)
    monkeypatch.setattr(gr, "_RESTART_BACKOFF_MAX_S", 0.02)
    monkeypatch.setattr(gr, "_RESTART_BACKOFF_RESET_AFTER_S", 3600.0)


@pytest.fixture(autouse=True)
def _fake_zenoh(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    session.when_ready = MagicMock()
    session.close = MagicMock()
    monkeypatch.setattr(gr, "ZenohSession", MagicMock(return_value=session))


@pytest.mark.asyncio
async def test_crashed_service_restarts_without_stopping_sibling() -> None:
    runtime = Runtime().add_service(_svc("beacon", 9100)).add_service(_svc("stable", 9101))

    starts: dict[str, int] = {"beacon": 0, "stable": 0}
    stable_running = asyncio.Event()
    beacon_restarted = asyncio.Event()

    async def fake_run(service: Service[Any], _host: str) -> Any:
        starts[service.name] += 1
        if service.name == "stable":
            stable_running.set()
            await asyncio.Event().wait()  # run forever until cancelled
        if starts["beacon"] == 1:
            raise RuntimeError("beacon exploded")
        beacon_restarted.set()
        await asyncio.Event().wait()

    with patch.object(runtime, "_run_service_http", side_effect=fake_run):
        task = asyncio.create_task(runtime._serve("127.0.0.1"))
        await asyncio.wait_for(stable_running.wait(), timeout=2)
        await asyncio.wait_for(beacon_restarted.wait(), timeout=2)
        assert starts["beacon"] >= 2
        assert starts["stable"] == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_service_clean_exit_does_not_restart() -> None:
    runtime = Runtime().add_service(_svc("oneshot", 9102))
    starts = 0

    async def fake_run(_service: Service[Any], _host: str) -> Any:
        nonlocal starts
        starts += 1
        return SimpleNamespace(should_exit=True)

    with patch.object(runtime, "_run_service_http", side_effect=fake_run):
        await asyncio.wait_for(runtime._serve("127.0.0.1"), timeout=2)

    assert starts == 1


def test_runtime_restarts_after_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime().add_service(_svc("only", 9103))
    setups = {"n": 0}
    serve_calls = {"n": 0}

    def fake_setup() -> None:
        setups["n"] += 1

    async def fake_serve_async(_host: str) -> None:
        serve_calls["n"] += 1
        if serve_calls["n"] == 1:
            raise RuntimeError("runtime boom")

    monkeypatch.setattr(runtime, "setup", fake_setup)
    monkeypatch.setattr(runtime, "teardown", MagicMock())
    monkeypatch.setattr(runtime, "_serve", fake_serve_async)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    runtime.run("127.0.0.1")

    assert serve_calls["n"] == 2
    assert setups["n"] == 2


def test_add_service_duplicate_raises() -> None:
    runtime = Runtime().add_service(_svc("dup", 9110))
    with pytest.raises(ValueError, match="already registered"):
        runtime.add_service(_svc("dup", 9111))


def test_sentry_and_process_name(monkeypatch: pytest.MonkeyPatch) -> None:
    init = MagicMock()
    monkeypatch.setattr(gr, "init_sentry", init)
    runtime = Runtime().sentry("custom").add_service(_svc("a", 9112)).add_service(_svc("b", 9113))
    runtime.setup()
    init.assert_called_once_with("custom")
    runtime.teardown()

    single = Runtime().add_service(_svc("solo", 9114))
    with single.state() as state:
        assert single._process_name(state) == "solo"
    multi = Runtime().add_service(_svc("x", 9115)).add_service(_svc("y", 9116))
    with multi.state() as state:
        assert multi._process_name(state) == "blueos"


def test_setup_binds_zenoh_and_teardown_clears() -> None:
    runtime = Runtime().add_service(_svc("svc", 9117))
    runtime.setup()
    with runtime.state() as state:
        assert state.zenoh is not None
        zenoh = state.zenoh
        service = state.services["svc"]
    assert service.zenoh is not None

    runtime.teardown()
    cast(MagicMock, zenoh).close.assert_called_once()
    with runtime.state() as state:
        assert state.zenoh is None
        assert state.fastapi_apps == {}
        assert state.loop is None
    assert service.zenoh is None


@pytest.mark.asyncio
async def test_serve_requires_services() -> None:
    with pytest.raises(RuntimeError, match="no services registered"):
        await Runtime()._serve("127.0.0.1")


def test_build_app_has_root_and_router() -> None:
    runtime = Runtime()
    service = _svc("http", 9118)
    app = runtime._build_app(service)
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/" in paths


@pytest.mark.asyncio
async def test_run_service_http_requires_port_and_calls_on_start() -> None:
    runtime = Runtime()
    bare = Service.builder("noport").state(_State()).routes(lambda _s: APIRouter()).build()
    with pytest.raises(RuntimeError, match="no http port"):
        await runtime._run_service_http(bare, "127.0.0.1")

    started = asyncio.Event()

    async def on_start(_service: Service[Any]) -> None:
        started.set()

    service = (
        Service.builder("with-start")
        .state(_State())
        .routes(lambda _s: APIRouter())
        .http(9120)
        .on_start(on_start)
        .logging()
        .build()
    )

    async def fake_serve() -> None:
        return None

    with patch("commonwealth.service.runtime.Server") as server_cls:
        server = MagicMock()
        server.serve = fake_serve
        server.should_exit = True
        server_cls.return_value = server
        result = await runtime._run_service_http(service, "127.0.0.1")
        await asyncio.wait_for(started.wait(), timeout=1)
        assert result is server


def test_setup_enables_service_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime().add_service(
        Service.builder("logged").state(_State()).routes(lambda _s: APIRouter()).http(9121).logging().build()
    )
    setup_logging = MagicMock()
    with runtime.state() as state:
        service = state.services["logged"]
    monkeypatch.setattr(service, "setup_logging", setup_logging)
    runtime.setup()
    setup_logging.assert_called_once()
    runtime.teardown()


def test_run_keyboard_interrupt_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime().add_service(_svc("kbi", 9119))
    monkeypatch.setattr(runtime, "setup", MagicMock())
    monkeypatch.setattr(runtime, "teardown", MagicMock())

    async def boom(_host: str) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(runtime, "_serve", boom)
    runtime.run("127.0.0.1")
