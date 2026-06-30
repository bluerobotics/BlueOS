import asyncio
import time
from datetime import datetime

import pytest

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


@pytest.mark.asyncio
async def test_async_cache_not_called_on_hit() -> None:
    """Test that the inner coroutine is not called again on cache hit."""
    call_count = 0

    @decorators.temporary_cache(timeout_seconds=CACHE_TIME)
    async def counting_function(_key: str) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return call_count

    # First call - should execute the function
    result1 = await counting_function("test_key")
    assert result1 == 1
    assert call_count == 1

    # Second call with same key - should return cached result WITHOUT calling function
    result2 = await counting_function("test_key")
    assert result2 == 1  # Same cached result
    assert call_count == 1  # Function was NOT called again

    # Third call - still cached
    result3 = await counting_function("test_key")
    assert result3 == 1
    assert call_count == 1


@pytest.mark.asyncio
async def test_async_cache_timeout() -> None:
    """Test that async cache expires after timeout."""
    call_count = 0

    @decorators.temporary_cache(timeout_seconds=CACHE_TIME)
    async def counting_function(_key: str) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return call_count

    # First call
    result1 = await counting_function("timeout_test")
    assert result1 == 1
    assert call_count == 1

    # Should return cached value immediately
    result2 = await counting_function("timeout_test")
    assert result2 == 1
    assert call_count == 1

    # Wait for cache to expire
    await asyncio.sleep(CACHE_WAIT_TIME)

    # Should call function again after timeout
    result3 = await counting_function("timeout_test")
    assert result3 == 2  # New result
    assert call_count == 2  # Function was called again


@pytest.mark.asyncio
async def test_async_cache_no_coroutine_reuse_error() -> None:
    """Test that async cached functions don't raise 'cannot reuse already awaited coroutine' error."""
    # This was the original bug - caching the coroutine instead of the result

    @decorators.temporary_cache(timeout_seconds=CACHE_TIME)
    async def async_function(key: str) -> str:
        await asyncio.sleep(0.01)
        return f"result_{key}"

    key = "reuse_test"

    # First call
    first_result = await async_function(key)
    assert first_result == "result_reuse_test"

    # Second call should not raise "cannot reuse already awaited coroutine"
    # It should return the cached result, not a cached coroutine
    try:
        second_result = await async_function(key)
        assert second_result == first_result
    except RuntimeError as e:
        if "cannot reuse already awaited coroutine" in str(e):
            pytest.fail("Cache is storing coroutine instead of result!")
        raise
