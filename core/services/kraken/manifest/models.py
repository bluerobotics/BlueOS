import platform
from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, RootModel, Field, field_validator

class DockerPlatforms(StrEnum):
    ARM_V7 = "arm/v7"
    AMD64 = "amd64"
    ARM64 = "arm64"

    @staticmethod
    def from_machine() -> Optional["DockerPlatforms"]:
        machine = platform.machine()

        match machine:
            case "armv7l":
                return DockerPlatforms.ARM_V7
            case "x86_64" | "amd64":
                return DockerPlatforms.AMD64
            case "aarch64" | "arm64":
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

    @field_validator('compatible')
    @classmethod
    def is_compatible(cls, _value: bool):
        current_platform = DockerPlatforms.from_machine()

        if current_platform is not None:
            image_machine = cls.platform.architecture + (f"/{cls.platform.variant}" if cls.platform.variant else "")
            return current_platform == image_machine

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

class ExtensionMetadata(BaseModel):
    identifier: str
    name: str
    website: str
    docker: str
    description: str
    extension_logo: Optional[str] = None
    company_logo: Optional[str] = None

class RepositoryEntry(ExtensionMetadata):
    versions: Dict[str, ExtensionVersion] = Field(default_factory=dict)

class ManifestRoot(RootModel):
    root: List[RepositoryEntry]

class ManifestBase(BaseModel):
    name: str
    url: str
    priority: int

class ManifestData(ManifestBase):
    identifier: str
    data: List[RepositoryEntry]
