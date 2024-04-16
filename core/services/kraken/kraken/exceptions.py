
class ExtensionNotFound(Exception):
    """
    Exception raised when an extension that is expected to be available cannot be found.

    HTTP Status Code: 404 Not Found
    """
    pass


class ExtensionPullFailed(Exception):
    """
    Exception raised when there is a failure in pulling (downloading or installing) an extension.

    HTTP Status Code: 500 Internal Server Error
    """
    pass


class ExtensionContainerNotFound(Exception):
    """
    Exception raised when the container for an extension is not found, typically indicating
    that the extension has not been loaded or initialized properly.

    HTTP Status Code: 404 Not Found
    """
    pass
