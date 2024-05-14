import dataclasses
import platform
from enum import StrEnum
from typing import Any, Dict, List, Optional


class DockerPlatforms(StrEnum):
    """
    Enum representing supported platforms from docker buildx.
    """

    ARM_V7 = "arm/v7"
    AMD64 = "amd64"
    ARM64 = "arm64"

    @staticmethod
    def from_machine() -> Optional["DockerPlatforms"]:
        """
        Returns current uname machine equivalent DockerPlatforms enum value.

        Args:
            machine (str): Uname machine string.

        Returns:
            Optional[DockerPlatforms]: DockerPlatforms enum value if conversion is possible.
        """

        machine = platform.machine()

        match machine:
            case "armv7l":
                return DockerPlatforms.ARM_V7
            case "x86_64" | "amd64":
                return DockerPlatforms.AMD64
            case "aarch64" | "arm64":
                # catch the case of 64 bit kernel with 32bit userland on Pi 5
                if platform.architecture()[0] == "32bit":
                    return DockerPlatforms.ARM_V7
                return DockerPlatforms.ARM64
            case _:
                return None


class ExtensionType(StrEnum):
    """
    Represents the type of an extension.

    Attributes:
        DEVICE_INTEGRATION (str): Device integration extension.
        EXAMPLE (str): Example extension.
        THEME (str): Theme extension.
        OTHER (str): Other extension.
        TOOL (str): Tool extension.
    """

    DEVICE_INTEGRATION = "device-integration"
    EXAMPLE = "example"
    THEME = "theme"
    OTHER = "other"
    TOOL = "tool"
    EDUCATION = "education"


@dataclasses.dataclass
class Author:
    """
    Represents an author of an extension.

    Attributes:
        name (str): Name of the author.
        email (str): Email of the author.
    """

    name: str
    email: str


@dataclasses.dataclass
class Platform:
    """
    Represents a platform supported by the extension.

    Attributes:
        architecture (str): Architecture of the platform.
        variant (Optional[str]): Variant of the platform.
        os (Optional[str]): Operating system of the platform.
    """

    architecture: str
    variant: Optional[str] = None
    os: Optional[str] = None


@dataclasses.dataclass
class Image:
    """
    Represents description of an image available for a given extension version.

    Attributes:
        digest (Optional[str]): Digest of the image.
        expanded_size (int): Uncompressed size of the image.
        platform (Platform): Platform of the image.
        compatible (bool): Whether the image is compatible with the platform.
    """

    expanded_size: int
    platform: Platform
    digest: Optional[str] = None
    compatible: bool = False

    def __post_init__(self) -> None:
        current_platform = DockerPlatforms.from_machine()

        if current_platform is not None:
            image_machine = self.platform.architecture + (f"/{self.platform.variant}" if self.platform.variant else "")
            self.compatible = current_platform == image_machine


@dataclasses.dataclass
class Company:
    """
    Represents a company associated with an extension.

    Attributes:
        name (str): Name of the company.
        about (Optional[str]): Description of the company.
        email (Optional[str]): Email of the company.
    """

    name: str
    about: Optional[str] = None
    email: Optional[str] = None


# pylint: disable=too-many-instance-attributes
@dataclasses.dataclass
class ExtensionVersion:
    """
    Represents a version of an extension.

    Attributes:
        tag (Optional[str]): Tag of the version.
        type (ExtensionType): Type of the extension.
        website (str): URL to the extension's website.
        docs (Optional[str]): URL to the extension's documentation.
        readme (Optional[str]): URL to the extension's readme.
        support (Optional[str]): URL to the extension's support.
        requirements (Optional[str]): Requirements of the extension.
        authors (List[Author]): Authors of the extension.
        company (Optional[Company]): Company associated with the extension.
        permissions (Optional[Dict[str, Any]]): Permissions of the extension.
        filter_tags (List[str]): Tags used to filter the extension.
        extra_links (Dict[str, str]): Extra links associated with the extension.
        images (List[Image]): Images available for the extension.
    """

    type: ExtensionType
    website: str
    images: List[Image]
    authors: List[Author]
    filter_tags: List[str]
    extra_links: Dict[str, str]
    tag: Optional[str] = None
    docs: Optional[str] = None
    readme: Optional[str] = None
    support: Optional[str] = None
    requirements: Optional[str] = None
    company: Optional[Company] = None
    permissions: Optional[Dict[str, Any]] = None


@dataclasses.dataclass
class ExtensionMetadata:
    """
    Represents metadata associated with some extension.

    Attributes:
        identifier (str): Identifier of the extension.
        name (str): Name of the extension.
        website (str): URL to the extension's website.
        docker (str): Docker repository name.
        description (str): Description of the extension.
        extension_logo (Optional[str]): URL to the extension's logo.
        company_logo (Optional[str]): URL to the company's logo.
    """

    identifier: str
    name: str
    website: str
    docker: str
    description: str
    extension_logo: Optional[str] = None
    company_logo: Optional[str] = None


@dataclasses.dataclass
class RepositoryEntry(ExtensionMetadata):
    """
    Represents a repository entry in the manifest output

    Attributes:
        versions (Dict[str, Version]): Available extension versions.
    """

    versions: Dict[str, ExtensionVersion] = dataclasses.field(default_factory=dict)
