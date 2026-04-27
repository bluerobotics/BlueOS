import asyncio
import json
import re
import threading
from concurrent.futures import Future
from typing import Any, AsyncGenerator, Callable, Coroutine, Optional

import fastapi
import zenoh
from fastapi.routing import APIRoute
from loguru import logger

from .Singleton import Singleton

PARAM_REGEX = r"{[a-zA-Z0-9_]+}"
_LOOP_START_TIMEOUT_S = 5.0
_LOOP_JOIN_TIMEOUT_S = 2.0


class ZenohSession(metaclass=Singleton):
    session: zenoh.Session | None = None
    config: zenoh.Config
    _loop: asyncio.AbstractEventLoop | None = None
    _loop_thread: threading.Thread | None = None
    _loop_ready: threading.Event
    _loop_start_error: Exception | None = None

    def __init__(self, service_name: str) -> None:
        if self.session is not None:
            return

        self.zenoh_config(service_name)
        self.session = zenoh.open(self.config)

        self._loop_ready = threading.Event()
        self._loop_start_error = None
        self._loop_thread = threading.Thread(
            target=self._run_loop,
            name="zenoh-loop",
            daemon=True,
        )
        self._loop_thread.start()
        if not self._loop_ready.wait(timeout=_LOOP_START_TIMEOUT_S):
            raise RuntimeError(f"Zenoh event loop did not signal readiness within {_LOOP_START_TIMEOUT_S}s")
        if self._loop_start_error is not None:
            raise RuntimeError(
                f"Zenoh event loop failed to start: {self._loop_start_error}"
            ) from self._loop_start_error

    def _run_loop(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
        except Exception as e:
            self._loop_start_error = e
            self._loop_ready.set()
            logger.exception("Failed to initialize Zenoh event loop")
            return
        self._loop_ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
            finally:
                loop.close()

    def submit_coroutine(self, coroutine: Coroutine[Any, Any, Any]) -> Future[Any] | None:

        loop = self._loop
        if loop is None or not loop.is_running():
            logger.warning("Zenoh session loop is not available, task will not be scheduled.")
            coroutine.close()
            return None
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        except RuntimeError as e:
            logger.warning(f"Could not schedule coroutine on Zenoh loop: {e}")
            coroutine.close()
            return None

        def _log_if_failed(fut: Future[Any]) -> None:
            if fut.cancelled():
                return
            exc = fut.exception()
            if exc is not None:
                logger.opt(exception=exc).error("Unhandled error in Zenoh background task")

        future.add_done_callback(_log_if_failed)
        return future

    def close(self) -> None:
        if self.session:
            self.session.close()  # type: ignore[no-untyped-call]
            self.session = None
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=_LOOP_JOIN_TIMEOUT_S)
            if self._loop_thread.is_alive():
                logger.warning(f"Zenoh loop thread did not terminate within {_LOOP_JOIN_TIMEOUT_S}")
            self._loop_thread = None
        self._loop = None

    def zenoh_config(self, service_name: str) -> None:
        configuration = {
            "mode": "client",
            "connect/endpoints": ["tcp/127.0.0.1:7447"],
            "adminspace": {"enabled": True},
            "metadata": {"name": service_name},
        }

        config = zenoh.Config()
        for key, value in configuration.items():
            config.insert_json5(key, json.dumps(value))

        self.config = config


class ZenohRouter:
    prefix: str
    zenoh_session: ZenohSession
    _publishers: dict[str, zenoh.Publisher]

    def __init__(self, service_name: str):
        self.prefix = service_name
        self.zenoh_session = ZenohSession(service_name)
        self._publishers = {}

    def close(self) -> None:
        for publisher in self._publishers.values():
            try:
                publisher.undeclare()  # type: ignore[no-untyped-call]
            except Exception:
                logger.exception(f"Failed to undeclare publisher {publisher.key_expr}.")
        self._publishers.clear()

    def ensure_publisher(self, path: str) -> None:
        full_path = self.get_path(path)

        if self.zenoh_session.session is None:
            logger.warning(f"Zenoh session unavailable, cannot declare publisher for {full_path}")
            return

        if full_path not in self._publishers:
            self._publishers[full_path] = self.zenoh_session.session.declare_publisher(full_path)

    def get_publisher(self, path: str) -> zenoh.Publisher | None:
        full_path = self.get_path(path)
        return self._publishers.get(full_path)

    def add_queryable(self, path: str, func: Callable[..., Any]) -> None:
        full_path = self.get_path(path)

        def wrapper(query: zenoh.Query) -> None:
            params = dict(query.parameters)  # type: ignore
            key_expr = query.selector.key_expr

            async def _handle_async(q: zenoh.Query) -> None:
                with q:
                    try:
                        response = await func(**params)
                        if response is not None:
                            q.reply(key_expr, json.dumps(response, default=str))
                    except Exception as e:
                        logger.exception(f"Error in zenoh query handler: {key_expr}")
                        error_response = {
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }
                        try:
                            q.reply(key_expr, json.dumps(error_response))
                        except Exception:
                            logger.exception(f"Failed to send error reply for {key_expr}")

            if self.zenoh_session.submit_coroutine(_handle_async(query)) is None:
                query.drop()  # type: ignore[no-untyped-call]

        if self.zenoh_session.session:
            self.zenoh_session.session.declare_queryable(full_path, wrapper)

    def publish_from_generator(
        self,
        topic: str,
        generator: AsyncGenerator[str, None],
        on_complete: Optional[str] = None,
    ) -> None:
        async def _run() -> None:
            publisher = self.get_publisher(topic)
            if publisher is None:
                logger.warning(f"Publisher for {topic} not found, dropping generator")
                async for _ in generator:
                    pass
                return

            try:
                async for chunk in generator:
                    publisher.put(chunk)
            except Exception:
                logger.exception(f"Error while publishing from generator on {topic}")
            finally:
                if on_complete is not None:
                    publisher.put(on_complete)

        self.zenoh_session.submit_coroutine(_run())

    def add_routes_to_zenoh(self, app: fastapi.FastAPI) -> None:
        queryables = []
        for route in app.router.routes:
            route_type = type(route)
            if (
                isinstance(route, APIRoute)
                and route_type.__name__ == "VersionedAPIRoute"
                and "fastapi_versioning" in route_type.__module__
                and "GET" in route.methods
            ):
                queryables.append((clean_path(route.path), route.endpoint))

        for path, func in queryables:
            self.add_queryable(path, func)

    def get_path(self, path: str) -> str:
        full_path = self.prefix
        if path:
            full_path += f"/{path}"
        return full_path


def clean_path(path: str) -> str:
    path = path.removeprefix("/").removesuffix("/")

    zenoh_path = re.sub(PARAM_REGEX, "*", path)
    zenoh_path = zenoh_path.replace("*/*", "**")

    return zenoh_path
