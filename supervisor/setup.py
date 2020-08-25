#!/usr/bin/env python3

import pathlib
import urllib.request
import os
from setuptools import setup


def ensure_dir(file_path: pathlib.Path) -> None:
    """Ensures that file_path exists

    Args:
        file_path (pathlib.Path): path to check
    """
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)


static_files = {
    "css/bootstrap-switch-button-1.1.0.min.css":
        "https://cdn.jsdelivr.net/gh/gitbrent/bootstrap-switch-button@1.1.0/css/bootstrap-switch-button.min.css",
    "css/bootstrap-vue.css":
        "https://unpkg.com/bootstrap-vue@latest/dist/bootstrap-vue.css",
    "css/bootstrap.min.css":
        "https://unpkg.com/bootstrap/dist/css/bootstrap.min.css",
    "css/fa-all.css":
        "https://use.fontawesome.com/releases/v5.7.0/css/all.css",
    "js/axios-0.19.2.min.js":
        "https://cdnjs.cloudflare.com/ajax/libs/axios/0.19.2/axios.min.js",
    "js/bootstrap-switch-button-1.1.0.min.js":
        "https://cdn.jsdelivr.net/gh/gitbrent/bootstrap-switch-button@1.1.0/dist/bootstrap-switch-button.min.js",
    "js/bootstrap-vue.js":
        "https://unpkg.com/bootstrap-vue@latest/dist/bootstrap-vue.js",
    "js/polyfill.min.js":
        "https://polyfill.io/v3/polyfill.min.js?features=es2015,IntersectionObserver",
    "js/vue.js":
        "https://unpkg.com/vue@latest/dist/vue.js",
}

current_folder = pathlib.Path(__file__).parent.absolute()
static_folder = pathlib.Path.joinpath(current_folder, "static")

for filename, url in static_files.items():
    path = pathlib.Path.joinpath(static_folder, filename)
    ensure_dir(path)
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as error:
        print(f"unable to open url {url}, error {error}")
        exit(1)
    print(url)

setup(name='supervisor_service',
      version='0.1.0',
      description='Blue Robotics Ardusub Companion Supervisor',
      license='MIT',
      install_requires=['connexion[swagger-ui, aiohttp]', 'docker', 'aiohttp==3.6.2', 'semver'])
