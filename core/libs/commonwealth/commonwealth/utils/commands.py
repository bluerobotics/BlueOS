import subprocess
from pathlib import Path
from typing import List, Optional

from loguru import logger


class KeyNotFound(Exception):
    """Raised when the SSH key is not found."""


def run_command_with_password(command: str, check: bool = True) -> "subprocess.CompletedProcess['str']":
    # attempt to run the command with sshpass
    # used as a fallback if the ssh key is not found
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
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_command_with_ssh_key(command: str, check: bool = True) -> "subprocess.CompletedProcess['str']":
    # attempt to run the command with the ssh key
    user = "pi"
    id_file = "/root/.config/.ssh/id_rsa"
    if not Path(id_file).exists():
        raise KeyNotFound

    return subprocess.run(
        [
            "sshpass",
            "ssh",
            "-i",
            id_file,
            "-o",
            "StrictHostKeyChecking=no",
            f"{user}@localhost",
            command,
        ],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_command(command: str, check: bool = True, log_output: bool = True) -> "subprocess.CompletedProcess['str']":
    # runs the given command on the host computer.
    # we first try with the ssh key, which is the default behavior.
    # we need to fallback to sshpass as some systems will try to call this function before the ssh key is generated.
    # this is the case for the first boot of this image after updating.
    # not including the sshpass step causes blueos_startup_update to fail hard. crashing BlueOS as a whole.
    try:
        ret = run_command_with_ssh_key(command, check)
    except Exception as error:
        logger.warning(f"Failed to run command with SSH key. {error}, trying with sshpass:\n{command}")
        ret = run_command_with_password(command, check)
    logger.info(f"Host: '{command}' : returned {ret.returncode}")
    if not log_output:
        return ret
    if ret.stdout:
        logger.info(f"stdout: {ret.stdout}")
    if ret.stderr:
        logger.error(f"stderr: {ret.stderr}")
    return ret


def upload_file_with_password(
    source: str, destination: str, check: bool = True
) -> "subprocess.CompletedProcess['str']":
    # attempt to upload the file with sshpass
    # used as a fallback if the ssh key is not found
    user = "pi"
    password = "raspberry"

    return subprocess.run(
        [
            "sshpass",
            "-p",
            password,
            "scp",
            source,
            f"{user}@localhost:{destination}",
        ],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def upload_file_with_ssh_key(source: str, destination: str, check: bool = True) -> "subprocess.CompletedProcess['str']":
    # attempt to upload the file with the ssh key
    user = "pi"
    id_file = "/root/.config/.ssh/id_rsa"
    if not Path(id_file).exists():
        raise KeyNotFound

    return subprocess.run(
        [
            "scp",
            "-i",
            id_file,
            source,
            f"{user}@localhost:{destination}",
        ],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def upload_file(file_content: str, destination: str, check: bool = True) -> "subprocess.CompletedProcess['str']":
    temp_file_in_container = "/tmp/file_to_upload"
    temp_file_in_host = "/tmp/uploaded_file"
    logger.debug(f"uploading to {destination}")
    with open(temp_file_in_container, "w", encoding="utf-8") as f:
        f.write(file_content)
    try:
        ret = upload_file_with_ssh_key(temp_file_in_container, temp_file_in_host, check)
    except KeyNotFound:
        logger.warning("SSH key not found, falling back to password authentication")
        ret = upload_file_with_password(temp_file_in_container, temp_file_in_host, check)
    logger.debug(ret)
    if ret.returncode == 0:
        run_command(f"sudo mv {temp_file_in_host} {destination}")
    else:
        logger.error(f"Failed to upload file: {ret.stderr}")
    return ret


def locate_file(candidates: List[str]) -> Optional[str]:
    # first match will return
    command = f"find {' '.join(candidates)} -type f -print -quit"
    return run_command(command, False, log_output=False).stdout.strip()


def save_file(file_name: str, file_content: str, backup_identifier: str, ensure_newline: bool = True) -> None:
    if ensure_newline and not file_content.endswith("\n"):
        file_content += "\n"
    command = f'sudo cp "{file_name}" "{file_name}.{backup_identifier}.bak"'
    run_command(command, False)
    upload_file(file_content, file_name, False)
