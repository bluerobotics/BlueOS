#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="wifi_service",
    version="0.1.0",
    description="Wifi manager for wpa_supplicant",
    license="MIT",
    install_requires=[
        "aiofiles == 0.6.0",
        "commonwealth == 0.1.0",
        "fastapi == 0.63.0",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "starlette == 0.13.6",
        "tabulate == 0.8.9",
        "types-tabulate == 0.8.3",
        "uvicorn == 0.13.4",
    ],
)
