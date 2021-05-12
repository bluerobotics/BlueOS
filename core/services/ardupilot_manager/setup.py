import setuptools

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
    ],
)
