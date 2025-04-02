#! /usr/bin/env python3
import json
import logging
import os
import shutil
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator

import appdirs
import uvicorn
from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.commands import run_command
from commonwealth.utils.general import delete_everything, delete_everything_stream
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.streaming import streamer
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger

SERVICE_NAME = "commander"
LOG_FOLDER_PATH = os.environ.get("BLUEOS_LOG_FOLDER_PATH", "/var/logs/blueos")
MAVLINK_LOG_FOLDER_PATH = os.environ.get("BLUEOS_MAVLINK_LOG_FOLDER_PATH", "/shortcuts/ardupilot_logs/logs/")

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

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


@app.get("/raspi/vcgencmd", status_code=status.HTTP_200_OK)
@version(1, 0)
async def vcgencmd(i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    output_vl085_firmware_version = await command_host("sudo vcgencmd otp_dump", True)
    logger.debug(f"VL085 firmware version command: {output_vl085_firmware_version}")
    output_bootloader_version = await command_host("sudo vcgencmd bootloader_version", True)
    logger.debug(f"Bootloader version command output: {output_bootloader_version}")
    output_raspberry_firmware_version = await command_host("sudo vcgencmd version", True)
    logger.debug(f"RPI firmware version command output: {output_raspberry_firmware_version}")

    return {
        "vl085": output_vl085_firmware_version,
        "bootloader": output_bootloader_version,
        "firmware": output_raspberry_firmware_version,
    }


@app.get("/raspi/eeprom_update", status_code=status.HTTP_200_OK)
@version(1, 0)
async def eeprom_update(i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    return await command_host("sudo rpi-eeprom-update", True)


@app.post("/raspi/eeprom_update", status_code=status.HTTP_200_OK)
@version(1, 0)
async def do_eeprom_update(i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    return await command_host("sudo rpi-eeprom-update -a -d", True)


@app.post("/settings/reset", status_code=status.HTTP_200_OK)
@version(1, 0)
async def reset_settings(i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    # Be sure to not delete bootstrap to avoid going back to factory image
    bootstrap_config_path = "/root/.config/bootstrap/startup.json"
    temporary_location = "/tmp/bootstrap_startup.json"
    shutil.copy2(bootstrap_config_path, temporary_location)
    delete_everything(Path(appdirs.user_config_dir()))
    shutil.copy2(temporary_location, bootstrap_config_path)


@app.post("/services/remove_log", status_code=status.HTTP_200_OK)
@version(1, 0)
async def remove_log_services(i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    delete_everything(Path(LOG_FOLDER_PATH))


@app.post("/services/remove_log_stream", status_code=status.HTTP_200_OK)
@version(1, 0)
async def remove_log_services_stream(i_know_what_i_am_doing: bool = False) -> StreamingResponse:
    """Stream the deletion of log files, providing real-time updates about each file being deleted."""
    check_what_i_am_doing(i_know_what_i_am_doing)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            async for info in delete_everything_stream(Path(LOG_FOLDER_PATH)):
                yield json.dumps(info)
        except Exception as error:
            logger.error(f"Error during log deletion stream: {error}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return StreamingResponse(
        streamer(generate(), heartbeats=1.0),
        media_type="application/x-ndjson",
        headers={
            "Content-Type": "application/x-ndjson",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx
        },
    )


@app.post("/services/remove_mavlink_log", status_code=status.HTTP_200_OK)
@version(1, 0)
async def remove_mavlink_log_services(i_know_what_i_am_doing: bool = False) -> Any:
    check_what_i_am_doing(i_know_what_i_am_doing)
    delete_everything(Path(MAVLINK_LOG_FOLDER_PATH))


@app.get("/services/check_log_folder_size", status_code=status.HTTP_200_OK)
@version(1, 0)
async def check_log_folder_size() -> Any:
    log_path = Path(LOG_FOLDER_PATH)
    # Return the total size in bytes
    return sum(file.stat().st_size for file in log_path.glob("**/*") if file.is_file())


@app.get("/services/check_mavlink_log_folder_size", status_code=status.HTTP_200_OK)
@version(1, 0)
async def check_mavlink_log_folder_size() -> Any:
    log_path = Path(MAVLINK_LOG_FOLDER_PATH)
    # Return the total size in bytes
    return sum(file.stat().st_size for file in log_path.glob("**/*") if file.is_file())


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


def setup_ssh() -> None:
    # store the key in the docker .config volume
    key_path = Path("/root/.config/.ssh")
    private_key = key_path / "id_rsa"
    public_key = private_key.with_suffix(".pub")
    user = os.environ.get("SSH_USER", "pi")
    gid = int(os.environ.get("USER_GID", 1000))
    uid = int(os.environ.get("USER_UID", 1000))
    authorized_keys = Path(f"/home/{user}/.ssh/authorized_keys")

    try:
        key_path.mkdir(parents=True, exist_ok=True)
        # check if id_rsa.pub exists, creates a new one if it doesnt
        if not public_key.is_file():
            subprocess.run(["ssh-keygen", "-t", "rsa", "-f", private_key, "-q", "-N", ""], check=True)
        public_key_text = public_key.read_text("utf-8")
        # add id_rsa.pub to authorized_keys if not there already
        try:
            authorized_keys_text = authorized_keys.read_text("utf-8")
        except FileNotFoundError:
            logger.info(f"File does not exist: {authorized_keys}")
            authorized_keys_text = ""

        if public_key_text not in authorized_keys_text:
            if not authorized_keys_text.endswith("\n"):
                authorized_keys_text += "\n"
            authorized_keys_text += public_key_text
            authorized_keys.write_text(authorized_keys_text, "utf-8")

        os.chown(authorized_keys, uid, gid)
        authorized_keys.chmod(0o600)
    except Exception as error:
        logger.error(f"Error setting up ssh: {error}")
    logger.info("SSH setup done")


if __name__ == "__main__":
    setup_ssh()
    # Register ssh client and remove message from the following commands
    run_command("ls")

    # Running uvicorn with log disabled so loguru can handle it
    uvicorn.run(app, host="0.0.0.0", port=9100, log_config=None)
