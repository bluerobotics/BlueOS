#!/usr/bin/env python3

import os
import ssl

from setuptools import setup

# Ignore ssl if it fails
if not os.environ.get("PYTHONHTTPSVERIFY", "") and getattr(ssl, "_create_unverified_context", None):
    ssl._create_default_https_context = ssl._create_unverified_context

setup(
    name="ping_service",
    version="0.2.0",
    description="Ping service for BlueRobotics' Ping1D and Pìng360",
    license="MIT",
    py_modules=[],
    install_requires=[
        "bluerobotics-ping == 0.1.5",
        "bridges == 0.1.0",
        "commonwealth == 0.1.0",
        "fastapi == 0.105.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "pyserial == 3.5",
        "starlette == 0.27.0",
        "uvicorn == 0.13.4",
    ],
)
