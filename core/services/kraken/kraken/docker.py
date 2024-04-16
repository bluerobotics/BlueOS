import aiodocker


class DockerCtx(object):
    """
    Context manager for Docker client.
    """

    def __init__(self) -> None:
        """
        Initialize the Docker context manager.

        Returns:
            - None
        """

        self._client: aiodocker.Docker = aiodocker.Docker()


    async def __aenter__(self) -> aiodocker.Docker:
        """
        Create a new Docker client.

        Returns:
            - DockerClient: Docker client.
        """

        return self._client


    async def __aexit__(self, exc_type, exc, tb) -> None:
        """
        Close the Docker client.

        Args:
            - exc_type: Exception type.
            - exc: Exception.
            - tb: Traceback.

        Returns:
            - None
        """

        await self._client.close()
