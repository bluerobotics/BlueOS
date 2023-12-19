#!/usr/bin/env python3

from setuptools import setup

setup(
    name="versionchooser_service",
    version="0.1.0",
    description="Blue Robotics Ardusub BlueOS Version Chooser",
    license="MIT",
    py_modules=[],
    install_requires=[
        "aiodocker == 0.21.0",
        "aiohttp == 3.7.4",
        "aiohttp-jinja2 == 1.4.2",
        "appdirs == 1.4.4",
        "asyncmock == 0.4.2",
        "attrs == 20.3.0",
        "commonwealth == 0.1.0",
        "connexion[swagger-ui, aiohttp] == 2.14.2",
        "docker == 5.0.3",
        "itsdangerous == 2.1.1",
        "jinja2 == 3.0.3",
        "jsonschema == 3.2.0",
        "loguru == 0.5.3",
        "pyrsistent == 0.16.0",
        "pytest-asyncio == 0.14.0",
        "werkzeug == 2.2.3",
    ],
)
