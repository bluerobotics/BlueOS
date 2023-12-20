#!/usr/bin/env python3

from setuptools import setup

setup(
    name="helper_service",
    version="0.1.0",
    description="Helper information for development",
    license="MIT",
    py_modules=[],
    install_requires=[
        "aiofiles == 0.6.0",
        "beautifulsoup4 == 4.9.3",
        "commonwealth == 0.1.0",
        "fastapi == 0.105.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "psutil == 5.7.2",
        "requests == 2.25.1",
        "speedtest-cli == 2.1.3",
        "starlette == 0.27.0",
        "uvicorn == 0.13.4",
    ],
)
