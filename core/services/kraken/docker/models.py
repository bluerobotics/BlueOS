from pydantic import BaseModel

class ContainerModel(BaseModel):
    name: str
    image: str
    image_id: str
    status: str

class ContainerUsageModel(BaseModel):
    cpu: str
    memory: float
    disk: int
