#!/usr/bin/env python3

import os
import ssl

from setuptools import setup

# Ignore ssl if it fails
if not os.environ.get("PYTHONHTTPSVERIFY", "") and getattr(ssl, "_create_unverified_context", None):
    ssl._create_default_https_context = ssl._create_unverified_context

setup(
    name="helper_service",
    version="0.1.0",
    description="Helper information for development",
    license="MIT",
    install_requires=[
        "bottle == 0.12.19",
        "psutil == 5.7.2",
        "beautifulsoup4 == 4.9.3",
    ],
)
