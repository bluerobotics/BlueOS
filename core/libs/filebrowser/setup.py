import os
import pathlib

import setuptools

# Force current path to be used as reference for Python
## Fix problems related to calling setup.py from different paths
os.chdir(os.path.abspath(os.path.dirname(__file__)))

with open(pathlib.Path(__file__).parent.joinpath("README.md"), "r", encoding="utf-8") as readme:
    long_description = readme.read()

setuptools.setup(
    name="filebrowser",
    version="0.1.0",
    description="BlueOS Python client for the filebrowser API.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "aiohttp == 3.7.4",
    ],
)
