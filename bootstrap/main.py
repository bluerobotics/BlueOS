#!/usr/bin/env python3

import os
import sys

import docker

from bootstrap.bootstrap import Bootstrapper

if __name__ == "__main__":
    if os.environ.get("COMPANION_CONFIG_PATH", None) is None:
        print("Please supply the host path for the config files as the COMPANION_CONFIG_PATH environment variable.")
        print("Example docker command line:")
        print(
            "docker run -it -v /var/run/docker.sock:/var/run/docker.sock -v $HOME/.config/companion:"
            "/root/.config/companion -e COMPANION_CONFIG_PATH=$HOME/.config/companion"
            "bluerobotics/companion-bootstrap:master"
        )
        sys.exit(1)

    bootstrapper = Bootstrapper(docker.client.from_env())
    bootstrapper.run()
