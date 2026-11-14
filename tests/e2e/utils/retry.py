import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def wait_until(
    action: Callable[[], T],
    timeout: float,
    interval: float = 3,
    errors: tuple[type[Exception], ...] = (Exception,),
    description: str = "condition",
) -> T:
    """Calls action until it returns without raising one of errors, raises TimeoutError otherwise"""
    deadline = time.monotonic() + timeout
    error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return action()
        except errors as exception:
            error = exception
        time.sleep(interval)
    raise TimeoutError(f"{description} not met after {timeout}s, last error: {error}")
