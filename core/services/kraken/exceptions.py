class ContainerDoesNotExist(RuntimeError):
    """Attempted to use a non-existing container"""


class ExtensionNotFound(RuntimeError):
    """Attempted to operate on a non-existing extension"""
