#!/usr/bin/env python3

import pathlib
import ssl
import sys
import time
import urllib.request
from collections import namedtuple
from warnings import warn

import setuptools

from settings import Settings

ssl._create_default_https_context = ssl._create_unverified_context


autopilot_settings = Settings()
defaults_folder = autopilot_settings.defaults_folder

StaticFile = namedtuple("StaticFile", "parent filename url")

static_files = [
    StaticFile(
        defaults_folder,
        "ardupilot_navigator",
        "https://firmware.ardupilot.org/Sub/stable-4.1.2/navigator/ardusub",
    ),
    StaticFile(defaults_folder, "ardupilot_pixhawk1", "https://firmware.ardupilot.org/Sub/latest/Pixhawk1/ardusub.apj"),
    StaticFile(defaults_folder, "ardupilot_pixhawk4", "https://firmware.ardupilot.org/Sub/latest/Pixhawk4/ardusub.apj"),
]

for file in static_files:
    path = pathlib.Path.joinpath(file.parent, file.filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    number_of_attempts = 0
    while number_of_attempts < 5:
        number_of_attempts += 1
        try:
            urllib.request.urlretrieve(file.url, path)
            break
        except Exception as error:
            warn(f"unable to open url {file.url}, error {error}")
        time.sleep(5)
    else:
        sys.exit(1)


with open("README.md", "r", encoding="utf-8") as readme:
    long_description = readme.read()

setuptools.setup(
    name="ardupilot-manager",
    version="0.0.1",
    author="Patrick José Pereira",
    author_email="patrick@bluerobotics.com",
    description="ArduPilot service manager.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "appdirs == 1.4.4",
        "packaging == 20.4",
        "smbus2 == 0.3.0",
        "starlette == 0.27.0",
        "fastapi == 0.105.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "uvicorn == 0.13.4",
        "python-multipart == 0.0.5",
        "validators == 0.18.2",
        "fastapi-versioning == 0.9.1",
        "aiofiles == 0.6.0",
        "loguru == 0.5.3",
        "commonwealth == 0.1.0",
        "pyelftools == 0.30",
        "psutil == 5.7.2",
        "pyserial == 3.5",
        "pydantic == 1.10.12",
    ],
)
