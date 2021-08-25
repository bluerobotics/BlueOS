"""
Ardupilot-manager exception classes.
"""


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
