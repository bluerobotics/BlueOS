from typing import Any, Optional

import aiohttp
from aiodocker import Docker


class DockerCtx:
    """
    Context manager for Docker clients.
    """

    def __init__(self, timeout: Optional[int] = None) -> None:
        if timeout is None:
            self._client: Docker = Docker()
        else:
            # aiodocker will not create a session if is different from None
            self._client: Docker = Docker(session=True)  # type: ignore
            # We insert a new session with desired timeout
            self._client.session = self._client.session = aiohttp.ClientSession(
                connector=self._client.connector,
                timeout=aiohttp.ClientTimeout(
                    total=None if timeout == 0 else timeout,
                    sock_read=None if timeout == 0 else timeout,
                ),
            )

    async def __aenter__(self) -> Docker:
        return self._client

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self._client.close()
