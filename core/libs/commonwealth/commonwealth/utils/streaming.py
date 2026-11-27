import asyncio
import base64
import json
from contextlib import aclosing
from dataclasses import asdict, dataclass
from typing import AsyncGenerator, Optional, Tuple, TypeVar

from fastapi import status

from commonwealth.utils.apis import StackedHTTPException

T = TypeVar("T")


@dataclass
class StreamingResponse:
    fragment: int
    status: int
    data: Optional[str] = None
    error: Optional[str] = None


def response_line(response: StreamingResponse) -> str:
    return json.dumps(asdict(response)) + "|\n\n|"


def streaming_timeout_exception(fragment: int) -> str:
    return response_line(
        StreamingResponse(fragment=fragment, data=None, status=status.HTTP_408_REQUEST_TIMEOUT, error="Timeout reached")
    )


def streaming_error_exception(fragment: int, error: Exception) -> str:
    return response_line(
        StreamingResponse(fragment=fragment, data=None, status=status.HTTP_500_INTERNAL_SERVER_ERROR, error=str(error))
    )


def streaming_stack_exception(fragment: int, error: StackedHTTPException) -> str:
    return response_line(StreamingResponse(fragment=fragment, data=None, status=error.status_code, error=error.detail))


def streaming_response(fragment: int, data: str | bytes) -> str:
    buffer = data.encode("utf-8") if isinstance(data, str) else data
    data_encoded = base64.b64encode(buffer).decode()
    return response_line(StreamingResponse(fragment=fragment, data=data_encoded, status=status.HTTP_200_OK))


async def streamer(gen: AsyncGenerator[str | bytes, None], heartbeats: float = -1.0) -> AsyncGenerator[str, None]:
    """
    Streamer wrapper for async generators and provide a consistent response format
    with error handling. Data is encoded in base64 to avoid any new line jsons conflicts.
    """

    async def send_heartbeat(period: float, queue: asyncio.Queue[Optional[str]]) -> None:
        while True:
            await asyncio.sleep(period)
            await queue.put(streaming_response(-1, "heartbeat"))

    queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    if heartbeats > 0:
        heartbeat_task = asyncio.create_task(send_heartbeat(heartbeats, queue))
    else:
        heartbeat_task = None

    async def generator_wrapper(gen: AsyncGenerator[str | bytes, None], queue: asyncio.Queue[Optional[str]]) -> None:
        fragment = 0
        try:
            async for data in gen:
                await queue.put(streaming_response(fragment, data))
                fragment += 1
        except StackedHTTPException as e:
            await queue.put(streaming_stack_exception(fragment, e))
        except Exception as e:
            await queue.put(streaming_error_exception(fragment, e))
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
                # so no late heartbeat can land after the end-of-stream marker
                await asyncio.gather(heartbeat_task, return_exceptions=True)
            await queue.put(None)

    asyncio.create_task(generator_wrapper(gen, queue))

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


async def _fetch_stream(
    gen: AsyncGenerator[str | bytes, None], queue: asyncio.Queue[Optional[Tuple[str | bytes | None, Exception | None]]]
) -> None:
    try:
        async for data in gen:
            await queue.put((data, None))
    except Exception as e:
        await queue.put((None, e))
    finally:
        await queue.put((None, None))


async def timeout_streamer(gen: AsyncGenerator[str | bytes, None], timeout: int = 3) -> AsyncGenerator[str, None]:
    """
    Streamer wrapper for async generators and provide a consistent response format
    with error handling with additional timeout limit for each item iteration.
    Data is encoded in base64 to avoid any new line jsons conflicts.
    """

    queue: asyncio.Queue[Optional[Tuple[str | bytes | None, Exception | None]]] = asyncio.Queue()
    task = asyncio.create_task(_fetch_stream(gen, queue))

    fragment = 0
    try:
        while True:
            item = await asyncio.wait_for(queue.get(), timeout=timeout)
            data, error = item if item else (None, None)
            if error:
                raise error
            if data is None:
                break
            yield streaming_response(fragment, data)
            fragment += 1
    except asyncio.TimeoutError:
        yield streaming_timeout_exception(fragment)
    except StackedHTTPException as e:
        yield streaming_stack_exception(fragment, e)
    except Exception as e:
        yield streaming_error_exception(fragment, e)
    finally:
        task.cancel()


async def idle_timeout(gen: AsyncGenerator[T, None], timeout: float) -> AsyncGenerator[T, None]:
    """
    Re-yield the items of an async generator, raising TimeoutError if it produces nothing for `timeout` seconds.
    """
    async with aclosing(gen) as closing_gen:
        iterator = aiter(closing_gen)
        while True:
            try:
                # wait_for can drop an item that lands exactly at the timeout, harmless for pull streams
                item = await asyncio.wait_for(anext(iterator), timeout)
            except StopAsyncIteration:
                return
            except asyncio.TimeoutError as error:
                raise TimeoutError(f"No progress for {timeout:.0f} s") from error
            yield item
