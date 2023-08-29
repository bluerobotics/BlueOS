#!/usr/bin/env python3
import setuptools

with open("README.md", "r", encoding="utf-8") as readme:
    long_description = readme.read()

setuptools.setup(
    name="nmea-injector",
    version="0.0.1",
    author="Rafael Araujo Lehmkuhl",
    author_email="rafael@bluerobotics.com",
    description="BlueOS NMEA Injector.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
)
