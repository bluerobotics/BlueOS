import subprocess
from pathlib import Path

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
    id_file = f"/home/{user}/.ssh/id_rsa"
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


def run_command(command: str, check: bool = True) -> "subprocess.CompletedProcess['str']":
    # runs the given command on the host computer.
    # we first try with the ssh key, which is the default behavior.
    # we need to fallback to sshpass as some systems will try to call this function before the ssh key is generated.
    # this is the case for the first boot of this image after updating.
    # not including the sshpass step causes blueos_startup_update to fail hard. crashing BlueOS as a whole.
    try:
        return run_command_with_ssh_key(command, check)
    except Exception as error:
        logger.warning(f"Failed to run command with SSH key. {error}, trying with sshpass:\n{command}")
        return run_command_with_password(command, check)
