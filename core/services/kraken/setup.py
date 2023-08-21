#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="Kraken",
    version="0.1.0",
    description="Manages BlueOS extensions",
    license="MIT",
    install_requires=[
        "aiodocker == 0.21.0",
        "appdirs == 1.4.4",
        "commonwealth == 0.1.0",
        "fastapi == 0.101.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "uvicorn == 0.13.4",
    ],
)
