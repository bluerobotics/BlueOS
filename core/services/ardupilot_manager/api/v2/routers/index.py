from fastapi import APIRouter, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import versioned_api_route

index_router_v2 = APIRouter(
    tags=["index_v2"],
    route_class=versioned_api_route(2, 0),
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@index_router_v2.get("/", status_code=status.HTTP_200_OK)
async def root_v2() -> HTMLResponse:
    html_content = """
    <html>
        <head>
            <title>ArduPilot Manager</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
