#!/usr/bin/env python3

from setuptools import setup

setup(
    name="blueos_bootstrap",
    version="0.0.1",
    description="Blue Robotics Ardusub BlueOS Docker System Bootstrap",
    license="MIT",
    py_modules=[],
    install_requires=[
        "docker==5.0.0",
        "loguru==0.5.3",
        "requests==2.26.0",
        # indirect dependencies
        "six==1.15.0",
        "idna==3.4",
        "urllib3==1.26.16",
        "certifi==2023.7.22",
        "charset-normalizer==2.0.12",
        "websocket-client==1.6.3",
    ],
)
