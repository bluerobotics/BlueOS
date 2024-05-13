import aiodocker

class DockerCtx(object):
    """
    Context manager for Docker client.
    """

    def __init__(self) -> None:
        self._client: aiodocker.Docker = aiodocker.Docker()

    async def __aenter__(self) -> aiodocker.Docker:
        return self._client

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._client.close()
