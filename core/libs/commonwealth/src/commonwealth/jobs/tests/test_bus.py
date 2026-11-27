"""The zenoh bus with a stub session.

The stub can't verify that zenohd delivers the samples, how zenoh-ts decodes them, or whether a client session
reconnects after zenohd restarts; those need a BlueOS install.
"""

import json
from typing import Any, List, Tuple

from commonwealth.jobs.bus import ZenohBus

NAME = "example"
TOPIC = f"service/state/{NAME}"


class FakeSession:
    def __init__(self, failing: bool = False) -> None:
        self.failing = failing
        self.puts: List[Tuple[str, Any]] = []

    def put(self, key: str, payload: str, **_options: Any) -> None:
        if self.failing:
            raise ConnectionError("the router is gone")
        self.puts.append((key, json.loads(payload)))


def test_publish_puts_the_json_and_keeps_the_value() -> None:
    session = FakeSession()
    bus = ZenohBus("service", connect=lambda: session)  # type: ignore[arg-type,return-value]
    bus.publish(NAME, {"status": "running"})
    bus.publish(NAME, None)
    assert session.puts == [(TOPIC, {"status": "running"}), (TOPIC, None)]
    assert bus.value(NAME) is None


def test_a_missing_router_keeps_the_value_and_retries_on_the_next_publish() -> None:
    session = FakeSession()
    attempts: List[int] = []

    def connect() -> FakeSession:
        attempts.append(len(attempts))
        if len(attempts) == 1:
            raise ConnectionError("no router")
        return session

    bus = ZenohBus("service", connect=connect)  # type: ignore[arg-type]
    bus.publish(NAME, 1)
    assert bus.value(NAME) == 1 and not session.puts
    bus.publish(NAME, 2)
    bus.publish(NAME, 3)
    assert session.puts == [(TOPIC, 2), (TOPIC, 3)] and len(attempts) == 2


def test_a_failing_put_never_reaches_the_kernel() -> None:
    bus = ZenohBus("service", connect=lambda: FakeSession(failing=True))  # type: ignore[arg-type,return-value]
    bus.publish(NAME, {"status": "done"})
    assert bus.value(NAME) == {"status": "done"}
