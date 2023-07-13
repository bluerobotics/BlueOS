#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="log_zipper",
    version="0.1.0",
    description="logrotate but better",
    license="MIT",
    install_requires=[
        "commonwealth == 0.1.0",
        "loguru == 0.5.3",
    ],
)
