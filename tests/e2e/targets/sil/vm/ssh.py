import subprocess
from pathlib import Path
from typing import IO

from utils.retry import wait_until


class Ssh:
    def __init__(self, port: int, user: str = "pi", password: str = "raspberry") -> None:
        self.port = port
        self.user = user
        self.password = password

    def _options(self) -> list[str]:
        return [
            "-o", "PreferredAuthentications=password", "-o", "PubkeyAuthentication=no",
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=3", "-F", "/dev/null",
        ]  # fmt: skip

    def _command(self, *args: str) -> list[str]:
        return [
            "sshpass",
            "-p",
            self.password,
            "ssh",
            *self._options(),
            "-p",
            str(self.port),
            f"{self.user}@127.0.0.1",
            *args,
        ]

    def _run(self, command: str, stdin: IO[bytes] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(self._command(command), stdin=stdin, capture_output=True, text=True, check=False)

    def run(self, command: str, stdin: IO[bytes] | None = None) -> str:
        result = self._run(command, stdin)
        if result.returncode != 0:
            raise RuntimeError(f"'{command}' failed ({result.returncode}): {result.stderr.strip()}")
        return result.stdout.strip()

    def put(self, local: Path, remote: str) -> None:
        staging = f"/tmp/{local.name}"
        scp = [
            "sshpass",
            "-p",
            self.password,
            "scp",
            *self._options(),
            "-P",
            str(self.port),
            str(local),
            f"{self.user}@127.0.0.1:{staging}",
        ]
        result = subprocess.run(scp, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"put {local} failed: {result.stderr.strip()}")
        self.run(f"sudo mkdir -p $(dirname {remote}) && sudo cp {staging} {remote} && rm {staging}")

    def wait_ready(self, timeout: float = 300) -> None:
        def check() -> None:
            result = self._run("systemctl is-system-running --wait")
            if result.stdout.strip() not in ("running", "degraded"):
                raise RuntimeError(result.stderr.strip() or result.stdout.strip())

        wait_until(check, timeout, errors=(RuntimeError,), description="VM ready")
