#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="Bridget",
    version="0.1.0",
    description="Manager for 'bridges' links.",
    license="MIT",
    install_requires=[
        "bridges == 0.1.0",
        "commonwealth == 0.1.0",
        "fastapi == 0.101.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "uvicorn == 0.13.4",
    ],
)
