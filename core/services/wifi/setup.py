#!/usr/bin/env python3

import os
import urllib.request

import setuptools


def download_script(url: str, dest: str) -> None:
    urllib.request.urlretrieve(url, dest)
    os.chmod(dest, 0o755)


download_script(
    "https://raw.githubusercontent.com/lakinduakash/linux-wifi-hotspot/refs/heads/master/src/scripts/create_ap",
    "/usr/bin/create_ap",
)

setuptools.setup(
    name="wifi_service",
    version="0.1.0",
    description="Wifi manager for wpa_supplicant",
    license="MIT",
    py_modules=[],
    install_requires=[
        "aiofiles == 0.6.0",
        "commonwealth == 0.1.0",
        "fastapi == 0.105.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "starlette == 0.27.0",
        "tabulate == 0.8.9",
        "types-tabulate == 0.8.3",
        "uvicorn == 0.13.4",
    ],
)
