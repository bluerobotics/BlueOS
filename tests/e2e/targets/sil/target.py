import logging
import shutil
from pathlib import Path

from blueos.core import BlueOS
from targets.sil import docker
from targets.sil.vm import disk
from targets.sil.vm.qemu import Qemu
from targets.sil.vm.ssh import Ssh
from targets.target import Target

E2E_DIR = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


class SilTarget(Target):
    name = "sil"
    ssh_port = 2222
    http_port = 8080
    required_tools = ("docker", "qemu-img", "qemu-system-x86_64", "ssh", "sshpass")

    def __init__(self) -> None:
        super().__init__()
        if missing := [tool for tool in self.required_tools if not shutil.which(tool)]:
            raise RuntimeError(f"the sil target needs {', '.join(missing)} installed")
        self.run_dir = E2E_DIR / ".run"
        self.run_dir.mkdir(exist_ok=True)
        base = disk.base_image(E2E_DIR / ".cache")
        self.qemu = Qemu(self.run_dir, disk.overlay(base, self.run_dir / "disk.qcow2"), self.ssh_port, self.http_port)
        self.ssh = Ssh(self.ssh_port)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.http_port}"

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
