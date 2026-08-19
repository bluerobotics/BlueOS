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
from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi import Path as FastPath
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from uvicorn import Config, Server

SERVICE_NAME = "bag-of-holding"
FILE_PATH = Path(appdirs.user_config_dir(SERVICE_NAME, "db.json"))
FLUSH_INTERVAL = 1.0

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)


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


app = FastAPI(
    title="Bag of Holding API",
    description=(
        "Bag of Holding implements a FastAPI service with versioning that provides a simple key-value"
        "storage API, enabling the user to store and retrieve data as JSON objects through HTTP requests."
    ),
)
app.router.route_class = GenericErrorHandlingRoute
logger.info(f"Starting Bag of Holding: {FILE_PATH}")


async def parse_nullable_body(payload: Any | None = Body(None)) -> Any:
    return payload


@app.post("/overwrite")
@version(1, 0)
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


async def main() -> None:
    await init_sentry_async(SERVICE_NAME)

    # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, host="0.0.0.0", port=9101, log_config=None)
    server = Server(config)

    try:
        await server.serve()
    finally:
        flush_now()


if __name__ == "__main__":
    asyncio.run(main())
