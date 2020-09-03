import pathlib
import shutil
import ssl
import sys
import urllib.request

import setuptools


def populate_static_files() -> None:
    # Ignore ssl when downloading new files
    # This can happen since python can fail to verify certificate
    ssl._create_default_https_context = ssl._create_unverified_context

    current_folder = pathlib.Path(__file__).parent.absolute()
    static_folder = pathlib.Path.joinpath(current_folder, "html/static")

    static_files = {
        "js": [
            "https://unpkg.com/axios@0.19.2/dist/axios.min.js",
            "https://cdn.metroui.org.ua/v4/js/metro.min.js",
            "https://unpkg.com/vue@2.6.11/dist/vue.js",
        ],
        "css": [
            "https://cdn.metroui.org.ua/v4/css/metro-all.min.css",
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
                name = url.split("/")[-1]
                # Create path with file name to download
                download_file_path = pathlib.Path.joinpath(download_path, name)
                urllib.request.urlretrieve(url, str(download_file_path))
            except Exception as error:
                print(f"Unable to download, error: {error}")
                sys.exit(1)


populate_static_files()

with open("README.md", "r") as readme:
    long_description = readme.read()

setuptools.setup(
    name="cable-guy",
    version="0.0.1",
    author="Patrick José Pereira",
    author_email="patrick@bluerobotics.com",
    description="A simple web api to provide access to ethernet configuration.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "appdirs == 1.4.4",
        "connexion[swagger-ui] == 2.7.0",
        "psutil == 5.7.2",
        "pyroute2 == 0.5.13",
        "waitress == 1.4.4",
    ],
)
