import os
import pathlib

import setuptools

# Force current path to be used as reference for Python
## Fix problems related to calling setup.py from different paths
os.chdir(os.path.abspath(os.path.dirname(__file__)))

with open(pathlib.Path(__file__).parent.joinpath("README.md"), "r", encoding="utf-8") as readme:
    long_description = readme.read()

setuptools.setup(
    name="commonwealth",
    version="0.1.0",
    description="BlueOS library to share common code.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    packages=setuptools.find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "aiohttp == 3.7.4",
        "appdirs == 1.4.4",
        "loguru == 0.5.3",
        "starlette == 0.27.0",
        "pykson == 1.0.2",
    ],
    dependency_links=[
        # Waiting for PRs to get merged in pykson
        "https://github.com/patrickelectric/pykson/tarball/1.0.2#egg=pykson-1.0.2"
    ],
)
