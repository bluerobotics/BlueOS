#! /usr/bin/env python3
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict

import appdirs
import dpath
from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.events import events
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi import Path as FastPath
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from pydantic import BaseModel
from uvicorn import Config, Server

SERVICE_NAME = "bag-of-holding"
FILE_PATH = Path(appdirs.user_config_dir(SERVICE_NAME, "db.json"))

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)
events.publish_start()

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


def read_db() -> Any:
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Database not found")
    except json.decoder.JSONDecodeError as exception:
        logger.error(f"Failed to parse json in database file: {exception}")
    except Exception as exception:
        logger.exception(exception)
    return {}


def write_db(data: Dict[str, Any]) -> None:
    # Just to be sure that we'll be able to load it later
    json_string = json.dumps(data)
    json.loads(json_string)

    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


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
    write_db(payload)
    return JSONResponse(content={"status": "success"})


@app.post("/set/{path:path}")
@version(1, 0)
async def write_data(
    path: str = FastPath(..., pattern=r"^.*$"),
    payload: Any = Depends(parse_nullable_body),
) -> JSONResponse:
    logger.debug(f"Write path: {path}, {json.dumps(payload)}")
    current_data = read_db()
    dpath.new(current_data, path, payload)
    write_db(current_data)
    return JSONResponse(content={"status": "success"})


@app.get("/get/{path:path}")
@version(1, 0)
async def read_data(path: str) -> JSONResponse:
    logger.debug(f"Get path: {path}")
    current_data = read_db()

    if path == "*":
        return JSONResponse(current_data)

    try:
        result = dpath.get(current_data, path)
        return JSONResponse(result)
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid path") from KeyError


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

    # Publish running event when service is ready
    events.publish_running()
    events.publish_health("ready", {"port": 9101})

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
