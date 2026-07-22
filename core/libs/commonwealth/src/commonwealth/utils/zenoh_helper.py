import asyncio
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import fastapi
import zenoh
from fastapi.routing import APIRoute
from loguru import logger

PARAM_REGEX = r"{[a-zA-Z0-9_]+}"


class DeferredPublisher:
    """Publisher that becomes live once the Zenoh session connects."""

    def __init__(self) -> None:
        self._publisher: zenoh.Publisher | None = None

    def _set(self, publisher: zenoh.Publisher) -> None:
        self._publisher = publisher

    def put(self, payload: Any, *args: Any, **kwargs: Any) -> None:
        if self._publisher is not None:
            self._publisher.put(payload, *args, **kwargs)

    def undeclare(self) -> None:
        if self._publisher is not None:
            self._publisher.undeclare()  # type: ignore[no-untyped-call]
            self._publisher = None


class DeferredSubscriber:
    """Subscriber that becomes live once the Zenoh session connects."""

    def __init__(self) -> None:
        self._subscriber: Any = None

    def _set(self, subscriber: Any) -> None:
        self._subscriber = subscriber

    def undeclare(self) -> None:
        if self._subscriber is not None:
            self._subscriber.undeclare()
            self._subscriber = None


class ZenohSession:
    """One Zenoh client session. Owned by a Runtime (not process-global)."""

    def __init__(self, name: str) -> None:
        self.session: zenoh.Session | None = None
        self._pending: list[Callable[[zenoh.Session], None]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.config = self._make_config(name)
        self._executor: ThreadPoolExecutor | None = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix=f"zenoh-{name}-",
        )
        threading.Thread(target=self._connect_loop, name=f"zenoh-connect-{name}", daemon=True).start()

    def when_ready(self, declare: Callable[[zenoh.Session], None]) -> None:
        with self._lock:
            if self.session is not None:
                session = self.session
            else:
                self._pending.append(declare)
                return
        declare(session)

    def _connect_loop(self) -> None:
        attempt = 0
        while not self._stop.is_set():
            try:
                session = zenoh.open(self.config)
            except Exception as e:
                attempt += 1
                if attempt == 1 or attempt % 30 == 0:
                    logger.warning(f"Zenoh not available, retrying every 1s: {e}")
                if self._stop.wait(1.0):
                    return
                continue

            with self._lock:
                self.session = session
                pending = list(self._pending)
                self._pending.clear()

            for declare in pending:
                try:
                    declare(session)
                except Exception as e:
                    logger.error(f"Failed to declare Zenoh resource after connect: {e}")

            logger.info("Zenoh session connected")
            return

    def submit_to_executor(self, func: Callable[..., Any]) -> None:
        if self._executor is None:
            logger.warning("Zenoh session executor is not available, task will not be initialized.")
            return
        try:
            self._executor.submit(func)
        except Exception as e:
            logger.error(f"Error submitting task to zenoh session executor: {e}")

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            self._pending.clear()
            session = self.session
            self.session = None
        if session:
            session.close()  # type: ignore[no-untyped-call]
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    @staticmethod
    def _make_config(name: str) -> zenoh.Config:
        configuration = {
            "mode": "client",
            "connect/endpoints": ["tcp/127.0.0.1:7447"],
            "adminspace": {"enabled": True},
            "metadata": {"name": name},
        }

        config = zenoh.Config()
        for key, value in configuration.items():
            config.insert_json5(key, json.dumps(value))
        return config


class ZenohRouter:
    prefix: str
    zenoh_session: ZenohSession

    def __init__(self, service_name: str, session: ZenohSession | None = None) -> None:
        self.prefix = service_name
        self.zenoh_session = session if session is not None else ZenohSession(service_name)

    def add_queryable(self, path: str, func: Callable[..., Any]) -> None:
        full_path = self.prefix
        if path:
            full_path += f"/{path}"

        def wrapper(query: zenoh.Query) -> None:
            params = dict(query.parameters)  # type: ignore

            async def _handle_async() -> None:
                try:
                    response = await func(**params)
                    if response is not None:
                        query.reply(query.selector.key_expr, json.dumps(response, default=str))
                except Exception as e:
                    logger.exception(f"Error in zenoh query handler: {query.selector.key_expr}")
                    error_response = {
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                    query.reply(query.selector.key_expr, json.dumps(error_response))

            def run_async() -> None:
                asyncio.run(_handle_async())

            self.zenoh_session.submit_to_executor(run_async)

        def declare(session: zenoh.Session) -> None:
            session.declare_queryable(full_path, wrapper)

        self.zenoh_session.when_ready(declare)

    def add_publisher(
        self,
        path: str,
        *,
        absolute: bool = False,
        publisher_options: dict[str, Any] | None = None,
    ) -> DeferredPublisher:
        if absolute:
            full_path = path
        else:
            full_path = self.prefix
            if path:
                full_path += f"/{path}"

        deferred = DeferredPublisher()

        def declare(session: zenoh.Session) -> None:
            deferred._set(session.declare_publisher(full_path, **(publisher_options or {})))

        self.zenoh_session.when_ready(declare)
        return deferred

    def add_subscriber(
        self,
        path: str,
        handler: Callable[[zenoh.Sample], Any],
        *,
        absolute: bool = False,
    ) -> DeferredSubscriber:
        if absolute:
            full_path = path
        else:
            full_path = self.prefix
            if path:
                full_path += f"/{path}"

        deferred = DeferredSubscriber()

        def safe_handler(sample: zenoh.Sample) -> None:
            try:
                handler(sample)
            except Exception:
                logger.exception(f"Zenoh subscriber handler failed for {full_path}")

        def declare(session: zenoh.Session) -> None:
            deferred._set(session.declare_subscriber(full_path, safe_handler))

        self.zenoh_session.when_ready(declare)
        return deferred

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


def clean_path(path: str) -> str:
    path = path.removeprefix("/").removesuffix("/")

    zenoh_path = re.sub(PARAM_REGEX, "*", path)
    zenoh_path = zenoh_path.replace("*/*", "**")

    return zenoh_path
