#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="Beacon",
    version="0.1.0",
    description="Mdns service",
    license="MIT",
    py_modules=[],
    install_requires=[
        "commonwealth == 0.1.0",
        "loguru == 0.5.3",
        "zeroconf==0.38.4",
        "uvicorn == 0.13.4",
    ],
)
