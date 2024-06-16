from typing import Any

from aiodocker import Docker


class DockerCtx:
    """
    Context manager for Docker clients.
    """

    def __init__(self) -> None:
        self._client: Docker = Docker()

    async def __aenter__(self) -> Docker:
        return self._client

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self._client.close()
