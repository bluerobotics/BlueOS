class ManifestDataFetchFailed(Exception):
    pass


class ManifestInvalidURL(Exception):
    pass


class ManifestDataParseFailed(Exception):
    pass


class ManifestNotFound(Exception):
    pass


class ManifestOperationNotAllowed(Exception):
    pass


class ManifestBackendOffline(Exception):
    pass
