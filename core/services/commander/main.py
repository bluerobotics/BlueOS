#! /usr/bin/env python3
import logging
import os
import shutil
import time
from enum import Enum
from pathlib import Path
from typing import Any

import appdirs
import uvicorn
from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.commands import run_command
from commonwealth.utils.logs import InterceptHandler, get_new_log_path
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger

SERVICE_NAME = "commander"
LOG_FOLDER_PATH = "/var/logs/blueos"

logging.basicConfig(handlers=[InterceptHandler()], level=0)
logger.add(get_new_log_path(SERVICE_NAME))

app = FastAPI(
    title="Commander API",
    description="Commander is a BlueOS service responsible to abstract simple commands to the frontend.",
)
app.router.route_class = GenericErrorHandlingRoute
logger.info("Starting Commander!")


class ShutdownType(str, Enum):
    """Valid shutdown types.
    For more information: https://www.kernel.org/doc/html/latest/admin-guide/sysrq.html#what-are-the-command-keys
    """

    REBOOT = "reboot"
    POWEROFF = "poweroff"


def check_what_i_am_doing(i_know_what_i_am_doing: bool = False) -> None:
    if not i_know_what_i_am_doing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Developer, you don't know what you are doing, command aborted.",
        )


def delete_everything(path: Path) -> None:
    if path.is_file():
        path.unlink()
        return

    for item in path.glob("*"):
        try:
            if item.is_file():
                item.unlink()
            if item.is_dir():
                # Delete folder and its contents
                shutil.rmtree(item)
        except Exception as exception:
            logger.warning(f"Failed to delete: {item}, {exception}")


@app.post("/command/host", status_code=status.HTTP_200_OK)
@version(1, 0)
async def command_host(command: str, i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    logger.debug(f"Running command: {command}")
    output = run_command(command, False)
    logger.debug(f"Output: {output}")
    message = {
        "stdout": f"{output.stdout!r}",
        "stderr": f"{output.stderr!r}",
        "return_code": output.returncode,
    }
    return message


@app.post("/set_time", status_code=status.HTTP_200_OK)
@version(1, 0)
async def set_time(unix_time_seconds: int, i_know_what_i_am_doing: bool = False) -> Any:
    unix_time_seconds_now = int(time.time())
    if abs(unix_time_seconds_now - unix_time_seconds) < 5 * 60:
        return {
            "message": f"External time ({unix_time_seconds}) is close to internal time ({unix_time_seconds_now})"
            ", not updating."
        }

    # It's necessary to stop ntp sync before setting time
    command = f"sudo timedatectl set-ntp false; sudo date -s '@{unix_time_seconds}'; sudo timedatectl set-ntp true"
    return await command_host(command, i_know_what_i_am_doing)


# TODO: Update commander to work with openapi modules and improve modularity and code organization
@app.post("/shutdown", status_code=status.HTTP_200_OK)
@version(1, 0)
async def shutdown(shutdown_type: ShutdownType, i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    hold_time_seconds = 5
    if shutdown_type == ShutdownType.REBOOT:
        output = run_command(f"(sleep {hold_time_seconds}; sudo reboot)&")
        logger.debug(f"reboot: {output}")
    elif shutdown_type == ShutdownType.POWEROFF:
        output = run_command(f"(sleep {hold_time_seconds}; sudo shutdown --poweroff -h now)&")
        logger.debug(f"shutdown: {output}")


@app.get("/raspi_config/camera_legacy", status_code=status.HTTP_200_OK)
@version(1, 0)
async def raspi_config_camera_legacy() -> Any:
    output = await command_host("raspi-config nonint get_legacy", True)
    logger.debug(f"raspi-config get_legacy: {output}")
    if output["return_code"] != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get legacy mode: {output}",
        )
    stdout_result = (
        bytes(output["stdout"], encoding="raw_unicode_escape").decode("unicode_escape").replace("'", "").strip()
    )
    return {"enabled": stdout_result == "0"}


@app.post("/raspi_config/camera_legacy", status_code=status.HTTP_200_OK)
@version(1, 0)
async def raspi_config_camera_legacy_set(enable: bool = True) -> Any:
    argument = "0" if enable else "1"
    output = await command_host(f"sudo raspi-config nonint do_legacy {argument}", True)
    logger.debug(f"raspi-config do_legacy: {output}")
    if output["return_code"] != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to set legacy mode: {output}",
        )

    return output


@app.post("/settings/reset", status_code=status.HTTP_200_OK)
@version(1, 0)
async def reset_settings(i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    delete_everything(Path(appdirs.user_config_dir()))


@app.post("/services/remove_log", status_code=status.HTTP_200_OK)
@version(1, 0)
async def remove_log_services(i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    delete_everything(Path(LOG_FOLDER_PATH))


@app.get("/environment_variables", status_code=status.HTTP_200_OK)
@version(1, 0)
async def environment_variables() -> Any:
    return os.environ


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
    # Register ssh client and remove message from the following commands
    run_command("ls")

    # Running uvicorn with log disabled so loguru can handle it
    uvicorn.run(app, host="0.0.0.0", port=9100, log_config=None)
