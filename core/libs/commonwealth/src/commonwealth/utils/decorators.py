import asyncio
import time
from functools import wraps
from threading import Lock
from typing import TypeVar
from typing import Any, Callable, Dict

F = TypeVar("F", bound=Callable[..., Any])


def temporary_cache(timeout_seconds: float = 10) -> Callable[[F], F]:
    """Decorator that creates a cache for specific inputs with a configured timeout in seconds.

    Supports both synchronous and asynchronous functions.

    Args:
        timeout_seconds (float, optional): Timeout to be used for cache invalidation. Defaults to 10.

    Returns:
        Any: Return of the decorated function
    """
    cache: Dict[Any, Any] = {}
    last_sample_time: Dict[Any, float] = {}

    def inner_function(function: F) -> F:
        def is_cache_valid(args: Any) -> bool:
            current_time = time.time()
            return args in last_sample_time and current_time - last_sample_time[args] < timeout_seconds

        # Check if the function is async
        if asyncio.iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(*args: Any) -> Any:
                # The cache is still valid and we can return the value if exists
                if is_cache_valid(args) and args in cache:
                    return cache[args]

                # The cache is invalid or argument does not exist in cache, update it!
                last_sample_time[args] = time.time()
                function_return = await function(*args)
                cache[args] = function_return
                return function_return

            return async_wrapper  # type: ignore

        @wraps(function)
        def sync_wrapper(*args: Any) -> Any:
            # The cache is still valid and we can return the value if exists
            if is_cache_valid(args) and args in cache:
                return cache[args]

            # The cache is invalid or argument does not exist in cache, update it!
            last_sample_time[args] = time.time()
            function_return = function(*args)
            cache[args] = function_return
            return function_return

        return sync_wrapper  # type: ignore

    return inner_function


def single_threaded(callback: Callable[[Any], Any]) -> Callable[[Callable[[Any], Any]], Any]:
    """
    Decorator to ensure that a function cannot be called in parallel. If the function is
    already running, the decorator calls the provided callback function if any and returns its return value.

    Args:
        callback (Callable[[Any], Any]): Callback to be called when the operation is already in progress.

    Returns:
        A decorator that wraps the original function.
    """

    def inner_function(function: Callable[[Any], Any]) -> Callable[[Callable[[Any], Any]], Any]:
        lock = Lock()

        @wraps(function)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal lock
            # pylint: disable=consider-using-with
            if not lock.acquire(blocking=False):
                return await callback(*args, **kwargs)
            try:
                return await function(*args, **kwargs)
            finally:
                lock.release()

        return wrapper

    return inner_function
