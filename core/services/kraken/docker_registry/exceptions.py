class RegistryError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ManifestNotFound(RegistryError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 404)
