from contextlib import asynccontextmanager
from typing import AsyncGenerator

from api.v1.routers import bus, jobs_router_v1, kernel
from commonwealth.utils.apis import (
    GenericErrorHandlingRoute,
    PrettyJSONResponse,
    use_local_docs_assets,
)
from config import SERVICE_NAME
from fastapi import FastAPI, WebSocket
from fastapi_versioning import VersionedFastAPI


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:  # pylint: disable=unused-argument
    yield
    await kernel.stop()


app = FastAPI(
    title="Vehicle Setup API",
    description="Vehicle Setup is responsible for setting up the vehicle for usage.",
    default_response_class=PrettyJSONResponse,
)
app.router.route_class = GenericErrorHandlingRoute

app.include_router(jobs_router_v1)

app = VersionedFastAPI(app, prefix_format="/v{major}.{minor}", enable_latest=True, lifespan=lifespan)
use_local_docs_assets(app)


@app.get("/", status_code=200)
async def root() -> dict[str, str]:
    return {"service": SERVICE_NAME}


# VersionedFastAPI only copies HTTP routes (it reads route.methods), so the websocket lives on the outer app
@app.websocket("/ws")
async def websocket(socket: WebSocket) -> None:
    await bus.serve(socket)
