import logging
import shutil
import socket
import tempfile
from pathlib import Path

from blueos.core import BlueOS
from targets.sil import docker
from targets.sil.vm.qemu import Qemu
from targets.sil.vm.ssh import Ssh
from targets.target import Target

E2E_DIR = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class SilTarget(Target):
    name = "sil"
    required_tools = ("docker", "qemu-system-x86_64", "ssh", "sshpass")

    def __init__(self) -> None:
        super().__init__()
        if missing := [tool for tool in self.required_tools if not shutil.which(tool)]:
            raise RuntimeError(f"the sil target needs {', '.join(missing)} installed")
        (E2E_DIR / ".run").mkdir(exist_ok=True)
        self.run_dir = Path(tempfile.mkdtemp(prefix="", dir=E2E_DIR / ".run"))
        self.vm_ssh_forward_port = free_port()
        self.vm_http_forward_port = free_port()
        self.qemu = Qemu(
            self.run_dir,
            E2E_DIR / ".cache" / "sil.qcow2",
            self.vm_ssh_forward_port,
            self.vm_http_forward_port,
        )
        self.ssh = Ssh(self.vm_ssh_forward_port)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.vm_http_forward_port}"

    def up(self) -> None:
        logger.debug("starting vm")
        self.qemu.start()
        self.ssh.wait_ready()
        docker.start_blueos(self.ssh, self.run_dir)
        logger.debug("waiting for blueos")
        BlueOS(self.base_url).wait_ready()

    def down(self) -> None:
        logger.debug("stopping vm")
        self.qemu.stop()

    def shell(self, command: str) -> str:
        return self.ssh.run(command)
