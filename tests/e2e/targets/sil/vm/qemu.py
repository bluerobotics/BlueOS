import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path


class Qemu:
    def __init__(self, run_dir: Path, disk: Path, ssh_port: int, http_port: int) -> None:
        self.pidfile = run_dir / "qemu.pid"
        self.serial_log = run_dir / "serial.log"
        self.args = [
            "-smp",
            "4",
            "-m",
            "3G",
            "-display",
            "none",
            "-daemonize",
            "-pidfile",
            str(self.pidfile),
            "-serial",
            f"file:{self.serial_log}",
        ]
        if os.access("/dev/kvm", os.W_OK):
            self.args += ["-enable-kvm", "-cpu", "host"]
        self.args += [
            "-drive",
            f"file={disk},if=virtio",
            "-netdev",
            f"user,id=n0,hostfwd=tcp:127.0.0.1:{ssh_port}-:22,hostfwd=tcp:127.0.0.1:{http_port}-:80",
            "-device",
            "virtio-net-pci,netdev=n0",
        ]

    def start(self) -> None:
        # A previous run that was killed leaves its vm behind, holding the ports and the pid file
        self.stop()
        result = subprocess.run(["qemu-system-x86_64", *self.args], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"qemu failed to start: {result.stderr.strip()}")

    def stop(self) -> None:
        if not self.pidfile.exists():
            return
        pid = int(self.pidfile.read_text())
        # The pid may have been reused by an unrelated process since the vm died
        if self._is_qemu(pid):
            os.kill(pid, signal.SIGTERM)
            while self._is_qemu(pid):
                time.sleep(0.1)
        self.pidfile.unlink(missing_ok=True)

    @staticmethod
    def _is_qemu(pid: int) -> bool:
        with contextlib.suppress(OSError):
            return b"qemu-system" in Path(f"/proc/{pid}/cmdline").read_bytes()
        return False
