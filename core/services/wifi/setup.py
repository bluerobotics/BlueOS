#!/usr/bin/env python3

import os
import ssl

from setuptools import setup

# Ignore ssl if it fails
if not os.environ.get("PYTHONHTTPSVERIFY", "") and getattr(ssl, "_create_unverified_context", None):
    ssl._create_default_https_context = ssl._create_unverified_context

setup(
    name="wifi_service",
    version="0.1.0",
    description="Wifi manager for wpa_supplicant",
    license="MIT",
    install_requires=[
        "starlette == 0.13.6",
        "fastapi == 0.63.0",
        "uvicorn == 0.13.4",
        "aiofiles == 0.6.0",
        "fastapi-versioning == 0.9.0",
    ],
)
