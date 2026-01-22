#! /usr/bin/env python3
import asyncio
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import appdirs
import dpath
import uvicorn
from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.logs import InterceptHandler, init_logger
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi import Path as FastPath
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from pydantic import BaseModel

SERVICE_NAME = "bag-of-holding"
FILE_PATH = Path(appdirs.user_config_dir(SERVICE_NAME, "db.json"))
FLUSH_INTERVAL = 1.0

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

app = FastAPI(
    title="Bag of Holding API",
    description=(
        "Bag of Holding implements a FastAPI service with versioning that provides a simple key-value"
        "storage API, enabling the user to store and retrieve data as JSON objects through HTTP requests."
    ),
)
app.router.route_class = GenericErrorHandlingRoute
logger.info(f"Starting Bag of Holding: {FILE_PATH}")


class KeyValue(BaseModel):
    key: str
    value: Any


def read_db() -> dict[str, Any]:
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
            logger.error("Database file is not an object")
    except FileNotFoundError:
        logger.error("Database not found")
    except json.decoder.JSONDecodeError as exception:
        logger.error(f"Failed to parse json in database file: {exception}")
    except Exception as exception:
        logger.exception(exception)
    return {}


def write_db() -> None:
    FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_file = FILE_PATH.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as handle:
        json.dump(bag_of_holding_db, handle)
        handle.flush()
        os.fsync(handle.fileno())
    temp_file.replace(FILE_PATH)


bag_of_holding_db = read_db()
_pending = SimpleNamespace(handle=None)


def mark_dirty() -> None:
    if _pending.handle is not None:
        return
    _pending.handle = asyncio.get_running_loop().call_later(FLUSH_INTERVAL, _flush)


def _flush() -> None:
    try:
        write_db()
        _pending.handle = None
    except Exception:
        logger.exception("Failed to persist database")
        _pending.handle = asyncio.get_running_loop().call_later(FLUSH_INTERVAL, _flush)


def flush_now() -> None:
    if _pending.handle is not None:
        _pending.handle.cancel()
        _pending.handle = None
    write_db()


async def parse_nullable_body(request: Request) -> Any:
    body = await request.body()
    if not body:
        return None

    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e


@app.post("/overwrite")
async def overwrite_data(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    logger.debug(f"Overwrite: {json.dumps(payload)}")
    bag_of_holding_db.clear()
    bag_of_holding_db.update(payload)
    flush_now()
    return JSONResponse(content={"status": "success"})


@app.post("/set/{path:path}")
@version(1, 0)
async def write_data(
    path: str = FastPath(..., pattern=r"^.*$"),
    payload: Any = Depends(parse_nullable_body),
) -> JSONResponse:
    logger.debug(f"Write path: {path}, {json.dumps(payload)}")
    dpath.new(bag_of_holding_db, path, payload)
    mark_dirty()
    return JSONResponse(content={"status": "success"})


@app.get("/get/{path:path}")
@version(1, 0)
async def read_data(path: str) -> JSONResponse:
    logger.debug(f"Get path: {path}")

    if path == "*":
        return JSONResponse(bag_of_holding_db)

    try:
        result = dpath.get(bag_of_holding_db, path)
        return JSONResponse(result)
    except KeyError as error:
        raise HTTPException(status_code=400, detail="Invalid path") from error


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)


@app.get("/")
async def root() -> HTMLResponse:
    html_content = """
    <html>
        <head>
            <title>Bag Of Holding</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


if __name__ == "__main__":
    try:
        # Running uvicorn with log disabled so loguru can handle it
        uvicorn.run(app, host="0.0.0.0", port=9101, log_config=None)
    finally:
        flush_now()
