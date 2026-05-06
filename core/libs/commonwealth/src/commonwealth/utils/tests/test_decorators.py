import time
from datetime import datetime

from .. import decorators

CACHE_TIME = 0.3
CACHE_WAIT_TIME = CACHE_TIME + 0.2


@decorators.temporary_cache(timeout_seconds=CACHE_TIME)
def cached_function(_entry: str) -> datetime:
    return datetime.now()


def test_nested_settings_save_load() -> None:
    inputs = ["first", "second", "third", "fourth", "fifth", "sixth"]
    original_output = {key: cached_function(key) for key in inputs}

    # Check cache faster than light, sue me Einstein
    assert all(original_output[key] == cached_function(key) for key in inputs)

    # Wait for cache to be invalid
    time.sleep(CACHE_WAIT_TIME)

    # Check if all cache values are invalid after waiting for a long time
    assert all(original_output[key] != cached_function(key) for key in inputs)


def test_temporary_cache_invalidate() -> None:
    inputs = ["first", "second", "third"]
    original_output = {key: cached_function(key) for key in inputs}

    # Cache is still warm: same call returns the same value
    assert all(original_output[key] == cached_function(key) for key in inputs)

    # Force invalidation; subsequent calls must re-execute the function
    cached_function.invalidate()  # type: ignore[attr-defined]

    assert all(original_output[key] != cached_function(key) for key in inputs)
