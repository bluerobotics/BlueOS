#!/usr/bin/env python3
import setuptools

with open("README.md", "r", encoding="utf-8") as readme:
    long_description = readme.read()

setuptools.setup(
    name="nmea-injector",
    version="0.0.1",
    author="Rafael Araujo Lehmkuhl",
    author_email="rafael@bluerobotics.com",
    description="BlueOS NMEA Injector.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "appdirs == 1.4.4",
        "commonwealth == 0.1.0",
        "fastapi == 0.105.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "pynmea2 == 1.18.0",
        "pytest-mock==3.10.0",
        "starlette == 0.27.0",
        "uvicorn == 0.13.4",
        "validators == 0.18.2",
    ],
)
