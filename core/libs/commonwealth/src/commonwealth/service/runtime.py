import asyncio
import logging
import time
from contextlib import contextmanager
from ipaddress import IPv4Address
from typing import Any, Awaitable, Callable, Generator, Self, Union

from commonwealth.service.service import Service
from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.logs import InterceptHandler, service_logging_context
from commonwealth.utils.mutex import Mutex
from commonwealth.utils.sentry_config import init_sentry
from commonwealth.utils.zenoh_helper import ZenohSession
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi_versioning import VersionedFastAPI
from loguru import logger
from uvicorn import Config, Server

_RESTART_BACKOFF_START_S = 1.0
_RESTART_BACKOFF_MAX_S = 60.0
_RESTART_BACKOFF_RESET_AFTER_S = 60.0


class RuntimeState:
    def __init__(self) -> None:
        self.services: dict[str, Service[Any]] = {}
        self.zenoh: ZenohSession | None = None
        self.fastapi_apps: dict[str, FastAPI] = {}
        self.loop: asyncio.AbstractEventLoop | None = None


class Runtime:
    """Process host: owns asyncio, FastAPI, uvicorn, and a private Zenoh session.

    Multiple Runtime instances do not share loop/zenoh/service state.
    Each service HTTP server is supervised independently; the runtime itself
    also restarts on unexpected failure.
    """

    def __init__(self) -> None:
        self._state: Mutex[RuntimeState] = Mutex(RuntimeState())
        self._setup_sentry = False
        self._sentry_name: str | None = None

    @contextmanager
    def state(self) -> Generator[RuntimeState, None, None]:
        with self._state.lock() as state:
            yield state

    def sentry(self, name: str | None = None) -> Self:
        """Enable Sentry for this runtime (once per runtime setup)."""
        self._setup_sentry = True
        self._sentry_name = name
        return self

    def add_service(self, service: Service[Any]) -> Self:
        with self.state() as state:
            if service.name in state.services:
                raise ValueError(f"service already registered: {service.name}.")

            state.services[service.name] = service
        return self

    def _process_name(self, state: RuntimeState) -> str:
        if self._sentry_name is not None:
            return self._sentry_name
        names = list(state.services)
        return names[0] if len(names) == 1 else "blueos"

    def setup(self) -> None:
        logging.basicConfig(handlers=[InterceptHandler()], level=0)

        with self.state() as state:
            if state.zenoh is None:
                state.zenoh = ZenohSession(self._process_name(state))

            for service in state.services.values():
                service.bind_zenoh(state.zenoh)
                if service.enable_logging:
                    service.setup_logging(state.zenoh)

            if self._setup_sentry:
                init_sentry(self._process_name(state))

    def teardown(self) -> None:
        with self.state() as state:
            for service in state.services.values():
                service.zenoh = None
                service.teardown_logging()
            if state.zenoh is not None:
                state.zenoh.close()
                state.zenoh = None
            state.fastapi_apps.clear()
            state.loop = None

    def _build_app(self, service: Service[Any]) -> FastAPI:
        app = FastAPI(title=service.http_title, description=service.http_description)
        app.router.route_class = GenericErrorHandlingRoute
        app.include_router(service.router())
        app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)

        @app.middleware("http")
        async def bind_service_logs(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
            with service_logging_context(service.name):
                return await call_next(request)

        @app.get("/")
        async def root() -> HTMLResponse:
            return HTMLResponse(
                f"<html><head><title>{service.http_title}</title></head></html>",
                status_code=200,
            )

        return app

    async def _run_service_http(self, service: Service[Any], host: str) -> Server:
        if service.http_port is None:
            raise RuntimeError(f"service '{service.name}' has no http port configured")

        app = self._build_app(service)
        with self.state() as state:
            state.fastapi_apps[service.name] = app

        with service_logging_context(service.name):
            logger.info(f"Starting {service.name} on {host}:{service.http_port}")

        if service._on_start is not None:
            await service._on_start(service)

        server = Server(Config(app=app, host=host, port=service.http_port, log_config=None))
        await server.serve()
        return server

    async def _supervise_service(self, service: Service[Any], host: str) -> None:
        backoff = _RESTART_BACKOFF_START_S
        while True:
            started = time.monotonic()
            try:
                server = await self._run_service_http(service, host)
                if server.should_exit:
                    with service_logging_context(service.name):
                        logger.info(f"{service.name} stopped")
                    return
                with service_logging_context(service.name):
                    logger.warning(f"{service.name} exited unexpectedly; restarting in {backoff:.0f}s")
            except Exception:
                with service_logging_context(service.name):
                    logger.exception(f"{service.name} crashed; restarting in {backoff:.0f}s")

            lived = time.monotonic() - started
            await asyncio.sleep(backoff)
            backoff = (
                _RESTART_BACKOFF_START_S
                if lived >= _RESTART_BACKOFF_RESET_AFTER_S
                else min(backoff * 2, _RESTART_BACKOFF_MAX_S)
            )

    async def _serve(self, host: str) -> None:
        with self.state() as state:
            services = list(state.services.values())

        if not services:
            raise RuntimeError("no services registered")

        tasks = [
            asyncio.create_task(self._supervise_service(service, host), name=f"svc:{service.name}")
            for service in services
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def run(self, host: Union[IPv4Address, str] = "0.0.0.0") -> None:
        """Own the asyncio loop; restart this runtime on unexpected failure."""
        host_str = str(host)
        backoff = _RESTART_BACKOFF_START_S
        while True:
            started = time.monotonic()
            try:
                with asyncio.Runner() as runner:
                    with self.state() as state:
                        state.loop = runner.get_loop()
                    try:
                        self.setup()
                        runner.run(self._serve(host_str))
                        return
                    finally:
                        self.teardown()
            except KeyboardInterrupt:
                logger.info("Runtime interrupted")
                return
            except Exception:
                logger.exception(f"Runtime crashed; restarting in {backoff:.0f}s")
                lived = time.monotonic() - started
                time.sleep(backoff)
                backoff = (
                    _RESTART_BACKOFF_START_S
                    if lived >= _RESTART_BACKOFF_RESET_AFTER_S
                    else min(backoff * 2, _RESTART_BACKOFF_MAX_S)
                )
