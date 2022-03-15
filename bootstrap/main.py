#!/usr/bin/env python3

import os
import sys

import docker

from bootstrap.bootstrap import Bootstrapper

if __name__ == "__main__":
    if os.environ.get("BLUEOS_CONFIG_PATH", None) is None:
        print("Please supply the host path for the config files as the BLUEOS_CONFIG_PATH environment variable.")
        print("Example docker command line:")
        print(
            "docker run -it -v /var/run/docker.sock:/var/run/docker.sock -v $HOME/.config/blueos:"
            "/root/.config/blueos -e BLUEOS_CONFIG_PATH=$HOME/.config/blueos"
            "bluerobotics/blueos-bootstrap:master"
        )
        sys.exit(1)

    bootstrapper = Bootstrapper(docker.client.from_env())
    bootstrapper.run()
