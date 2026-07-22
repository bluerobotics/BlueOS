from contextlib import contextmanager
from threading import Lock
from typing import Generator, Generic, TypeVar

T = TypeVar("T")


class Mutex(Generic[T]):
    def __init__(self, value: T) -> None:
        self._lock = Lock()
        self._value = value

    @contextmanager
    def lock(self) -> Generator[T, None, None]:
        with self._lock:
            yield self._value
