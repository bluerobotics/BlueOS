import threading
import time
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest
from commonwealth.utils.zenoh_helper import (
    DeferredPublisher,
    DeferredSubscriber,
    ZenohRouter,
    ZenohSession,
    clean_path,
)


def test_deferred_publisher_put_and_undeclare_noop_until_set() -> None:
    deferred = DeferredPublisher()
    deferred.put("payload")
    deferred.undeclare()

    publisher = MagicMock()
    deferred._set(publisher)
    deferred.put("payload", encoding="text")
    publisher.put.assert_called_once_with("payload", encoding="text")
    deferred.undeclare()
    publisher.undeclare.assert_called_once()
    assert deferred._publisher is None


def test_deferred_subscriber_undeclare() -> None:
    deferred = DeferredSubscriber()
    deferred.undeclare()
    subscriber = MagicMock()
    deferred._set(subscriber)
    deferred.undeclare()
    subscriber.undeclare.assert_called_once()
    assert deferred._subscriber is None


def test_clean_path_strips_and_collapses_params() -> None:
    assert clean_path("/v1.0/items/{item_id}/detail/") == "v1.0/items/*/detail"
    assert clean_path("/a/{x}/b/{y}") == "a/*/b/*"
    assert clean_path("/a/{x}/{y}/z") == "a/**/z"


def test_zenoh_session_when_ready_queues_then_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    live = MagicMock()
    monkeypatch.setattr("commonwealth.utils.zenoh_helper.zenoh.open", MagicMock(return_value=live))

    session = ZenohSession("unit-test")
    try:
        called: list[Any] = []

        def declare(opened: Any) -> None:
            called.append(opened)

        session.when_ready(declare)
        deadline = time.monotonic() + 2
        while not called and time.monotonic() < deadline:
            time.sleep(0.01)
        assert called == [live]

        later: list[Any] = []
        session.when_ready(later.append)
        assert later == [live]
    finally:
        session.close()
    live.close.assert_called_once()
    assert session.session is None
    assert session._executor is None


def test_zenoh_session_connect_failure_then_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "commonwealth.utils.zenoh_helper.zenoh.open",
        MagicMock(side_effect=OSError("no broker")),
    )
    session = ZenohSession("offline")
    time.sleep(0.05)
    session.close()
    assert session.session is None


def test_zenoh_session_pending_declare_error_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    live = MagicMock()
    opened = threading.Event()

    def open_after_pending(_config: Any) -> Any:
        assert opened.wait(timeout=2)
        return live

    monkeypatch.setattr("commonwealth.utils.zenoh_helper.zenoh.open", open_after_pending)
    session = ZenohSession("declare-fail")
    try:

        def boom(_opened: Any) -> None:
            raise RuntimeError("bad declare")

        session.when_ready(boom)
        opened.set()
        deadline = time.monotonic() + 2
        while session.session is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert session.session is live
    finally:
        session.close()


def test_submit_to_executor_runs_and_handles_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    live = MagicMock()
    monkeypatch.setattr("commonwealth.utils.zenoh_helper.zenoh.open", MagicMock(return_value=live))
    session = ZenohSession("exec")
    try:
        done = MagicMock()
        session.submit_to_executor(done)
        deadline = time.monotonic() + 2
        while not done.called and time.monotonic() < deadline:
            time.sleep(0.01)
        done.assert_called_once()
    finally:
        session.close()
    session.submit_to_executor(lambda: None)


def test_zenoh_router_publisher_subscriber_queryable() -> None:
    zsession = MagicMock()

    def when_ready(declare: Callable[[Any], None]) -> None:
        declare(zsession)

    session = MagicMock(when_ready=when_ready, submit_to_executor=MagicMock())
    pub, sub = MagicMock(), MagicMock()
    zsession.declare_publisher.return_value = pub
    zsession.declare_subscriber.return_value = sub

    router = ZenohRouter("svc", session=session)
    assert router.add_publisher("events")._publisher is pub
    zsession.declare_publisher.assert_called_once()
    assert router.add_publisher("services/svc/log", absolute=True)._publisher is pub

    def handler(_sample: Any) -> None:
        raise RuntimeError("handler boom")

    assert router.add_subscriber("inbox", handler)._subscriber is sub
    zsession.declare_subscriber.call_args[0][1](MagicMock())  # exception swallowed

    async def endpoint(**_params: Any) -> dict[str, str]:
        return {"ok": "1"}

    router.add_queryable("status", endpoint)
    zsession.declare_queryable.assert_called_once()
    zsession.declare_queryable.call_args[0][1](MagicMock(parameters=[], selector=MagicMock(key_expr="svc/status")))
    session.submit_to_executor.assert_called()
