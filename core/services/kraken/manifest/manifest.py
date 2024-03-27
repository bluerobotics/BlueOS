import dataclasses
import datetime
from typing import List, Optional, cast

# Extra
import aiohttp
from dataclass_wizard import fromdict

# Models
from manifest.models import ExtensionVersion, RepositoryEntry

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
    # pylint: disable=unnecessary-lambda
    issued_at: int = dataclasses.field(default_factory=lambda: ManifestContent._current_timestamp())

    @classmethod
    def _current_timestamp(cls) -> int:
        """
        Returns the current timestamp as an integer.

        Returns:
            int: Current timestamp.
        """

        return int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    @property
    def is_expired(self) -> bool:
        """
        Checks if the manifest is expired.

        Returns:
            bool: True if the manifest is expired, False otherwise.
        """

        return (ManifestContent._current_timestamp() - self.issued_at) > self.expires_in


class Manifest:
    """
    Class responsible for fetching and managing the extension manifest.
    """

    _instance: Optional["Manifest"] = None
    _cached_manifest: Optional[ManifestContent] = None

    def __init__(self) -> None:
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

        headers = {"Accept": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.get(REPO_URL, headers=headers) as resp:
                if resp.status != 200:
                    error_msg = f"Error fetching manifest file: response status {resp.status}"
                    print(error_msg)
                    raise RuntimeError(error_msg)

                content = {"extensions": await resp.json()}

                return cast(ManifestContent, fromdict(ManifestContent, content))

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

        matching_extensions = (extension for extension in extensions if extension.identifier == identifier)
        return next(matching_extensions, None)

    async def get_extension_version(self, identifier: str, version: str) -> Optional[ExtensionVersion]:
        """
        Returns a given extension version from the manifest.

        Args:
            identifier (str): Identifier of the extension.
            version (str): Version of the extension.

        Returns:
            Optional[ExtensionVersion]: Extension version in the manifest.
        """

        ext = await self.get_extension(identifier)

        if not ext:
            return None

        return ext.versions.get(version, None)
