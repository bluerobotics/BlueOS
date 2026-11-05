import code
import logging

from targets.sil.target import SilTarget

BANNER = """
BlueOS:  {url}
SSH:     sshpass -p {password} ssh -p {port} {user}@127.0.0.1

target  the running SilTarget

Ctrl+D stops the VM"""


def main() -> None:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    target = SilTarget()
    target.up()
    banner = BANNER.format(
        url=target.base_url, password=target.ssh.password, port=target.ssh_port, user=target.ssh.user
    )
    try:
        code.interact(banner=banner, local={"target": target}, exitmsg="")
    finally:
        target.down()


if __name__ == "__main__":
    main()
