import os
import pathlib

import setuptools

# Force current path to be used as reference for Python
## Fix problems related to calling setup.py from different paths
os.chdir(os.path.abspath(os.path.dirname(__file__)))

with open(pathlib.Path(__file__).parent.joinpath("README.md"), "r", encoding="utf-8") as readme:
    long_description = readme.read()

setuptools.setup(
    name="bridges",
    version="0.1.0",
    description="BlueOS abstraction over bridges tool.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    packages=setuptools.find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "loguru == 0.5.3",
        "pyserial == 3.5",
    ],
)
