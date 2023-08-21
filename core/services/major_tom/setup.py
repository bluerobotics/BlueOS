#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="Major Tom",
    version="0.1.0",
    description="Sends telemetry back to Ground Control",
    license="MIT",
    install_requires=[
        "requests==2.31.0",
        "loguru==0.5.3",
    ],
)
