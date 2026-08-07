import asyncio
from typing import AsyncGenerator, List


class JobStream:
    def __init__(self) -> None:
        self._chunks: List[bytes] = []
        self._updated = asyncio.Event()
        self._done = False
        self._retries = 0

    def publish(self, chunk: bytes) -> None:
        self._chunks.append(chunk)
        self._updated.set()

    def reset(self) -> None:
        self._chunks = []
        self._retries += 1
        self._updated.set()

    def close(self) -> None:
        self._done = True
        self._updated.set()

    async def subscribe(self) -> AsyncGenerator[bytes, None]:
        index = 0
        retries = self._retries
        while True:
            self._updated.clear()
            if retries != self._retries:
                retries = self._retries
                index = 0
            while index < len(self._chunks):
                yield self._chunks[index]
                index += 1
            if self._done:
                return
            await self._updated.wait()
