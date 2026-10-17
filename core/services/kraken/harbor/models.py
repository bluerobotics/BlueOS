from pydantic import BaseModel


class ContainerModel(BaseModel):
    name: str
    image: str
    image_id: str
    status: str
    uptime_seconds: float | None = None


class ContainerUsageModel(BaseModel):
    cpu: float
    memory: float | str
    disk: float | str
