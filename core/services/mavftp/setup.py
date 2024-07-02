#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name="mavftp",
    version="0.1.0",
    description="mavftp client with fuse filesystem",
    license="MIT",
    py_modules=[],
    install_requires=[
        "pymavlink == 2.4.41",
        "loguru == 0.5.3",
        "fusepy == 3.0.1",
    ],
)
