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
