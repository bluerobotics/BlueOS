import platform as sys_platform
from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

# Manifest data source models


class DockerPlatforms(StrEnum):
    ARM_V7 = "arm/v7"
    AMD64 = "amd64"
    ARM64 = "arm64"

    @staticmethod
    def from_machine() -> Optional["DockerPlatforms"]:
        machine = sys_platform.machine()

        match machine:
            case "armv7l":
                return DockerPlatforms.ARM_V7
            case "x86_64" | "amd64":
                return DockerPlatforms.AMD64
            case "aarch64" | "arm64":
                # catch the case of 64 bit kernel with 32bit userland on Pi 5
                if sys_platform.architecture()[0] == "32bit":
                    return DockerPlatforms.ARM_V7
                return DockerPlatforms.ARM64
            case _:
                return None


class ExtensionType(StrEnum):
    DEVICE_INTEGRATION = "device-integration"
    EXAMPLE = "example"
    THEME = "theme"
    OTHER = "other"
    TOOL = "tool"
    EDUCATION = "education"


class Author(BaseModel):
    name: str
    email: str


class Platform(BaseModel):
    architecture: str
    variant: Optional[str] = None
    os: Optional[str] = None


class Image(BaseModel):
    expanded_size: int
    platform: Platform
    digest: Optional[str] = None
    compatible: bool = False

    @validator("compatible", pre=True, always=True)
    @classmethod
    def is_compatible(cls, _value: bool, values: Any) -> bool:
        current_platform = DockerPlatforms.from_machine()

        if current_platform is not None:
            platform = values["platform"].architecture
            variant = values["platform"].variant

            image_machine = platform + (f"/{variant}" if variant else "")
            return bool(current_platform == image_machine)

        return False


class Company(BaseModel):
    name: str
    about: Optional[str] = None
    email: Optional[str] = None


class ExtensionVersion(BaseModel):
    type: ExtensionType
    images: List[Image]
    authors: List[Author]
    filter_tags: List[str]
    extra_links: Dict[str, str]
    website: Optional[str] = None
    tag: Optional[str] = None
    docs: Optional[str] = None
    readme: Optional[str] = None
    support: Optional[str] = None
    requirements: Optional[str] = None
    company: Optional[Company] = None
    permissions: Optional[Dict[str, Any]] = None


class RepoInfo(BaseModel):
    downloads: int
    last_updated: Optional[str] = None  # utc timestamp
    date_registered: Optional[str] = None  # utc timestamp


class ExtensionMetadata(BaseModel):
    identifier: str
    name: str
    website: str
    docker: str
    description: str
    extension_logo: Optional[str] = None
    company_logo: Optional[str] = None
    repo_info: Optional[RepoInfo] = None


class RepositoryEntry(ExtensionMetadata):
    versions: Dict[str, ExtensionVersion] = Field(default_factory=dict)


# Local Manifest models


class ManifestData(BaseModel):
    __root__: List[RepositoryEntry]


class ManifestSource(BaseModel):
    name: str
    url: str
    enabled: bool


class UpdateManifestSource(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None


class Manifest(ManifestSource):
    identifier: str
    priority: int
    factory: bool
    data: Optional[List[RepositoryEntry]] = None
