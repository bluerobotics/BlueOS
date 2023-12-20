#!/usr/bin/env python3

import os
import pathlib
import shutil
import ssl
import sys
import urllib.request

from setuptools import setup

# Ignore ssl if it fails
if not os.environ.get("PYTHONHTTPSVERIFY", "") and getattr(ssl, "_create_unverified_context", None):
    ssl._create_default_https_context = ssl._create_unverified_context


def populate_static_files() -> None:
    # Ignore ssl when downloading new files
    # This can happen since python can fail to verify certificate
    ssl._create_default_https_context = ssl._create_unverified_context

    current_folder = pathlib.Path(__file__).parent.absolute()
    static_folder = pathlib.Path.joinpath(current_folder, "html/static")

    static_files = {
        "js": [
            "https://unpkg.com/axios@0.19.2/dist/axios.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/js/metro.min.js",
            "https://unpkg.com/vue@2.6.11/dist/vue.js",
        ],
        "css": [
            "https://cdnjs.cloudflare.com/ajax/libs/metro/4.4.3/css/metro-all.min.css",
        ],
    }

    # Delete static folder and redownload everything
    if static_folder.exists():
        shutil.rmtree(static_folder, ignore_errors=True)
    static_folder.mkdir()

    for path, urls in static_files.items():
        print(f"Downloading in {path}..")
        for url in urls:
            print(f"File: {url}")
            try:
                # Create path of file
                download_path = pathlib.Path.joinpath(static_folder, path)
                download_path.mkdir(exist_ok=True)
                name = url.rsplit("/", maxsplit=1)[-1]
                # Create path with file name to download
                download_file_path = pathlib.Path.joinpath(download_path, name)
                urllib.request.urlretrieve(url, str(download_file_path))
            except Exception as error:
                print(f"Unable to download, error: {error}")
                sys.exit(1)


populate_static_files()

setup(
    name="helper_service",
    version="0.1.0",
    description="Helper information for development",
    license="MIT",
    py_modules=[],
    install_requires=[
        "aiofiles == 0.6.0",
        "beautifulsoup4 == 4.9.3",
        "commonwealth == 0.1.0",
        "fastapi == 0.105.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "fastapi-versioning == 0.9.1",
        "loguru == 0.5.3",
        "psutil == 5.7.2",
        "requests == 2.25.1",
        "speedtest-cli == 2.1.3",
        "starlette == 0.27.0",
        "uvicorn == 0.13.4",
    ],
)
