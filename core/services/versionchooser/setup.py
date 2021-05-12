#!/usr/bin/env python3

import pathlib
import ssl
import urllib.request
from warnings import warn

from setuptools import setup

ssl._create_default_https_context = ssl._create_unverified_context


static_files = {
    "js/axios.min.js": "https://cdnjs.cloudflare.com/ajax/libs/axios/0.19.2/axios.min.js",
    "js/polyfill.min.js": "https://polyfill.io/v3/polyfill.min.js?features=es2015,IntersectionObserver",
    "js/vue.js": "https://cdnjs.cloudflare.com/ajax/libs/vue/2.6.12/vue.js",
    "js/timeago.js": "https://cdnjs.cloudflare.com/ajax/libs/timeago.js/2.0.2/timeago.min.js",
    "js/metro.js": "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/js/metro.min.js",
    "js/jquery.js": "https://cdnjs.cloudflare.com/ajax/libs/jquery/3.2.1/jquery.min.js",
    "css/metro-all.css": "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/css/metro-all.css",
    "mif/metro.woff": "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/mif/metro.woff",
    "mif/metro.ttf": "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/mif/metro.ttf",
}

current_folder = pathlib.Path(__file__).parent.absolute()
static_folder = pathlib.Path.joinpath(current_folder, "static")

for filename, url in static_files.items():
    path = pathlib.Path.joinpath(static_folder, filename)
    path.parent.mkdir(exist_ok=True)
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as error:
        warn(f"unable to open url {url}, error {error}")

setup(
    name="versionchooser_service",
    version="0.1.0",
    description="Blue Robotics Ardusub Companion Version Chooser",
    license="MIT",
    install_requires=[
        "aiohttp-jinja2 == 1.4.2",
        "aiohttp == 3.7.3",
        "connexion[swagger-ui, aiohttp] == 2.7.0",
        "docker == 4.4.4",
        "appdirs == 1.4.4",
        "pytest-asyncio == 0.14.0",
        "asyncmock == 0.4.2",
        "werkzeug == 2.0.0",
        "attrs == 20.3.0",
    ],
)
