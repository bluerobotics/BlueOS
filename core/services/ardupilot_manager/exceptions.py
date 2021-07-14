"""
Ardupilot-manager exception classes.
"""


class FirmwareUploadFail(RuntimeError):
    """Firmware upload operation failed."""


class UploadToolNotFound(RuntimeError):
    """Firmware upload tool not found."""


class InvalidUploadTool(ValueError):
    """Firmware upload tool cannot be validated."""


class InvalidFirmwareFile(ValueError):
    """Firmware file cannot be validated."""


class UndefinedPlatform(ValueError):
    """Ardupilot platform is not defined."""


class UnsupportedPlatform(ValueError):
    """Ardupilot platform not supported."""


class FirmwareInstallFail(RuntimeError):
    """Firmware install operation failed."""


class FirmwareDownloadFail(RuntimeError):
    """Firmware download operation failed."""


class NoVersionAvailable(ValueError):
    """No firmware versions available for specified configuration."""


class InvalidManifest(ValueError):
    """Ardupilot manifest file cannot be validated."""


class ManifestUnavailable(RuntimeError):
    """Ardupilot manifest file unavailable."""


class MoreThanOneCandidate(ValueError):
    """More than one firmware candidate found for specified configuration."""
