#!/usr/bin/env python3

import pathlib
import ssl
import sys
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
        sys.exit(1)


setuptools.setup(
    name="wifi_service",
    version="0.1.0",
    description="Wifi manager for wpa_supplicant",
    license="MIT",
)
