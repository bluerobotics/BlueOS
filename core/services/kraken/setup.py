#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="Kraken",
    version="0.1.0",
    description="Manages BlueOS extensions",
    license="MIT",
    py_modules=[],
    install_requires=[
        "aiodocker == 0.21.0",
        "appdirs == 1.4.4",
        "commonwealth == 0.1.0",
        "fastapi == 0.110.1",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 4.3.0",
        "fastapi-versioning == 0.10.0",
        "loguru == 0.7.2",
        "psutil == 5.9.8",
        "uvicorn == 0.29.0",
        "dataclass-wizard == 0.22.3",
    ],
)
