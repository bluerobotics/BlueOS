#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="Bag of Holding",
    version="0.1.0",
    description="Allow the persistence of arbitrary data in a Blue Robotics BlueOS system",
    license="MIT",
    install_requires=[
        "appdirs == 1.4.4",
        "commonwealth == 0.1.0",
        "fastapi == 0.105.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "uvicorn == 0.13.4",
        "dpath == 2.1.5",
    ],
)
