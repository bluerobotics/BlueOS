from abc import ABC
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generator, Generic, Self, TypeVar, Union

from commonwealth.utils.logs import ServiceLogging, service_logging_context
from commonwealth.utils.mutex import Mutex
from commonwealth.utils.zenoh_helper import ZenohRouter, ZenohSession
from fastapi import APIRouter

EventHandler = Callable[[Any], None]


@dataclass(frozen=True)
class ReadModelUpdated:
    """Event whose payload is the new read model.

    Built-in subscriber: Service._snapshot. Typical extras: settings persistence, Zenoh.
    """

    model: Any


class ServiceState(ABC):
    def __init__(self) -> None:
        self._pending_events: list[Any] = []

    def snapshot(self) -> Any | None:
        """Build the current read-model projection, or None to opt out of snapshots.

        Call publish_read_model() after a successful mutation to emit ReadModelUpdated.
        Services with huge state (e.g. bag of holding) leave the default and emit their own
        persistence events against the file store instead; reads then fall back to the write mutex.
        """
        return None

    def subscribers(self) -> list[EventHandler]:
        """Handlers owned by this write model (e.g. settings persistence on ReadModelUpdated)."""
        return []

    def emit(self, event: Any) -> None:
        """Record an event to dispatch after the write lock is released."""
        self._pending_events.append(event)

    def publish_read_model(self) -> None:
        """Emit ReadModelUpdated with snapshot() — the usual post-mutation event."""
        # Overrides return a view; the base implementation returns None (opt-out).
        view = self.snapshot()  # pylint: disable=assignment-from-none
        if view is not None:
            self.emit(ReadModelUpdated(view))

    def drain_events(self) -> list[Any]:
        events = self._pending_events
        self._pending_events = []
        return events

    def on_zenoh(self, zenoh: ZenohRouter) -> None:
        """Called once when the runtime binds this service to its Zenoh session."""


S = TypeVar("S", bound=ServiceState)


# pylint: disable-next=too-many-instance-attributes
class Service(Generic[S]):
    name: str
    logging: ServiceLogging
    zenoh: ZenohRouter | None
    http_port: int | None
    http_title: str
    http_description: str
    enable_logging: bool
    _state: Mutex[S]
    _snapshot: Any | None
    _routes: Callable[["Service[S]"], APIRouter] | None
    _zenoh_setup: Callable[["Service[S]"], None] | None
    _on_start: Callable[["Service[S]"], Awaitable[None]] | None
    _event_handlers: list[EventHandler]

    # pylint: disable-next=too-many-arguments
    def __init__(
        self,
        name: str,
        state: S,
        *,
        routes: Callable[["Service[S]"], APIRouter] | None = None,
        http_port: int | None = None,
        http_title: str | None = None,
        http_description: str = "",
        enable_logging: bool = False,
        zenoh_setup: Callable[["Service[S]"], None] | None = None,
        on_start: Callable[["Service[S]"], Awaitable[None]] | None = None,
        event_handlers: list[EventHandler] | None = None,
    ) -> None:
        self.name = name
        self.logging = ServiceLogging(name)
        self.zenoh = None
        self.http_port = http_port
        self.http_title = http_title or name
        self.http_description = http_description
        self.enable_logging = enable_logging
        self._state = Mutex(state)
        self._routes = routes
        self._zenoh_setup = zenoh_setup
        self._on_start = on_start
        # State-owned subscribers (settings, …) then builder .on_event(...) handlers.
        self._event_handlers = [*state.subscribers(), *(event_handlers or ())]
        with self._state.lock() as live:
            # Bootstrap read cache; later updates come only via ReadModelUpdated.
            self._snapshot = live.snapshot()

    @classmethod
    def builder(cls, name: str) -> "ServiceBuilderStart":
        return ServiceBuilderStart(name)

    def _dispatch(self, event: Any) -> None:
        if isinstance(event, ReadModelUpdated):
            self._snapshot = event.model
        for handler in self._event_handlers:
            handler(event)

    @contextmanager
    def write(self) -> Generator[S, None, None]:
        """Exclusive write access. On success, dispatches emitted events before unlocking.

        Dispatch stays under the lock so file-backed RMW (e.g. bag of holding) cannot interleave
        another write between emit and persist.
        """
        with service_logging_context(self.name):
            with self._state.lock() as state:
                state.drain_events()
                try:
                    yield state
                except Exception:
                    state.drain_events()
                    raise
                for event in state.drain_events():
                    self._dispatch(event)

    @contextmanager
    def read(self) -> Generator[Any, None, None]:
        """Lock-free read model when present; otherwise same mutex as write()."""
        with service_logging_context(self.name):
            snap = self._snapshot
            if snap is not None:
                yield snap
                return
            with self._state.lock() as state:
                yield state

    def router(self) -> APIRouter:
        if self._routes is None:
            raise RuntimeError(f"service '{self.name}' has no routes configured")
        return self._routes(self)

    def bind_zenoh(self, session: ZenohSession) -> None:
        """Attach this service to the runtime-owned Zenoh session."""
        with service_logging_context(self.name):
            self.zenoh = ZenohRouter(self.name, session=session)
            with self.write() as state:
                state.on_zenoh(self.zenoh)
            if self._zenoh_setup is not None:
                self._zenoh_setup(self)

    def setup_logging(self, session: ZenohSession | None = None) -> None:
        with service_logging_context(self.name):
            self.logging.setup(session)

    def teardown_logging(self) -> None:
        with service_logging_context(self.name):
            self.logging.teardown()


