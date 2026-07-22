import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from commonwealth.utils import logs as logs_mod
from commonwealth.utils.logs import (
    InterceptHandler,
    ServiceLogging,
    create_log_sink,
    init_logger,
    service_logging_context,
    stack_trace_message,
    validate_service_name,
)


def test_validate_service_name_rejects_bad_names() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_service_name("")
    with pytest.raises(ValueError, match="forward slash"):
        validate_service_name("a/b")
    with pytest.raises(ValueError, match="extension"):
        validate_service_name("a.b")
    validate_service_name("ok")


def test_service_logging_context_sets_and_resets() -> None:
    assert logs_mod._service_logging_name.get() is None
    with service_logging_context("svc"):
        assert logs_mod._service_logging_name.get() == "svc"
    assert logs_mod._service_logging_name.get() is None


def test_service_logging_filter_and_level() -> None:
    logging_svc = ServiceLogging("svc", level="INFO")
    assert logging_svc.level == "INFO"
    logging_svc.set_level("DEBUG")
    assert logging_svc.level == "DEBUG"

    record = {
        "extra": {"service": "svc"},
        "level": SimpleNamespace(no=logging_svc._level_no),
    }
    assert logging_svc.filter(record) is True  # type: ignore[arg-type]
    record["extra"] = {"service": "other"}
    assert logging_svc.filter(record) is False  # type: ignore[arg-type]


def test_service_logging_setup_teardown(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = MagicMock()
    monkeypatch.setattr("commonwealth.utils.logs.create_log_sink", MagicMock(return_value=sink))
    add = MagicMock(return_value=42)
    remove = MagicMock()
    monkeypatch.setattr("commonwealth.utils.logs.logger.add", add)
    monkeypatch.setattr("commonwealth.utils.logs.logger.remove", remove)

    logging_svc = ServiceLogging("svc")
    logging_svc.setup(session=MagicMock())
    logging_svc.setup(session=MagicMock())  # idempotent
    add.assert_called_once()
    logging_svc.teardown()
    remove.assert_called_once_with(42)
    logging_svc.teardown()


def test_init_logger_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "commonwealth.utils.logs.ServiceLogging",
        MagicMock(side_effect=RuntimeError("nope")),
    )
    init_logger("svc")


def test_stack_trace_message_joins_causes() -> None:
    err = RuntimeError("outer")
    err.__cause__ = ValueError("inner")
    assert stack_trace_message(err) == "outer inner"


def test_intercept_handler_emits(monkeypatch: pytest.MonkeyPatch) -> None:
    log = MagicMock()
    monkeypatch.setattr("commonwealth.utils.logs.logger.opt", MagicMock(return_value=log))
    monkeypatch.setattr("commonwealth.utils.logs.logger.level", MagicMock(side_effect=ValueError))
    InterceptHandler().emit(logging.LogRecord("n", logging.INFO, __file__, 1, "hi", (), None))
    log.log.assert_called_once()


def test_create_log_sink_publishes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    publisher = MagicMock()
    router = MagicMock()
    router.add_publisher.return_value = publisher
    monkeypatch.setattr("commonwealth.utils.logs.ZenohRouter", MagicMock(return_value=router))

    sink = create_log_sink("svc", session=MagicMock())
    record = {
        "time": SimpleNamespace(timestamp=lambda: 1.5),
        "level": SimpleNamespace(name="INFO"),
        "message": "hello",
        "exception": None,
        "name": "mod",
        "file": SimpleNamespace(name="f.py"),
        "line": 10,
    }
    sink(SimpleNamespace(record=record))  # type: ignore[arg-type]
    payload = json.loads(publisher.put.call_args[0][0])
    assert payload["message"] == "hello"
    assert payload["level"] == 2

    publisher.put.side_effect = RuntimeError("down")
    sink(SimpleNamespace(record=record))  # type: ignore[arg-type]
