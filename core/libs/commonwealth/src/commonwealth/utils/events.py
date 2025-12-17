"""Publish structured Foxglove events for Python services."""

from __future__ import annotations

import asyncio
import atexit
import json
import sys
import time
import traceback
from typing import Any, Dict, Optional

import zenoh
from loguru import logger

from commonwealth.utils.process import get_process_name
from commonwealth.utils.zenoh_helper import ZenohSession

FOXGLOVE_ENCODING = zenoh.Encoding.APPLICATION_JSON.with_schema("foxglove.Log")
FOXGLOVE_INFO_LEVEL = 2


class EventPublisher:
    """Publisher for service lifecycle events following the Foxglove log schema."""

    def __init__(self) -> None:
        self._zenoh_session: Optional[ZenohSession] = None
        self._service_name: Optional[str] = None
        self._process_name: str = ""
        self._topic: str = ""
        self._initialized: bool = False
        self._stop_emitted: bool = False
        self._atexit_registered: bool = False
        self._excepthook_installed: bool = False
        self._previous_excepthook = None
        self._asyncio_handler_installed: bool = False
        self._previous_asyncio_handler = None

    def initialize(self, service_name: str) -> None:
        """Initialize the event publisher with the current service name."""
        if self._initialized:
            if service_name and service_name != self._service_name:
                raise RuntimeError(
                    f"Event publisher already initialized for '{self._service_name}',"
                    f" cannot reinitialize with '{service_name}'."
                )
            return
        if not service_name:
            raise ValueError("Service name cannot be empty when initializing event publisher.")
        self._service_name = service_name
        self._process_name = get_process_name()
        self._zenoh_session = ZenohSession(service_name)
        self._topic = f"services/{service_name}/event"
        self._initialized = True
        self._register_exit_handlers()

    @staticmethod
    def _foxglove_timestamp() -> Dict[str, int]:
        total_ns = time.time_ns()
        return {"sec": total_ns // 1_000_000_000, "nsec": total_ns % 1_000_000_000}

    def _serialize_event_message(self, event_type: str, payload: Dict[str, Any]) -> str:
        body = {"type": event_type, "payload": payload}
        try:
            return json.dumps(body, default=str)
        except TypeError as exc:
            logger.warning(f"Failed to serialize payload for {event_type} event: {exc}")
            safe_payload = {key: str(value) for key, value in payload.items()}
            return json.dumps({"type": event_type, "payload": safe_payload})

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self._initialized or self._zenoh_session is None:
            raise RuntimeError("EventPublisher not initialized. Call events.initialize() before publishing.")

        session = self._zenoh_session.session
        if session is None:
            logger.debug("Zenoh session unavailable while publishing event, skipping.")
            return

        foxglove_log = {
            "timestamp": self._foxglove_timestamp(),
            "level": FOXGLOVE_INFO_LEVEL,
            "message": self._serialize_event_message(event_type, payload),
            "name": self._zenoh_session.format_source_name(self._process_name),
            "file": "",
            "line": 0,
        }

        try:
            session.put(
                self._topic,
                json.dumps(foxglove_log),
                encoding=FOXGLOVE_ENCODING,
            )
            logger.debug(f"Published {event_type} event to {self._topic}")
        except Exception as exc:
            logger.error(f"Failed to publish {event_type} event: {exc}")

    def publish(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """Publish a generic event with a custom payload."""
        self._publish_event(event_type, payload or {})

    def publish_start(self, additional_payload: Optional[Dict[str, Any]] = None) -> None:
        payload = self._timestamp_payload(additional_payload)
        self._publish_event("start", payload)

    def publish_settings(self, settings: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
        payload = self._timestamp_payload({"settings": settings})
        if metadata:
            payload["metadata"] = metadata
        self._publish_event("settings", payload)

    def publish_running(self, additional_payload: Optional[Dict[str, Any]] = None) -> None:
        payload = self._timestamp_payload(additional_payload)
        self._publish_event("running", payload)
        # Emit an initial healthy status when the service is running.
        self.publish_health("ready")

    def publish_health(self, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        payload = self._timestamp_payload({"status": status})
        if details:
            payload["details"] = details
        self._publish_event("health", payload)

    def publish_error(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        payload = self._timestamp_payload({"message": message})
        if details:
            payload["details"] = details
        self._publish_event("error", payload)

    def publish_stop(self, additional_payload: Optional[Dict[str, Any]] = None) -> None:
        if self._stop_emitted:
            return
        payload = self._timestamp_payload(additional_payload)
        self._stop_emitted = True
        self._publish_event("stop", payload)

    def _timestamp_payload(self, base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"timestamp_ns": time.time_ns()}
        if base:
            payload.update(base)
        return payload

    def _register_exit_handlers(self) -> None:
        if not self._atexit_registered:
            atexit.register(self._handle_process_exit)
            self._atexit_registered = True
        if not self._excepthook_installed:
            self._previous_excepthook = sys.excepthook
            sys.excepthook = self._handle_unhandled_exception
            self._excepthook_installed = True
        if not self._asyncio_handler_installed:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                self._previous_asyncio_handler = loop.get_exception_handler()
                loop.set_exception_handler(self._handle_async_exception)
                self._asyncio_handler_installed = True

    def _handle_process_exit(self) -> None:
        try:
            self.publish_stop()
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug(f"Unable to publish stop event while shutting down: {exc}")

    def _handle_unhandled_exception(self, exc_type, exc_value, exc_traceback) -> None:  # type: ignore[no-untyped-def]
        try:
            trace = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            self.publish_error(
                "unhandled_exception",
                {
                    "exception_type": exc_type.__name__,
                    "exception_message": str(exc_value),
                    "traceback": trace,
                },
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug(f"Failed to publish error event: {exc}")
        finally:
            if self._previous_excepthook:
                self._previous_excepthook(exc_type, exc_value, exc_traceback)

    def _handle_async_exception(self, loop: asyncio.AbstractEventLoop, context: Dict[str, Any]) -> None:
        try:
            message = context.get("message", "asyncio_exception")
            exception = context.get("exception")
            details: Dict[str, Any] = {}
            if exception:
                details["exception_type"] = type(exception).__name__
                details["exception_message"] = str(exception)
                details["traceback"] = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            if "future" in context:
                details["future"] = repr(context["future"])
            self.publish_error(message, details or None)
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug(f"Failed to publish asyncio error event: {exc}")
        finally:
            if self._previous_asyncio_handler:
                self._previous_asyncio_handler(loop, context)
            else:
                loop.default_exception_handler(context)


events = EventPublisher()


def init_event_publisher(service_name: str) -> None:
    """Backward compatible wrapper for initializing events."""
    events.initialize(service_name)


def publish_start_event(additional_payload: Optional[Dict[str, Any]] = None) -> None:
    """Backward compatible wrapper to publish a service start event."""
    events.publish_start(additional_payload)


def publish_settings_event(settings: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
    """Backward compatible wrapper to publish a settings/configuration event."""
    events.publish_settings(settings, metadata)


def publish_running_event(additional_payload: Optional[Dict[str, Any]] = None) -> None:
    """Backward compatible wrapper to publish a service running event."""
    events.publish_running(additional_payload)


def publish_health_event(status: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Backward compatible wrapper to publish a health event."""
    events.publish_health(status, details)


def publish_error_event(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Backward compatible wrapper to publish an error event."""
    events.publish_error(message, details)


def publish_stop_event(additional_payload: Optional[Dict[str, Any]] = None) -> None:
    """Backward compatible wrapper to publish a stop event."""
    events.publish_stop(additional_payload)
