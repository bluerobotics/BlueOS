import uuid
from typing import List, Optional, cast

import aiohttp
from aiocache import cached, Cache
from pydantic import RootModel

from manifest.models import ManifestRoot, ManifestData
from commonwealth.settings.manager import Manager
from config import EXT_PROD_MANIFEST_URL, SERVICE_NAME
from settings import ManifestSettings, SettingsV1

class Manifest:
    def __init__(self, settings: ManifestSettings) -> None:
        self.settings = settings

    async def _from_url(self, url: str) -> ManifestRoot:
        headers = {"Accept": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    error_msg = f"Failed to fetch manifest from {url}, status code: {resp.status}"
                    raise RuntimeError(error_msg)

                return ManifestRoot.model_validate(await resp.json(content_type=None))

    @cached(ttl=3600)
    async def fetch(self) -> ManifestData:
        data = await self._from_url(self.settings.url)

        return ManifestData(
            identifier=self.settings.identifier,
            name=self.settings.name,
            url=self.settings.url,
            priority=self.settings.priority,
            data=data.root
        )


class ManifestManager:
    """
    Class responsible for fetching and managing the extension manifest.
    """

    _instance: Optional["ManifestManager"] = None
    _settings: Manager = Manager(SERVICE_NAME, SettingsV1).settings
    _manifests: List[Manifest] = []

    def __init__(self) -> None:
        raise RuntimeError("This class should not be instantiated, use Manifest.instance() instead")

    @classmethod
    def instance(cls) -> "ManifestManager":
        return cls._instance if cls._instance else cls.__new__(cls)

    def _sorted_settings(self) -> List[ManifestSettings]:
        manifests = sorted(ManifestManager.settings.manifests, key=lambda x: x.priority, reverse=True)
        return cast(List[ManifestSettings], manifests)

    async def fetch() -> List[ManifestData]:
        for source in self._sorted_settings():
            pass

    async def fetch_by_identifier(self, identifier: str) -> Optional[Manifest]:
        manifests = await self.fetch()
        return next(filter(lambda x: x.identifier == identifier, manifests), None)

    async def add(self, data: ManifestBase) -> str:
        manifest = ManifestSettings(
            identifier=str(uuid.uuid4()),
            name=data.name,
            url=data.url,
            priority=data.priority
        )
        ManifestManager._settings.manifests.append(manifest)
        ManifestManager._settings.save()
        ManifestManager._cache.delete("_manifest_manager_fetch_")

        return manifest.identifier

    async def remove(self, identifier: str) -> None:
        ManifestManager._settings.manifests = [
            other
            for other in ManifestManager._settings.manifests
            if not (other.identifier == self.identifier and other.tag == self.tag)
        ]
        if extension:
            self.settings.extensions.append(extension)
        self.manager.save()

    async def update(self, identifier: str, data: ManifestBase) -> None:
        pass

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
        Returns the version of the manifest.

        Returns:
            str: Version of the manifest.
        """

        ext = await self.get_extension(identifier)

        if not ext:
            return None

        return ext.versions.get(version, None)
