#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="Commander",
    version="0.1.0",
    description="Allow the usage of simple commands from the frontend.",
    license="MIT",
    install_requires=[
        "appdirs == 1.4.4",
        "commonwealth == 0.1.0",
        "fastapi == 0.63.0",
        "fastapi-offline == 1.5.2",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "uvicorn == 0.13.4",
    ],
)
