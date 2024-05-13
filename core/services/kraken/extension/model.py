from pydantic import BaseModel

class ExtensionModel(BaseModel):
    """
    Represents an extension model.

    Attributes:
        identifier (str): The unique identifier of the extension.
        name (str): The name of the extension.
        docker (str): The Docker image of the extension.
        tag (str): The tag associated with the Docker image.
        permissions (str): The permissions required by the extension.
        enabled (str): Indicates whether the extension is enabled or not.
        user_permissions (str): The permissions assigned to users for this extension.
    """

    identifier: str
    name: str
    docker: str
    tag: str
    permissions: str
    enabled: str
    user_permissions: str
