#!/usr/bin/env python3

import os
import signal
import sys

import docker
from loguru import logger

from bootstrap.bootstrap import Bootstrapper

if __name__ == "__main__":
    version = os.environ.get("GIT_DESCRIBE_TAGS", None)
    logger.add("/var/logs/blueos/services/bootstrap/bootstrap_{time}.log", enqueue=True, rotation="30 minutes")
    logger.info(f"Running BlueOS Bootstrap {version}")
    if os.environ.get("BLUEOS_CONFIG_PATH", None) is None:
        logger.info("Please supply the host path for the config files as the BLUEOS_CONFIG_PATH environment variable.")
        logger.info("Example docker command line:")
        logger.info(
            "docker run -it --network=host"
            " -v /var/run/docker.sock:/var/run/docker.sock"
            " -v $HOME/.config/blueos:/root/.config/blueos"
            " -v /var/logs/blueos:/var/logs/blueos"
            " /root/.config/blueos -e BLUEOS_CONFIG_PATH=$HOME/.config/blueos"
            " bluerobotics/blueos-bootstrap:master"
        )
        sys.exit(1)

    # As PID 1 the default SIGTERM action is ignored, so docker waited 10s to kill us on every shutdown
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    bootstrapper = Bootstrapper(docker.client.from_env())
    bootstrapper.run()
