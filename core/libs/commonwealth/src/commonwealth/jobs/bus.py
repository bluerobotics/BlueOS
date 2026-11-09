import json
from typing import Any, Callable, Dict, Optional, Protocol

import zenoh
from commonwealth.utils.zenoh_helper import ZenohSession
from loguru import logger


class Bus(Protocol):
    def publish(self, name: str, payload: Any) -> None:
        ...


def open_session(service: str) -> zenoh.Session:
    session = ZenohSession(service).session
    if session is None:
        raise ConnectionError("the zenoh session is closed")
    return session


class ZenohBus:
    """Puts every state on its zenoh key, and keeps the last values for GET, which late subscribers read first."""

    def __init__(self, service: str, connect: Optional[Callable[[], zenoh.Session]] = None) -> None:
        self.prefix = f"{service}/state/"
        self.values: Dict[str, Any] = {}
        self.connect = connect or (lambda: open_session(service))
        self.session: Optional[zenoh.Session] = None

    def topic(self, name: str) -> str:
        return f"{self.prefix}{name}"

    def publish(self, name: str, payload: Any) -> None:
        topic = self.topic(name)
        self.values[topic] = payload

        try:
            if self.session is None:
                self.session = self.connect()

            # BLOCK: a page reads the current state once, then only hears samples, so a dropped final state leaves it
            # waiting. TODO: AdvancedPublisher would recover it instead, once zenoh-ts has AdvancedSubscriber
            # (not in 1.10.2)
            self.session.put(
                topic,
                json.dumps(payload),
                encoding=zenoh.Encoding.APPLICATION_JSON,
                congestion_control=zenoh.CongestionControl.BLOCK,
            )
        except Exception as error:
            logger.warning(f"Failed to put {topic} on zenoh: {error}")

    def value(self, name: str) -> Any:
        return self.values[self.topic(name)]
