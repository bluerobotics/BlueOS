#!/usr/bin/env python3

import os
import sys

CLONE_PATH = os.path.realpath("/tmp")
SERVICE_PATH = os.path.dirname(os.path.realpath(__file__))
MAVLINK_ROUTER_PATH = os.path.join(CLONE_PATH, "mavlink-router")


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


def run_apt_uninstall(package: str) -> None:
    run_command(f"DEBIAN_FRONTEND=noninteractive apt --yes purge {package} ")
    # "autoremove" is actually responsible for cleaning up 193 MB
    run_command("DEBIAN_FRONTEND=noninteractive apt --yes autoremove ")


print("Starting..")
run_apt_install("autoconf g++ git libtool make pkg-config")
run_command("pip install future==0.18.2")

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
run_command(f"make install -j{os.cpu_count()}")
run_command(f"rm -rf {MAVLINK_ROUTER_PATH}")

set_directory(SERVICE_PATH)
run_command("mavlink-routerd --version")
print("Cleaning up...")
run_apt_uninstall("autoconf g++ git libtool make pkg-config python3-future")
print(f"Finished to build {get_project_name()}!")
