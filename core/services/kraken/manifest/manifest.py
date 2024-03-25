import datetime
import dataclasses
from typing import List, Optional
# Extra
import aiohttp
from dataclass_wizard import fromdict
# Models
from manifest.models import RepositoryEntry

# Current Extension Manifest host
REPO_URL = "https://bluerobotics.github.io/BlueOS-Extensions-Repository/manifest.json"


@dataclasses.dataclass
class ManifestContent:
    """
    Represents the manifest content with cache control.

    Attributes:
        extensions (List[RepositoryEntry]): List of extensions in the manifest.
        issued_at (Optional[int]): Timestamp when the manifest was issued.
        expires_in (Optional[int]): Time in seconds until the manifest expires.
    """

    extensions: List[RepositoryEntry]
    expires_in: int = 3600
    issued_at: int = datetime.datetime.now(datetime.timezone.utc)


    @property
    def is_expired(self) -> bool:
        """
        Checks if the manifest is expired.

        Returns:
            bool: True if the manifest is expired, False otherwise.
        """

        return (datetime.datetime.now(datetime.timezone.utc) - self.issued_at).total_seconds() > self.expires_in


class Manifest:
    """
    Class responsible for fetching and managing the extension manifest.
    """

    _instance: Optional["Manifest"] = None
    _cached_manifest: Optional[ManifestContent] = None


    def __init__(self):
        raise RuntimeError("This class should not be instantiated, use Manifest.instance() instead")


    @classmethod
    def instance(cls) -> "Manifest":
        """
        Returns the instance of the manifest manager.

        Returns:
            Manifest: Instance of the manifest.
        """

        if cls._instance is None:
            cls._instance = cls.__new__(cls)
        return cls._instance


    async def _fetch_manifest(self) -> ManifestContent:
        """
        Fetches the manifest from the repository.

        Returns:
            ManifestContent: Manifest content.

        Raises:
            RuntimeError: If the manifest could not be fetched.
        """

        async with aiohttp.ClientSession() as session:
            async with session.get(REPO_URL) as resp:
                if resp.status != 200:
                    error_msg = f"Error fetching manifest file: response status {resp.status}"
                    print(error_msg)
                    raise RuntimeError(error_msg)

                data = await resp.json()
                return fromdict(ManifestContent, data)


    async def fetch(self) -> List[RepositoryEntry]:
        """
        Fetches the manifest from repository or cache if valid.

        Returns:
            List[RepositoryEntry]: List of extensions in the manifest.

        Raises:
            RuntimeError: If the manifest could not be fetched.
        """

        if not self._cached_manifest or self._cached_manifest.is_expired:
            self._cached_manifest = await self._fetch_manifest()

        return self._cached_manifest.extensions


    async def get_extension(self, identifier: str) -> Optional[RepositoryEntry]:
        """
        Fetches the manifest from repository or cache if valid.

        Args:
            identifier (str): Identifier of the extension.

        Returns:
            Optional[RepositoryEntry]: Extension in the manifest.
        """

        extensions = await self.fetch()

        return next(filter(lambda extension: extension.identifier == identifier, extensions), None)