class ServiceBuilderStart:
    """Builder before state is set — `.state(...)` locks in the Service[S] type."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._log_level: Union[str, int] = "DEBUG"
        self._setup_logging = False

    def logging(self, level: Union[str, int] = "DEBUG") -> Self:
        self._setup_logging = True
        self._log_level = level
        return self

    def state(self, state: S) -> "ServiceBuilder[S]":
        return ServiceBuilder(
            self._name,
            state,
            log_level=self._log_level,
            setup_logging=self._setup_logging,
        )


# pylint: disable-next=too-many-instance-attributes
class ServiceBuilder(Generic[S]):
    # pylint: disable-next=too-many-arguments
    def __init__(
        self,
        name: str,
        state: S,
        *,
        log_level: Union[str, int] = "DEBUG",
        setup_logging: bool = False,
        routes: Callable[[Service[S]], APIRouter] | None = None,
        http_port: int | None = None,
        http_title: str | None = None,
        http_description: str = "",
        zenoh_setup: Callable[[Service[S]], None] | None = None,
        on_start: Callable[[Service[S]], Awaitable[None]] | None = None,
        event_handlers: list[EventHandler] | None = None,
    ) -> None:
        self._name = name
        self._state = state
        self._log_level = log_level
        self._setup_logging = setup_logging
        self._routes = routes
        self._http_port = http_port
        self._http_title = http_title
        self._http_description = http_description
        self._zenoh_setup = zenoh_setup
        self._on_start = on_start
        self._event_handlers: list[EventHandler] = list(event_handlers or ())

    def logging(self, level: Union[str, int] = "DEBUG") -> Self:
        self._setup_logging = True
        self._log_level = level
        return self

    def routes(self, factory: Callable[[Service[S]], APIRouter]) -> Self:
        self._routes = factory
        return self

    def zenoh(self, setup: Callable[[Service[S]], None]) -> Self:
        """Register pubs/subs (and other Zenoh use) once the runtime binds the session."""
        self._zenoh_setup = setup
        return self

    def on_start(self, hook: Callable[[Service[S]], Awaitable[None]]) -> Self:
        """Run once the runtime event loop is up, before serving HTTP."""
        self._on_start = hook
        return self

    def on_event(self, handler: EventHandler) -> Self:
        """Subscribe to events dispatched after successful writes (e.g. Zenoh publish)."""
        self._event_handlers.append(handler)
        return self

    def http(
        self,
        port: int,
        *,
        title: str | None = None,
        description: str = "",
    ) -> Self:
        self._http_port = port
        self._http_title = title
        self._http_description = description
        return self

    def build(self) -> Service[S]:
        service = Service(
            self._name,
            self._state,
            routes=self._routes,
            http_port=self._http_port,
            http_title=self._http_title,
            http_description=self._http_description,
            enable_logging=self._setup_logging,
            zenoh_setup=self._zenoh_setup,
            on_start=self._on_start,
            event_handlers=self._event_handlers,
        )
        service.logging.set_level(self._log_level)
        return service
