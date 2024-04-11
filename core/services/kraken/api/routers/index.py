# FastAPI
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, Response
# Kraken
from kraken import Kraken

# Creates Root Kraken router
kraken_router = APIRouter(
    responses={
        404: {"description": "Not found"}
    },
)

# Endpoints

@kraken_router.get("/", response_class=RedirectResponse, status_code=200)
async def root() -> Response:
    """
    Root endpoint for the Kraken API.

    Returns:
    - RedirectResponse: Redirects to the root.html page.
    """

    return RedirectResponse(url="/static/pages/root.html")


@kraken_router.get("/log", response_class=RedirectResponse, status_code=200)
async def log(container_name: str) -> Response:
    """
    Get logs from current running Kraken instance.

    Returns:
    """

    return await Kraken.log(container_name)
