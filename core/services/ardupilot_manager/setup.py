#!/usr/bin/env python3

import pathlib
import ssl
import urllib.request
from warnings import warn

import setuptools

ssl._create_default_https_context = ssl._create_unverified_context


static_files = {
    "js/axios.min.js": "https://cdnjs.cloudflare.com/ajax/libs/axios/0.19.2/axios.min.js",
    "js/polyfill.min.js": "https://polyfill.io/v3/polyfill.min.js?features=es2015,IntersectionObserver",
    "js/vue.js": "https://cdnjs.cloudflare.com/ajax/libs/vue/2.6.12/vue.js",
    "js/metro.js": "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/js/metro.min.js",
    "css/metro-all.css": "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/css/metro-all.css",
    "mif/metro.woff": "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/mif/metro.woff",
    "mif/metro.ttf": "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/mif/metro.ttf",
}

current_folder = pathlib.Path(__file__).parent.absolute()
frontend_folder = pathlib.Path.joinpath(current_folder, "frontend")
static_folder = pathlib.Path.joinpath(frontend_folder, "static")
static_folder.mkdir(exist_ok=True)

for filename, url in static_files.items():
    path = pathlib.Path.joinpath(static_folder, filename)
    path.parent.mkdir(exist_ok=True)
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as error:
        warn(f"unable to open url {url}, error {error}")


with open("README.md", "r") as readme:
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
        "fastapi-versioning == 0.9.0",
        "aiofiles == 0.6.0",
        "loguru == 0.5.3",
        "commonwealth == 0.1.0",
    ],
)
