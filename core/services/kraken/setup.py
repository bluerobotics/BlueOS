#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="Kraken",
    version="0.1.0",
    description="Manages BlueOS extensions",
    license="MIT",
    py_modules=[],
    install_requires=[
        "semver == 3.0.2",
        "aiodocker == 0.21.0",
        "aiocache == 0.12.2",
        "appdirs == 1.4.4",
        "commonwealth == 0.1.0",
        "fastapi == 0.105.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "psutil == 5.7.2",
        "uvicorn == 0.13.4",
        "dataclass-wizard == 0.22.3",
    ],
)
