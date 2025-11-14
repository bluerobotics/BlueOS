import asyncio
import time
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def temporary_cache(timeout_seconds: float = 10) -> Callable[[F], F]:
    """Decorator that creates a cache for specific inputs with a configured timeout in seconds.

    Supports both synchronous and asynchronous functions.

    The wrapped function exposes an `invalidate()` attribute that drops every cached entry,
    forcing the next call to re-execute the function.

    Args:
        timeout_seconds (float, optional): Timeout to be used for cache invalidation. Defaults to 10.

    Returns:
        Any: Return of the decorated function
    """
    cache: Dict[Any, Any] = {}
    last_sample_time: Dict[Any, float] = {}
    # Retained for the process lifetime. Safe here because args are a small set (enums/ports).
    arg_locks: Dict[Any, Lock] = {}
    arg_locks_guard = Lock()
    async_locks: Dict[Any, asyncio.Lock] = {}

    def invalidate() -> None:
        cache.clear()
        last_sample_time.clear()

    def inner_function(function: F) -> F:
        if asyncio.iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(*args: Any) -> Any:
                # No await between lookup and insert, so this is atomic on one event loop.
                async_lock = async_locks.get(args)
                if async_lock is None:
                    async_lock = asyncio.Lock()
                    async_locks[args] = async_lock

                async with async_lock:
                    current_time = time.time()
                    cache_is_valid = args in last_sample_time and current_time - last_sample_time[args] < timeout_seconds

                    # The cache is still valid and we can return the value if exists
                    if cache_is_valid and args in cache:
                        return cache[args]

                    # The cache is invalid or argument does not exist in cache, update it!
                    last_sample_time[args] = current_time
                    function_return = await function(*args)
                    cache[args] = function_return
                    return function_return

            async_wrapper.invalidate = invalidate  # type: ignore[attr-defined]
            return async_wrapper  # type: ignore

        @wraps(function)
        def wrapper(*args: Any) -> Any:
            nonlocal last_sample_time
            with arg_locks_guard:
                arg_lock = arg_locks.setdefault(args, Lock())

            with arg_lock:
                current_time = time.time()
                cache_is_valid = args in last_sample_time and current_time - last_sample_time[args] < timeout_seconds

                # The cache is still valid and we can return the value if exists
                if cache_is_valid and args in cache:
                    return cache[args]

                # The cache is invalid or argument does not exist in cache, update it!
                last_sample_time[args] = current_time
                function_return = function(*args)
                cache[args] = function_return
                return function_return

        wrapper.invalidate = invalidate  # type: ignore[attr-defined]
        return wrapper  # type: ignore

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
