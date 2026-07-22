from typing import Any

from commonwealth.service.service import Service
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi import Path as FastPath
from fastapi.responses import JSONResponse
from fastapi_versioning import version
from service import BagOfHoldingState


async def parse_nullable_body(payload: Any | None = Body(None)) -> Any:
    return payload


def build_bag_router(service: Service[BagOfHoldingState]) -> APIRouter:
    router = APIRouter()

    @router.post("/overwrite")
    async def overwrite_data(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        with service.write() as state:
            state.overwrite(payload)

        return JSONResponse(content={"status": "success"})

    @router.post("/set/{path:path}")
    @version(1, 0)
    async def write_data(
        path: str = FastPath(..., pattern=r"^.*$"),
        payload: Any = Depends(parse_nullable_body),
    ) -> JSONResponse:
        try:
            with service.write() as state:
                state.set(path, payload)
        except KeyError:
            raise HTTPException(status_code=400, detail="Invalid path") from None

        return JSONResponse(content={"status": "success"})

    @router.get("/get/{path:path}")
    @version(1, 0)
    async def read_data(path: str) -> JSONResponse:
        try:
            with service.read() as state:
                result = state.get(path)
        except KeyError:
            raise HTTPException(status_code=400, detail="Invalid path") from None

        return JSONResponse(result)

    return router
