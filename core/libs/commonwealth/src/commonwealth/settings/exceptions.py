class BadSettingsFile(ValueError):
    """Settings file is not valid."""


class SettingsFromTheFuture(ValueError):
    """Settings file version is from a newer version of the service."""


class MigrationFail(RuntimeError):
    """Could not apply migration."""


class BadAttributes(BadSettingsFile):
    """Attributes on settings file are not valid."""


class BadSettingsClassNaming(RuntimeError):
    """Setting class in the inheritance chain have a name that is not valid."""
