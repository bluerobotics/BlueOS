import json
import logging
import subprocess
from pathlib import Path

from images import BOOTSTRAP, CORE
from targets.sil.vm.ssh import Ssh
from utils.retry import wait_until

STARTUP_JSON = Path(__file__).resolve().parents[4] / "bootstrap" / "startup.json.default"
CONFIG_DIR = "/root/.config/blueos"
logger = logging.getLogger(__name__)


def startup_json(run_dir: Path) -> Path:
    config = json.loads(STARTUP_JSON.read_text())
    image, separator, tag = CORE.rpartition(":")
    if not separator or "/" in tag:
        raise ValueError(f"E2E_CORE_IMAGE '{CORE}' needs an explicit tag, like name:tag")
    config["core"]["image"], config["core"]["tag"] = image, tag
    path = run_dir / "startup.json"
    path.write_text(json.dumps(config, indent=4))
    return path


def load(ssh: Ssh, image: str) -> None:
    logger.debug("loading %s", image)
    if subprocess.run(["docker", "image", "inspect", image], capture_output=True, check=False).returncode != 0:
        wait_until(
            lambda: subprocess.run(["docker", "pull", "-q", image], check=True, capture_output=True),
            600,
            errors=(subprocess.CalledProcessError,),
            description=f"docker pull {image}",
        )
    with subprocess.Popen(["docker", "save", image], stdout=subprocess.PIPE) as save:
        ssh.run("sudo docker load", stdin=save.stdout)
    if save.returncode != 0:
        raise RuntimeError(f"docker save {image} failed ({save.returncode})")


def start_blueos(ssh: Ssh, run_dir: Path) -> None:
    load(ssh, CORE)
    load(ssh, BOOTSTRAP)
    logger.debug("starting bootstrap")
    ssh.put(startup_json(run_dir), f"{CONFIG_DIR}/bootstrap/startup.json")
    ssh.run(
        "sudo docker run -d -t --restart unless-stopped --name blueos-bootstrap --net=host "
        f"-v {CONFIG_DIR}/bootstrap:/root/.config/bootstrap "
        "-v /var/run/docker.sock:/var/run/docker.sock -v /var/logs/blueos:/var/logs/blueos "
        f"-e BLUEOS_CONFIG_PATH={CONFIG_DIR} {BOOTSTRAP}"
    )
