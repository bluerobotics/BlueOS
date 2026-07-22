import copy
import json
from dataclasses import dataclass
from typing import Any, Dict, Protocol

import dpath
from commonwealth.service.service import EventHandler, ServiceState
from loguru import logger


class KvStore(Protocol):
    def read(self) -> Any:
        ...

    def write(self, data: Dict[str, Any]) -> None:
        ...


@dataclass(frozen=True)
class BagUpdated:
    """New file contents after a mutation — Database.write is the subscriber."""

    data: Dict[str, Any]


class BagOfHoldingState(ServiceState):
    """File is the only memory. Mutations read → transform → emit; DB writer persists."""

    def __init__(self, store: KvStore) -> None:
        super().__init__()
        self._store = store

    def subscribers(self) -> list[EventHandler]:
        return [self._persist]

    def _persist(self, event: Any) -> None:
        if isinstance(event, BagUpdated):
            self._store.write(event.data)

    def _current_data(self) -> Any:
        """Store, or the latest pending BagUpdated in this write() (RMW chaining)."""
        for event in reversed(self._pending_events):
            if isinstance(event, BagUpdated):
                return copy.deepcopy(event.data)
        return self._store.read()

    def get(self, path: str) -> Any:
        logger.debug(f"Get path: {path}")
        current_data = self._current_data()

        if path == "*":
            return current_data

        return dpath.get(current_data, path)  # note: raises KeyError

    def set(self, path: str, value: Any) -> None:
        logger.debug(f"Write path: {path}, {json.dumps(value)}")
        current_data = self._current_data()
        dpath.new(current_data, path, value)
        self.emit(BagUpdated(current_data))

    def overwrite(self, payload: Dict[str, Any]) -> None:
        logger.debug(f"Overwrite: {json.dumps(payload)}")
        self.emit(BagUpdated(copy.deepcopy(payload)))
