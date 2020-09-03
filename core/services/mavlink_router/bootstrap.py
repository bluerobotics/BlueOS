#!/usr/bin/env python3

import os
import sys

CLONE_PATH = os.path.realpath("/tmp")
SERVICE_PATH = os.path.dirname(os.path.realpath(__file__))
MAVLINK_ROUTER_PATH = os.path.join(CLONE_PATH, "mavlink-router")
MAVLINK_INSTALL_PATH = os.path.join(SERVICE_PATH, "install")


def set_directory(path: str) -> None:
    print(f"Changing directory to: {path}")
    os.chdir(path)


def get_project_name() -> str:
    return os.path.basename(os.path.dirname(os.path.realpath(__file__)))


def run_command(command: str) -> None:
    print(f"Running command: {command}")
    return_code = os.system(command)
    if return_code:
        print("FAILED")
        sys.exit(1)
    print("Done")


def run_apt_install(package: str) -> None:
    # No interaction is necessary since there is packages that'll be installed
    # like tzdata, that'll ask for user input
    run_command(f"DEBIAN_FRONTEND=noninteractive apt --yes install {package}")


print("Starting..")
run_apt_install("autoconf g++ git libtool make pkg-config python3-future")

set_directory(SERVICE_PATH)
if not os.path.exists(MAVLINK_ROUTER_PATH):
    run_command(f"git clone --depth 1 --branch v2 https://github.com/intel/mavlink-router {MAVLINK_ROUTER_PATH}")

set_directory(MAVLINK_ROUTER_PATH)
run_command("git submodule update --init --recursive --quiet")
run_command("./autogen.sh")
run_command(
    " ".join(
        [
            "./configure",
            "--disable-systemd",
            "CFLAGS='-g -O2'",
            "--sysconfdir=/etc",
            "--localstatedir=/var",
            "--libdir=/usr/lib64",
            "--prefix=/usr",
        ]
    )
)
run_command(f"make DESTDIR={MAVLINK_INSTALL_PATH} install -j{os.cpu_count()}")

set_directory(SERVICE_PATH)
run_command("./run --version")
print(f"Finished to build {get_project_name()}!")
