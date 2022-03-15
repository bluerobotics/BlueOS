#! /usr/bin/env python3
import logging
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any

import appdirs
import uvicorn
from commonwealth.utils.logs import InterceptHandler, get_new_log_path
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger

SERVICE_NAME = "commander"

logging.basicConfig(handlers=[InterceptHandler()], level=0)
logger.add(get_new_log_path(SERVICE_NAME))

app = FastAPI(
    title="Commander API",
    description="Commander is a Companion service responsible to abstract simple commands to the frontend.",
)
logger.info("Starting Commander!")


class ShutdownType(str, Enum):
    """Valid shutdown types.
    For more information: https://www.kernel.org/doc/html/latest/admin-guide/sysrq.html#what-are-the-command-keys
    """

    REBOOT = "reboot"
    POWEROFF = "poweroff"


def run_command(command: str) -> "subprocess.CompletedProcess['bytes']":
    user = "pi"
    password = "raspberry"

    return subprocess.run(
        [
            "sshpass",
            "-p",
            password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            f"{user}@localhost",
            command,
        ],
        check=True,
    )


def check_what_i_am_doing(i_know_what_i_am_doing: bool = False) -> None:
    if not i_know_what_i_am_doing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Developer, you don't know what you are doing, command aborted.",
        )


# TODO: Update commander to work with openapi modules and improve modularity and code organization
@app.post("/shutdown", status_code=status.HTTP_200_OK)
@version(1, 0)
async def shutdown(response: Response, shutdown_type: ShutdownType, i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)

    try:
        hold_time_seconds = 5
        if shutdown_type == ShutdownType.REBOOT:
            output = run_command(f"(sleep {hold_time_seconds}; sudo shutdown --reboot -h now)&")
            logger.debug(f"reboot: {output}")
        elif shutdown_type == ShutdownType.POWEROFF:
            output = run_command(f"(sleep {hold_time_seconds}; sudo shutdown --poweroff -h now)&")
            logger.debug(f"shutdown: {output}")

        return HTMLResponse(status_code=200)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.exception(error)
        return {"message": f"{error}"}


@app.post("/settings/reset", status_code=status.HTTP_200_OK)
@version(1, 0)
async def reset_settings(response: Response, i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)

    try:
        user_config_dir = Path(appdirs.user_config_dir())
        for item in user_config_dir.glob("*"):
            try:
                if item.is_file():
                    item.unlink()
                if item.is_dir():
                    # Delete folder and its contents
                    shutil.rmtree(item)
            except Exception as exception:
                logger.warning(f"Failed to delete: {item}, {exception}")

        return HTMLResponse(status_code=200)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.exception(error)
        return {"message": f"Could not reset user configuration, {error}"}


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)


@app.get("/")
async def root() -> Any:
    html_content = """
    <html>
        <head>
            <title>Commander</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


if __name__ == "__main__":
    # Running uvicorn with log disabled so loguru can handle it
    uvicorn.run(app, host="0.0.0.0", port=9100, log_config=None)
