import json
from typing import Optional

from pydantic import BaseModel

from manifest.models import ExtensionVersion, RepositoryEntry
from settings import ExtensionSettings


class ExtensionSourceAuth(BaseModel):
    username: str
    password: str


class ExtensionSource(BaseModel):
    identifier: str
    tag: str
    name: str
    docker: str
    enabled: bool
    permissions: str
    user_permissions: str = ""
    auth: Optional[ExtensionSourceAuth] = None

    @staticmethod
    def from_settings(settings: ExtensionSettings) -> "ExtensionSource":
        return ExtensionSource(
            identifier=settings.identifier,
            tag=settings.tag,
            name=settings.name,
            docker=settings.docker,
            enabled=settings.enabled,
            permissions=settings.permissions,
            user_permissions=settings.user_permissions,
        )

    @staticmethod
    def from_repository_version(entry: RepositoryEntry, version: ExtensionVersion) -> "ExtensionSource":
        return ExtensionSource(
            identifier=entry.identifier,
            tag=version.tag,
            name=entry.name,
            docker=entry.docker,
            enabled=False,
            permissions=json.dumps(version.permissions),
            user_permissions="",
        )
