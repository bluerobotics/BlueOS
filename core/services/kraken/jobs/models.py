from enum import Enum
from typing import Any

from pydantic import BaseModel


class JobMethod(str, Enum):
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class Job(BaseModel):
    id: str
    route: str
    method: JobMethod
    body: Any
    retries: int = 5
