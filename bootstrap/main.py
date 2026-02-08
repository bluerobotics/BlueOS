#!/usr/bin/env python3

import os
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

    bootstrapper = Bootstrapper(docker.client.from_env())
    bootstrapper.run()
