
class InvalidEnvironmentImplementation(ValueError):
    """Required platform implementation class does not exists"""

class InvalidFirmwareImplementation(ValueError):
    """Required firmware implementation class does not exists"""

class InvalidAutopilotManifestData(ValueError):
    """Invalid manifest data"""

class InvalidAutopilotManifestURL(ValueError):
    """Invalid manifest URL"""

class ManifestDataFetchFailed(RuntimeError):
    """Failed to fetch manifest data"""

class BackendIsOffline(RuntimeError):
    """Backend is offline"""
