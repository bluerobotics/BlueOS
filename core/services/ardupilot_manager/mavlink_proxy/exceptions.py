class DuplicateEndpointName(ValueError):
    """Another mavlink endpoint with same name already exists."""


class EndpointAlreadyExists(ValueError):
    """Mavlink endpoint already exists."""


class EndpointDontExist(ValueError):
    """Given Mavlink endpoint do not exist."""


class MavlinkRouterStartFail(RuntimeError):
    """Failed to initiate Mavlink router."""


class NoMasterMavlinkEndpoint(ValueError):
    """No master Mavlink endpoint set."""


class EndpointCreationFail(RuntimeError):
    """Failed to add endpoint."""


class EndpointDeleteFail(RuntimeError):
    """Failed to delete endpoint."""


class EndpointUpdateFail(RuntimeError):
    """Failed to update endpoint."""
