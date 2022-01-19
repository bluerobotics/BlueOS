#!/usr/bin/env python3

import pathlib
import ssl
import sys
import urllib.request
from collections import namedtuple
from warnings import warn

import setuptools

from settings import Settings

ssl._create_default_https_context = ssl._create_unverified_context


current_folder = pathlib.Path(__file__).parent.absolute()
frontend_folder = pathlib.Path.joinpath(current_folder, "frontend")
static_folder = pathlib.Path.joinpath(frontend_folder, "static")

autopilot_settings = Settings()
defaults_folder = autopilot_settings.defaults_folder

StaticFile = namedtuple("StaticFile", "parent filename url")

static_files = [
    StaticFile(static_folder, "js/axios.min.js", "https://cdnjs.cloudflare.com/ajax/libs/axios/0.19.2/axios.min.js"),
    StaticFile(
        static_folder,
        "js/polyfill.min.js",
        "https://polyfill.io/v3/polyfill.min.js?features=es2015,IntersectionObserver",
    ),
    StaticFile(static_folder, "js/vue.js", "https://cdnjs.cloudflare.com/ajax/libs/vue/2.6.12/vue.js"),
    StaticFile(static_folder, "js/metro.js", "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/js/metro.min.js"),
    StaticFile(
        static_folder, "css/metro-all.css", "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/css/metro-all.css"
    ),
    StaticFile(static_folder, "mif/metro.woff", "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/mif/metro.woff"),
    StaticFile(static_folder, "mif/metro.ttf", "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/mif/metro.ttf"),
    StaticFile(defaults_folder, "ardupilot_navigator", "https://firmware.ardupilot.org/Sub/latest/navigator/ardusub"),
    StaticFile(
        defaults_folder,
        "ardupilot_navigator_r4",
        "https://s3.us-west-1.amazonaws.com/ardusub.bluerobotics.com/test-builds/ardusub-a09013c6-navigator-r4-preview",
    ),
    StaticFile(defaults_folder, "ardupilot_pixhawk1", "https://firmware.ardupilot.org/Sub/latest/Pixhawk1/ardusub.apj"),
]

for file in static_files:
    path = pathlib.Path.joinpath(file.parent, file.filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(file.url, path)
    except Exception as error:
        warn(f"unable to open url {file.url}, error {error}")
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
        "starlette == 0.13.6",
        "fastapi == 0.63.0",
        "uvicorn == 0.13.4",
        "python-multipart == 0.0.5",
        "validators == 0.18.2",
        "fastapi-versioning == 0.9.1",
        "aiofiles == 0.6.0",
        "loguru == 0.5.3",
        "commonwealth == 0.1.0",
        "pyelftools == 0.27",
        "psutil == 5.7.2",
        "pyserial == 3.5",
    ],
)
