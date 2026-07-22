import copy
import json
from typing import Any, Callable, cast

import pytest
from commonwealth.service.service import EventHandler, Service
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from routes import build_bag_router
from service import BagOfHoldingState, BagUpdated


class _MemStore:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = copy.deepcopy(data or {})
        self.writes: list[dict[str, Any]] = []

    def read(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)

    def write(self, data: dict[str, Any]) -> None:
        self.data = copy.deepcopy(data)
        self.writes.append(copy.deepcopy(data))


def _service(
    data: dict[str, Any] | None = None,
    store: _MemStore | None = None,
    *,
    handlers: list[EventHandler] | None = None,
) -> tuple[Service[BagOfHoldingState], _MemStore]:
    store = store or _MemStore(data)
    return Service("bag", BagOfHoldingState(store), event_handlers=handlers), store


def _endpoint(router: Any, path: str, method: str) -> Callable[..., Any]:
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return cast(Callable[..., Any], getattr(route, "endpoint"))
    raise KeyError(f"{method} {path}")


def test_db_writer_subscribes_to_bag_updated() -> None:
    service, store = _service({"a": 1})

    with service.write() as state:
        state.set("b", 2)

    assert store.writes == [{"a": 1, "b": 2}]
    with service.read() as state:
        assert state.get("*") == {"a": 1, "b": 2}


def test_overwrite_persists_via_event() -> None:
    seen: list[object] = []
    service, store = _service({"old": True}, handlers=[seen.append])

    with service.write() as state:
        state.overwrite({"fresh": 3})

    assert store.writes == [{"fresh": 3}]
    assert len(seen) == 1
    assert isinstance(seen[0], BagUpdated)
    assert seen[0].data == {"fresh": 3}


def test_get_star_and_nested_path() -> None:
    service, _ = _service({"a": {"b": 1}, "c": 2})

    with service.read() as state:
        assert state.get("*") == {"a": {"b": 1}, "c": 2}
        assert state.get("a/b") == 1
        assert state.get("c") == 2


def test_get_missing_path_raises() -> None:
    service, _ = _service({"a": 1})
    with service.read() as state:
        with pytest.raises(KeyError):
            state.get("missing")


def test_set_nested_path_creates_parents() -> None:
    service, store = _service({})

    with service.write() as state:
        state.set("a/b/c", 9)

    assert store.data == {"a": {"b": {"c": 9}}}
    with service.read() as state:
        assert state.get("a/b/c") == 9


def test_multiple_sets_in_one_write_chain_rmw() -> None:
    service, store = _service({})

    with service.write() as state:
        state.set("a", 1)
        state.set("b", 2)
        assert state.get("a") == 1
        assert state.get("*") == {"a": 1, "b": 2}

    assert store.data == {"a": 1, "b": 2}
    assert store.writes[-1] == {"a": 1, "b": 2}


def test_set_then_overwrite_in_one_write() -> None:
    service, store = _service({"keep": True})

    with service.write() as state:
        state.set("a", 1)
        state.overwrite({"only": 2})

    assert store.data == {"only": 2}
    assert store.writes[-1] == {"only": 2}


def test_overwrite_deepcopies_payload() -> None:
    service, store = _service({})
    payload: dict[str, Any] = {"x": {"y": 1}}

    with service.write() as state:
        state.overwrite(payload)
    payload["x"]["y"] = 99
    payload["z"] = True

    assert store.data == {"x": {"y": 1}}


def test_write_exception_after_set_discards_persist() -> None:
    service, store = _service({"a": 1})

    with pytest.raises(RuntimeError, match="boom"):
        with service.write() as state:
            state.set("b", 2)
            raise RuntimeError("boom")

    assert store.data == {"a": 1}
    assert not store.writes
    with service.read() as state:
        assert state.get("*") == {"a": 1}


def test_persist_failure_leaves_store_unchanged() -> None:
    class _ExplodingStore(_MemStore):
        def write(self, data: dict[str, Any]) -> None:
            raise OSError("disk full")

    store = _ExplodingStore({"a": 1})
    service, _ = _service(store=store)

    with pytest.raises(OSError, match="disk full"):
        with service.write() as state:
            state.set("b", 2)

    assert store.data == {"a": 1}
    assert not store.writes


def test_consecutive_writes_see_persisted_data() -> None:
    service, store = _service({})

    with service.write() as state:
        state.set("a", 1)
    with service.write() as state:
        state.set("b", 2)

    assert store.data == {"a": 1, "b": 2}
    assert store.writes == [{"a": 1}, {"a": 1, "b": 2}]


def test_set_null_and_overwrite_empty() -> None:
    service, store = _service({"old": 1})

    with service.write() as state:
        state.set("old", None)
    assert store.data == {"old": None}

    with service.write() as state:
        state.overwrite({})
    assert store.data == {}


@pytest.mark.asyncio
async def test_routes_get_set_overwrite_and_missing_path() -> None:
    service, store = _service({})
    router = build_bag_router(service)

    def body(resp: JSONResponse) -> Any:
        return json.loads(resp.body)

    assert body(await _endpoint(router, "/get/{path:path}", "GET")("*")) == {}
    assert body(await _endpoint(router, "/set/{path:path}", "POST")("a/b", 3)) == {"status": "success"}
    assert store.data == {"a": {"b": 3}}
    assert body(await _endpoint(router, "/get/{path:path}", "GET")("a/b")) == 3

    assert body(await _endpoint(router, "/overwrite", "POST")({"fresh": True})) == {"status": "success"}
    assert store.data == {"fresh": True}

    with pytest.raises(HTTPException) as exc_info:
        await _endpoint(router, "/get/{path:path}", "GET")("nope")
    assert exc_info.value.status_code == 400
