import time
from concurrent.futures import ThreadPoolExecutor, wait
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


def test_temporary_cache_coalesces_in_flight() -> None:
    calls = []

    @decorators.temporary_cache(timeout_seconds=1.0)
    def slow(_entry: str) -> int:
        calls.append(1)
        time.sleep(0.5)
        return len(calls)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(slow, "same") for _ in range(4)]
        wait(futures)
        results = [future.result() for future in futures]

    assert len(calls) == 1
    assert results == [1, 1, 1, 1]
