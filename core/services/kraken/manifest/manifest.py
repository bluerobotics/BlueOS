import asyncio
import uuid
from functools import wraps
from typing import Any, Callable, List, Optional, Set, Tuple, cast

import aiohttp
import semver
from aiocache import cached
from commonwealth.settings.manager import Manager
from loguru import logger

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
    _manager: Manager = Manager(SERVICE_NAME, SettingsV2)
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
        default_ids = [source["identifier"] for source in DEFAULT_MANIFESTS]
        had_settings = bool(cls._settings.manifests)

        def factory_snap() -> Tuple[dict[str, Tuple[Any, ...]], dict[str, int], dict[str, int]]:
            fields: dict[str, Tuple[Any, ...]] = {}
            index: dict[str, int] = {}
            counts: dict[str, int] = {}
            for i, manifest in enumerate(cls._settings.manifests):
                ident = manifest.identifier
                if ident not in default_ids:
                    continue
                counts[ident] = counts.get(ident, 0) + 1
                if ident not in fields:
                    fields[ident] = (manifest.enabled, manifest.factory, manifest.name, manifest.url)
                    index[ident] = i
            return fields, index, counts

        before = factory_snap()

        for source in DEFAULT_MANIFESTS:
            identifier = source["identifier"]
            name = source["name"]
            url = source["url"]

            # Keep factory sources present, named, enabled, and marked factory
            try:
                manifest = cls._get_settings_by_identifier(identifier)
                manifest.url = url
                manifest.name = name
                manifest.enabled = True
                manifest.factory = True
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

        # Pin factory sources first and drop duplicate factory rows left by older builds
        by_id: dict[str, ManifestSettings] = {}
        others: List[ManifestSettings] = []
        for manifest in cls._settings.manifests:
            if manifest.identifier in default_ids:
                by_id.setdefault(manifest.identifier, manifest)
            else:
                others.append(manifest)
        cls._settings.manifests = [by_id[identifier] for identifier in default_ids if identifier in by_id] + others
        for i, manifest in enumerate(cls._settings.manifests):
            manifest.priority = i
        after = factory_snap()
        if had_settings and before != after:
            logger.info(
                "Healed factory catalog sources "
                f"(fields {before[0]} -> {after[0]}; "
                f"index {before[1]} -> {after[1]}; "
                f"rows {before[2]} -> {after[2]})"
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
                            return ManifestData.parse_obj(await resp.json(content_type=None)).__root__
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

        results = await asyncio.gather(
            *[self._fetch_manifest(source, fetch_data) for source in settings],
            return_exceptions=True,
        )

        manifests: List[Manifest] = []
        for source, result in zip(settings, results):
            if isinstance(result, BaseException):
                if not isinstance(result, Exception):
                    raise result
                logger.warning(f"Skipping unreachable manifest source {source.identifier} ({source.url}): {result}")
                manifests.append(await self._fetch_manifest(source, fetch_data=False))
            else:
                manifests.append(cast(Manifest, result))
        return manifests

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

    def _raise_if_default_manifests_demoted(self, new_order: List[str]) -> None:
        # 409 if a factory source would lose its current index or be omitted.
        # Unknown ids are not this check: callers look up first (404). Dummy
        # order/0 is 409 because factory would drop from 0 to 1.
        current = [manifest.identifier for manifest in self._get_settings()]
        for identifier in (source["identifier"] for source in DEFAULT_MANIFESTS):
            if identifier not in current:
                continue
            if identifier not in new_order or new_order.index(identifier) > current.index(identifier):
                self._raise_in_default_source(identifier)

    @staticmethod
    def not_on_default_manifest(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self: "ManifestManager", identifier: str, *args: Tuple[Any], **kwargs: dict[str, Any]) -> Any:
            self._raise_in_default_source(identifier)
            return await func(self, identifier, *args, **kwargs)

        return wrapper

    async def add_source(self, source: ManifestSource, validate_url: bool) -> Manifest:
        manifests = self._get_settings()

        if any(manifest.name == source.name and manifest.url == source.url for manifest in manifests):
            raise ManifestOperationNotAllowed(
                f"Manifest source with name [{source.name}] and url [{source.url}] already exists"
            )

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
        self._raise_in_default_source(identifier)
        manifest = self._get_settings_by_identifier(identifier)
        manifest.enabled = enabled
        self._manager.save()

    async def enable_source(self, identifier: str) -> None:
        self._set_enabled(identifier, True)

    async def disable_source(self, identifier: str) -> None:
        self._set_enabled(identifier, False)

    @not_on_default_manifest
    async def order_source(self, identifier: str, order: int) -> None:
        manifest = self._get_settings_by_identifier(identifier)
        manifests = self._get_settings()
        proposed = [item.identifier for item in manifests if item.identifier != identifier]
        proposed.insert(min(order, len(proposed)), identifier)
        self._raise_if_default_manifests_demoted(proposed)

        manifest.priority = order

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

        for identifier in identifiers:
            if identifier not in manifest_record:
                raise ManifestNotFound(f"Manifest with identifier {identifier} not found")

        if len(identifiers) != len(set(identifiers)):
            raise ManifestOperationNotAllowed("Duplicate manifest identifiers are not allowed")

        omitted = [manifest.identifier for manifest in manifests if manifest.identifier not in identifiers]
        self._raise_if_default_manifests_demoted(identifiers + omitted)

        ordered_manifests = []
        for order, identifier in enumerate(identifiers):
            manifest = manifest_record[identifier]
            manifest.priority = order
            ordered_manifests.append(manifest)

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

    @staticmethod
    def versions_from_entry(ext: RepositoryEntry, stable: bool) -> List[str]:
        if not ext.versions:
            return []

        def valid_semver(string: str) -> Optional[semver.VersionInfo]:
            # We want to allow versions to be prefixed with a 'v'.
            if string.startswith("v"):
                string = string[1:]
            try:
                return semver.VersionInfo.parse(string)
            except ValueError:
                return None

        tagged = []
        for tag in ext.versions:
            version = valid_semver(tag)
            if version is not None:
                tagged.append((version, tag))
        tagged.sort(key=lambda item: item[0], reverse=True)
        if stable:
            tagged = [(version, tag) for version, tag in tagged if not version.prerelease]
        return [tag for _, tag in tagged]

    async def fetch_latest_extension_version(
        self, extension_id: str, stable: bool, manifest_id: Optional[str] = None
    ) -> Optional[ExtensionVersion]:
        ext = await self.fetch_extension(extension_id, manifest_id)
        if not ext or not ext.versions:
            return None

        versions = self.versions_from_entry(ext, stable)

        return ext.versions.get(versions[0]) if versions else None

    async def fetch_extension_version(self, extension_id: str, tag: str) -> Optional[ExtensionVersion]:
        ext = await self.fetch_extension(extension_id)
        if not ext:
            return None

        return (
            ext.versions.get(tag)
            or ext.versions.get(f"v{tag}")
            or (ext.versions.get(tag[1:]) if tag.startswith("v") else None)
        )
