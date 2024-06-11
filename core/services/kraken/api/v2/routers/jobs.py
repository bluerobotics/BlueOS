import uuid
from functools import wraps
from typing import Any, Callable, List, Tuple

from fastapi import APIRouter, Body, HTTPException, status
from fastapi_versioning import versioned_api_route

from jobs import JobsManager
from jobs.exceptions import JobNotFound
from jobs.models import Job, JobMethod

jobs_router_v2 = APIRouter(
    prefix="/jobs",
    tags=["jobs_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


def jobs_to_http_exception(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(endpoint)
    async def wrapper(*args: Tuple[Any], **kwargs: dict[str, Any]) -> Any:
        try:
            return await endpoint(*args, **kwargs)
        except JobNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return wrapper


@jobs_router_v2.post("/{route:path}", status_code=status.HTTP_202_ACCEPTED)
@jobs_to_http_exception
async def create(
    route: str, body: dict[str, Any] = Body(...), method: JobMethod = JobMethod.POST, retries: int = 5
) -> Job:
    job = Job(id=str(uuid.uuid4()), route=route, method=method, body=body, retries=retries)
    JobsManager.add(job)
    return job


@jobs_router_v2.get("/", status_code=status.HTTP_200_OK)
@jobs_to_http_exception
async def fetch() -> List[Job]:
    return JobsManager.get()


@jobs_router_v2.get("/{identifier}", status_code=status.HTTP_200_OK)
@jobs_to_http_exception
async def fetch_by_identifier(identifier: str) -> Job:
    return JobsManager.get_by_identifier(identifier)


@jobs_router_v2.delete("/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
@jobs_to_http_exception
async def delete(identifier: str) -> None:
    JobsManager.delete(identifier)
