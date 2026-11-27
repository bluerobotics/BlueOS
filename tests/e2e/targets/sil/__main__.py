import argparse
import code
import logging
import os
import subprocess
import sys

from blueos.core import BlueOS
from targets.sil.target import SilTarget

BANNER = """
BlueOS:  {url}
SSH:     sshpass -p {password} ssh -p {port} {user}@127.0.0.1

target  the running SilTarget
blueos  the BlueOS API client

Ctrl+D stops the VM"""


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m targets.sil", description="Runs BlueOS in the VM until the command or the Python prompt ends"
    )
    parser.add_argument("command", nargs="*", help="command run after --, with BLUEOS_URL set")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    target = SilTarget()
    try:
        target.up()
        os.environ["BLUEOS_URL"] = target.base_url
        console = code.InteractiveConsole({"target": target, "blueos": BlueOS(target.base_url)})
        if args.command:
            sys.exit(subprocess.call(args.command))
        banner = BANNER.format(
            url=target.base_url, password=target.ssh.password, port=target.vm_ssh_forward_port, user=target.ssh.user
        )
        console.interact(banner=banner, exitmsg="")
    finally:
        target.down()


if __name__ == "__main__":
    main()
