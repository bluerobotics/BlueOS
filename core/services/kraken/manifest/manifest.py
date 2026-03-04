import asyncio
import uuid
from functools import wraps
from typing import Any, Callable, List, Optional, Set, Tuple, cast

import aiohttp
import semver
from aiocache import cached
from commonwealth.settings.manager import PydanticManager
from config import DEFAULT_MANIFESTS, SERVICE_NAME
from manifest.exceptions import (
    ManifestBackendOffline,
    ManifestDataFetchFailed,
    ManifestDataParseFailed,
    ManifestInvalidURL,
    ManifestNotFound,
    ManifestOperationNotAllowed,
)
from manifest.models import (
    ExtensionVersion,
    Manifest,
    ManifestData,
    ManifestSource,
    RepositoryEntry,
    UpdateManifestSource,
)
from settings import ManifestSettings, SettingsV2


class ManifestManager:
    """
    Class responsible for fetching and managing extension manifests.
    """

    _instance: Optional["ManifestManager"] = None
    _manager: PydanticManager = PydanticManager(SERVICE_NAME, SettingsV2)
    _settings = _manager.settings

    def __init__(self) -> None:
        raise RuntimeError("This class should not be instantiated, use ManifestManager.instance() instead")

    @classmethod
    def _get_settings(cls) -> List[ManifestSettings]:
        return cast(List[ManifestSettings], sorted(cls._settings.manifests, key=lambda x: x.priority))

    @classmethod
    def _get_settings_by_identifier(cls, identifier: str) -> ManifestSettings:
        manifest = next(filter(lambda x: x.identifier == identifier, cls._settings.manifests), None)
        if not manifest:
            raise ManifestNotFound(f"Manifest with identifier {identifier} not found")
        return cast(ManifestSettings, manifest)

    @classmethod
    def _set_default_manifests(cls) -> None:
        for source in DEFAULT_MANIFESTS:
            identifier = source["identifier"]
            name = source["name"]
            url = source["url"]

            # If already exists only update the name and url otherwise add it
            try:
                manifest = cls._get_settings_by_identifier(identifier)
                manifest.url = url
                manifest.name = name
            except ManifestNotFound:
                cls._settings.manifests.append(
                    ManifestSettings(
                        identifier=identifier,
                        enabled=True,
                        priority=len(cls._settings.manifests),
                        factory=True,
                        name=name,
                        url=url,
                    )
                )
        cls._manager.save()

    @classmethod
    def instance(cls) -> "ManifestManager":
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._set_default_manifests()

        return cls._instance

    @cached(ttl=3600, namespace="manifest")
    async def _fetch_manifest_data(self, url: str) -> List[RepositoryEntry]:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Accept": "application/json"}
                try:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            raise ManifestDataFetchFailed(
                                f"Failed to fetch manifest data from {url} with status {resp.status}"
                            )

                        try:
                            return ManifestData.model_validate(await resp.json(content_type=None)).root
                        except Exception as e:
                            raise ManifestDataParseFailed(f"Failed to parse manifest data from {url}") from e
                except aiohttp.InvalidURL as e:
                    raise ManifestInvalidURL(f"Invalid URL {url}") from e
        except aiohttp.ClientConnectionError as e:
            raise ManifestBackendOffline("Unable to fetch manifest, backend is offline") from e

    async def _fetch_manifest(self, settings: ManifestSettings, fetch_data: bool = True) -> Manifest:
        manifest = Manifest(
            identifier=settings.identifier,
            name=settings.name,
            url=settings.url,
            priority=settings.priority,
            enabled=settings.enabled,
            factory=settings.factory,
        )

        if fetch_data:
            manifest.data = await self._fetch_manifest_data(settings.url)

        return manifest

    async def fetch(self, fetch_data: bool, enabled: bool = False) -> List[Manifest]:
        settings: List[ManifestSettings] = self._get_settings()

        if enabled:
            settings = [source for source in settings if source.enabled]

        return await asyncio.gather(*[self._fetch_manifest(source, fetch_data) for source in settings])

    async def fetch_by_identifier(self, identifier: str, fetch_data: bool) -> Manifest:
        settings = self._get_settings_by_identifier(identifier)

        return await self._fetch_manifest(settings, fetch_data)

    async def fetch_consolidated(self) -> List[RepositoryEntry]:
        manifests = await self.fetch(fetch_data=True, enabled=True)

        consolidated = []
        seen_identifiers: Set[str] = set()
        for manifest in manifests:
            if manifest.data is not None:
                new_entries = [entry for entry in manifest.data if entry.identifier not in seen_identifiers]
                consolidated.extend(new_entries)
                seen_identifiers.update(entry.identifier for entry in new_entries)

        return consolidated

    def _raise_in_default_source(self, identifier: str) -> None:
        default_identifiers = [source["identifier"] for source in DEFAULT_MANIFESTS]

        if identifier in default_identifiers:
            raise ManifestOperationNotAllowed(f"Operation is not allowed in default manifest [{identifier}]")

    @staticmethod
    def not_on_default_manifest(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self: "ManifestManager", identifier: str, *args: Tuple[Any], **kwargs: dict[str, Any]) -> Any:
            self._raise_in_default_source(identifier)
            return await func(self, identifier, *args, **kwargs)

        return wrapper

    async def add_source(self, source: ManifestSource, validate_url: bool) -> Manifest:
        manifests = self._get_settings()

        new_manifest_settings = ManifestSettings(
            identifier=str(uuid.uuid4()),
            priority=len(manifests),
            factory=False,
            enabled=source.enabled,
            url=source.url,
            name=source.name,
        )

        new_manifest = await self._fetch_manifest(new_manifest_settings, validate_url)

        self._settings.manifests.append(new_manifest_settings)
        self._manager.save()

        return new_manifest

    @not_on_default_manifest
    async def remove_source(self, identifier: str) -> None:
        manifest = self._get_settings_by_identifier(identifier)
        self._settings.manifests.remove(manifest)
        self._manager.save()

    @not_on_default_manifest
    async def update_source(self, identifier: str, source: UpdateManifestSource, validate_url: bool) -> None:
        manifest = self._get_settings_by_identifier(identifier)

        manifest.name = source.name if source.name is not None else manifest.name
        manifest.url = source.url if source.url is not None else manifest.url
        manifest.enabled = source.enabled if source.enabled is not None else manifest.enabled

        if validate_url:
            await self._fetch_manifest(manifest)

        self._manager.save()

    def _set_enabled(self, identifier: str, enabled: bool) -> None:
        manifest = self._get_settings_by_identifier(identifier)
        manifest.enabled = enabled
        self._manager.save()

    async def enable_source(self, identifier: str) -> None:
        self._set_enabled(identifier, True)

    async def disable_source(self, identifier: str) -> None:
        self._set_enabled(identifier, False)

    async def order_source(self, identifier: str, order: int) -> None:
        manifest = self._get_settings_by_identifier(identifier)
        manifest.priority = order

        manifests = self._get_settings()
        if manifest in manifests:
            manifests.remove(manifest)

        manifests.insert(min(order, len(manifests)), manifest)

        for i, m in enumerate(manifests):
            m.priority = i

        self._settings.manifests = manifests
        self._manager.save()

    async def order_sources(self, identifiers: List[str]) -> None:
        manifests = self._get_settings()
        manifest_record = {manifest.identifier: manifest for manifest in manifests}

        ordered_manifests = []
        for order, identifier in enumerate(identifiers):
            if identifier in manifest_record:
                manifest = manifest_record[identifier]
                manifest.priority = order
                ordered_manifests.append(manifest)
            else:
                raise ManifestNotFound(f"Manifest with identifier {identifier} not found")

        for manifest in manifests:
            if manifest.identifier not in identifiers:
                manifest.priority = len(ordered_manifests)
                ordered_manifests.append(manifest)

        self._settings.manifests = ordered_manifests
        self._manager.save()

    async def fetch_extension(self, extension_id: str, manifest_id: Optional[str] = None) -> Optional[RepositoryEntry]:
        manifest = []
        if manifest_id is None:
            # Only fetch enabled sources already sorted by priority
            manifest = await self.fetch_consolidated()
        else:
            manifest = (await self.fetch_by_identifier(manifest_id, fetch_data=True)).data or []

        return next((ext for ext in manifest if ext.identifier == extension_id), None)

    async def fetch_extension_versions(
        self, extension_id: str, stable: bool, manifest_id: Optional[str] = None
    ) -> List[semver.VersionInfo]:
        ext = await self.fetch_extension(extension_id, manifest_id)
        if not ext or not ext.versions:
            return []

        def valid_semver(string: str) -> Optional[semver.VersionInfo]:
            # We want to allow versions to be prefixed with a 'v'.
            if string.startswith("v"):
                string = string[1:]
            try:
                return semver.VersionInfo.parse(string)
            except ValueError:
                return None

        versions: List[semver.VersionInfo] = sorted(
            [ver for ver in (valid_semver(tag) for tag in ext.versions) if ver is not None],
            reverse=True,
        )
        if stable:
            versions = [v for v in versions if not v.prerelease and not v.patch]

        return versions

    async def fetch_latest_extension_version(
        self, extension_id: str, stable: bool, manifest_id: Optional[str] = None
    ) -> Optional[ExtensionVersion]:
        ext = await self.fetch_extension(extension_id, manifest_id)
        if not ext or not ext.versions:
            return None

        versions = await self.fetch_extension_versions(extension_id, stable, manifest_id)

        return (ext.versions.get(str(versions[0])) or ext.versions.get(f"v{versions[0]}")) if versions else None

    async def fetch_extension_version(self, extension_id: str, tag: str) -> Optional[ExtensionVersion]:
        ext = await self.fetch_extension(extension_id)
        if not ext:
            return None

        return ext.versions.get(tag)
