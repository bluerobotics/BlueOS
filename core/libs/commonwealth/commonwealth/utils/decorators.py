import time
from functools import wraps
from typing import Any, Callable, Dict


def temporary_cache(timeout_seconds: float = 10) -> Callable[[Callable[[Any], Any]], Any]:
    """Decorator that creates a cache for specific inputs with a configured timeout in seconds.

    Args:
        timeout_seconds (float, optional): Timeout to be used for cache invalidation. Defaults to 10.

    Returns:
        Any: Return of the decorated function
    """
    cache: Dict[Any, Any] = {}
    last_sample_time: Dict[Any, float] = {}

    def inner_function(function: Callable[[Any], Any]) -> Any:
        @wraps(function)
        def wrapper(*args: Any) -> Any:
            nonlocal last_sample_time
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

        return wrapper

    return inner_function
