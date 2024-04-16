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


class ContainerModel(BaseModel):
    """
    Represents a Docker container model.

    Attributes:
        name (str): The name of the container.
        image (str): The image used by the container.
        image_id (str): The ID of the image.
        status (str): The status of the container.
    """

    name: str
    image: str
    image_id: str
    status: str


class ContainerUsageModel(BaseModel):
    """
    Represents the usage of a Docker container.

    Attributes:
        cpu (str): The CPU usage of the container.
        memory (float): The memory usage of the container.
        disk (int): The disk usage of the container.
    """

    cpu: str
    memory: float
    disk: int
