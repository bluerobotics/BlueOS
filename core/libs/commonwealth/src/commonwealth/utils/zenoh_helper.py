import ast
import asyncio
import inspect
import json
import re
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable

import fastapi
import zenoh
from commonwealth.utils.tree import TreeNode
from fastapi.routing import APIRoute
from loguru import logger
from starlette.responses import StreamingResponse

from .Singleton import Singleton

PARAM_REGEX = r"{[a-zA-Z0-9_:]+}"
RESPONSE_PREFIX = "response/"


def _async_to_sync(async_func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to convert an async function to a sync function.
    """

    @wraps(async_func)
    def wrapper() -> None:
        asyncio.run(async_func())

    return wrapper


class ZenohSession(metaclass=Singleton):
    session: zenoh.Session | None = None
    config: zenoh.Config
    _executor: ThreadPoolExecutor | None = None

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
    tree: TreeNode

    def __init__(self, service_name: str):
        self.prefix = service_name
        self.zenoh_session = ZenohSession(service_name)
        self.tree = TreeNode(service_name)

    def add_queryable(self, path: str, func: Callable[..., Any]) -> None:
        def wrapper(query: zenoh.Query) -> None:
            params = dict(query.parameters)  # type: ignore

            @_async_to_sync
            async def _handle_async() -> None:
                try:
                    response = await func(**params)
                    if response is not None:
                        query.reply(query.selector.key_expr, handle_json(response))
                except Exception as e:
                    logger.exception(f"Error in zenoh query handler: {query.selector.key_expr}")
                    error_response = {
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                    query.reply(query.selector.key_expr, json.dumps(error_response))

            self.zenoh_session.submit_to_executor(_handle_async)

        if self.zenoh_session.session:
            self.zenoh_session.session.declare_queryable(path, wrapper)

    def add_subscriber(self, path: str, func: Callable[..., Any]) -> None:
        def wrapper(sample: zenoh.Sample) -> None:
            if not self._should_process(sample, path, func):
                return

            @_async_to_sync
            async def _handle_async() -> None:
                try:
                    parameters = get_parameters(sample, func)
                    result = await func(**parameters)
                    if result is not None:
                        await self.process_subscriber_response(result, sample)
                except Exception as e:
                    logger.exception(f"Error in zenoh subscriber handler on {path}: {sample.kind=}, {str(e)}")

            self.zenoh_session.submit_to_executor(_handle_async)

        if self.zenoh_session.session:
            self.zenoh_session.session.declare_subscriber(path, wrapper)

    async def process_subscriber_response(self, result: Any, sample: zenoh.Sample) -> None:
        if self.zenoh_session.session is None:
            return

        response_key = RESPONSE_PREFIX + str(sample.key_expr)
        logger.info(f"The response for {sample.key_expr} will be published to {response_key}.")

        with self.zenoh_session.session.declare_publisher(response_key) as publisher:
            if isinstance(result, StreamingResponse):
                await self._handle_streaming_response(result, publisher)
            else:
                publisher.put(handle_json(result))

    async def _handle_streaming_response(self, result: StreamingResponse, publisher: zenoh.Publisher) -> None:
        async for chunk in result.body_iterator:
            if isinstance(chunk, (dict, list)):
                chunk_data = json.dumps(chunk, default=str)
            elif isinstance(chunk, bytes):
                chunk_data = chunk.decode("utf-8", errors="replace")
            else:
                chunk_data = str(chunk)
            publisher.put(chunk_data)

    def add_routes_to_zenoh(self, app: fastapi.FastAPI) -> None:
        methods = self._get_methods(app)
        for method, path, func in methods:
            full_path = self.get_route_path(path)
            self.tree.process_path(full_path, method, func)

            if method == "GET" and not is_streaming_response(func):
                self.add_queryable(full_path, func)
            else:
                self.add_subscriber(full_path, func)

    def _get_methods(self, app: fastapi.FastAPI) -> list[tuple[str, str, Callable[..., Any]]]:
        methods = []
        for route in app.router.routes:
            if (
                isinstance(route, APIRoute)
                and type(route).__name__ == "VersionedAPIRoute"
                and "fastapi_versioning" in type(route).__module__
            ):
                method_type = next(iter(route.methods), None)
                if method_type and method_type in ("GET", "POST", "PUT", "DELETE"):
                    methods.append((method_type, clean_path(route.path), route.endpoint))
        return methods

    def get_route_path(self, path: str) -> str:
        return self.prefix + "/" + path if path else self.prefix

    def _should_process(self, sample: zenoh.Sample, endpoint: str, func: Callable[..., Any]) -> bool:
        matched = self.tree.get_match(str(sample.key_expr))

        if matched is None:
            return False

        matched_path, node = matched
        if matched_path != endpoint:
            return False

        found_method = node.get_corresponding_method(sample.kind)
        if found_method is None:
            return False
        return found_method == func


def is_streaming_response(func: Callable[..., Any]) -> bool:
    signature = inspect.signature(func)
    return_annotation = signature.return_annotation

    if return_annotation is inspect.Signature.empty:
        return False

    if inspect.isclass(return_annotation):
        return issubclass(return_annotation, StreamingResponse)

    return False


def clean_path(path: str) -> str:
    path = path.removeprefix("/").removesuffix("/")
    zenoh_path = re.sub(PARAM_REGEX, "*", path)

    return zenoh_path


def get_parameters(sample: zenoh.Sample, func: Callable[..., Any]) -> dict[str, Any]:
    source = None
    if sample.kind == zenoh.SampleKind.PUT:
        source = sample.payload
    else:
        source = sample.attachment

    if source is None:
        return {}

    parameters = parameters_process(source.to_string())
    return parameters_type_validation(parameters, func)


def parameters_process(parameters: str) -> dict[str, str]:
    if not parameters:
        return {}

    result = {}
    for parameter in parameters.split(";"):
        parameter = parameter.strip()
        if not parameter:
            continue

        if "=" not in parameter:
            logger.warning(f"Skipping malformated parameter (no '=' found): {parameter}")
            continue

        key, value = parameter.split("=", maxsplit=1)
        key, value = key.strip(), value.strip()

        if key:
            result[key] = value
    return result


def parameters_type_validation(parameters: dict[str, Any], func: Callable[..., Any]) -> dict[str, Any]:
    signature = inspect.signature(func)
    typed_parameters = {}

    for key, value in parameters.items():
        if key not in signature.parameters:
            continue

        annotation = signature.parameters[key].annotation
        try:
            if is_primitive(annotation):
                typed_parameters[key] = annotation(value)
            else:
                parsed = ast.literal_eval(value)
                typed_parameters[key] = annotation(**parsed)
        except Exception as e:
            logger.warning(f"Error converting parameter {key} to type {annotation}: {e}")
            continue

    return typed_parameters


def is_primitive(value: Any) -> bool:
    return value in (int, float, str, bool)


def handle_json(data: Any) -> str:
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing data to JSON: {data}, {e}")
        return '{"error": "Serialization failed"}'
