import subprocess
from pathlib import Path

BUILD_SCRIPT = "targets/sil/image/build.sh"


def base_image(cache: Path) -> Path:
    path = cache / "sil.qcow2"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found, build it first with {BUILD_SCRIPT}")
    return path


def overlay(base: Path, path: Path, size: str = "8G") -> Path:
    path.unlink(missing_ok=True)
    subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", "-b", str(base), "-F", "qcow2", path, size], check=True)
    return path
