import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

import fastapi
import zenoh
from fastapi.routing import APIRoute
from loguru import logger

from .Singleton import Singleton

PARAM_REGEX = r"{[a-zA-Z0-9_]+}"


class ZenohSession(metaclass=Singleton):
    session: zenoh.Session | None = None
    config: zenoh.Config
    _executor: ThreadPoolExecutor | None = None
    _session_id: Optional[str] = None

    def __init__(self, service_name: str) -> None:
        if self.session is not None:
            return

        self.zenoh_config(service_name)
        self.session = zenoh.open(self.config)

        self._executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="zenoh-",
        )

    def submit_to_executor(self, func: Callable[..., Any]) -> None:
        if self._executor is None:
            logger.warning("Zenoh session executor is not available, task will not be initialized.")
            return
        try:
            self._executor.submit(func)
        except Exception as e:
            logger.error(f"Error submitting task to zenoh session executor: {e}")

    def close(self) -> None:
        if self.session:
            self.session.close()  # type: ignore[no-untyped-call]
            self.session = None
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    def get_session_id(self) -> Optional[str]:
        """Return the Zenoh session ID (zid) if available."""
        if self._session_id:
            return self._session_id
        if self.session is None:
            return None
        try:
            info_attr = getattr(self.session, "info", None)
            if info_attr is None:
                logger.debug("Zenoh session does not expose info attribute.")
                return None
            info = info_attr() if callable(info_attr) else info_attr
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.debug(f"Could not fetch zenoh session info: {exc}")
            return None

        session_id = self._extract_session_id(info)
        if session_id:
            self._session_id = session_id
        return session_id

    def format_source_name(self, process_name: str) -> str:
        """Compose the `<zid>/<process>` identifier requested by the logging spec."""
        session_id = self.get_session_id()
        return f"{session_id}/{process_name}" if session_id else process_name

    @staticmethod
    def _extract_session_id(info: Any) -> Optional[str]:
        if isinstance(info, dict):
            for key in ("zid", "session_id", "id"):
                value = info.get(key)
                if value:
                    return str(value)

        candidate = getattr(info, "zid", None)
        if candidate:
            try:
                candidate = candidate() if callable(candidate) else candidate
            except Exception as exc:  # pragma: no cover - best effort
                logger.debug(f"Failed to call zid accessor: {exc}")
                candidate = None
            if candidate:
                return str(candidate)

        if isinstance(info, str):
            parsed = ZenohSession._parse_session_id_string(info)
            if parsed:
                return parsed

        try:
            as_str = str(info)
        except Exception:
            as_str = None
        if as_str:
            parsed = ZenohSession._parse_session_id_string(as_str)
            if parsed:
                return parsed

        return None

    @staticmethod
    def _parse_session_id_string(data: str) -> Optional[str]:
        try:
            decoded = json.loads(data)
            if isinstance(decoded, dict):
                for key in ("zid", "session_id", "id"):
                    value = decoded.get(key)
                    if value:
                        return str(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

        match = re.search(r"(?:zid|session[_ ]?id|id)\s*[:=]\s*\"?([0-9A-Fa-fx\.\-:]+)\"?", data)
        if match:
            return match.group(1)
        return None

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

    def __init__(self, service_name: str):
        self.prefix = service_name
        self.zenoh_session = ZenohSession(service_name)

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

        if self.zenoh_session.session:
            self.zenoh_session.session.declare_queryable(full_path, wrapper)

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
