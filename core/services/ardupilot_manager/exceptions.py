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


class NoCandidate(ValueError):
    """No firmware candidate found for specified configuration."""


class MoreThanOneCandidate(ValueError):
    """More than one firmware candidate found for specified configuration."""


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


class ArdupilotProcessKillFail(RuntimeError):
    """Could not kill Ardupilot process."""


class NoDefaultFirmwareAvailable(RuntimeError):
    """Default firmware file is not available."""


class EndpointCreationFail(RuntimeError):
    """Failed to add endpoint."""


class EndpointDeleteFail(RuntimeError):
    """Failed to delete endpoint."""


class EndpointUpdateFail(RuntimeError):
    """Failed to update endpoint."""


class MavlinkRouterStartFail(RuntimeError):
    """Failed to initiate Mavlink router."""


class NoMasterMavlinkEndpoint(ValueError):
    """No master Mavlink endpoint set."""


class EndpointAlreadyExists(ValueError):
    """Mavlink endpoint already exists."""


class DuplicateEndpointName(ValueError):
    """Another mavlink endpoint with same name already exists."""


class EndpointDontExist(ValueError):
    """Given Mavlink endpoint do not exist."""


class NoPreferredBoardSet(RuntimeError):
    """No preferred board is set yet."""
