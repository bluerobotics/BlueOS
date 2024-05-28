import setuptools

with open("README.md", "r", encoding="utf-8") as readme:
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
        "psutil == 5.7.2",
        "pyroute2 == 0.5.13",
        "starlette == 0.27.0",
        "fastapi == 0.105.0",
        "sdbus-networkmanager == 2.0.0",
        # Enforce anyio fastapi subdependency to avoid conflict with starlette
        "anyio == 3.7.1",
        "uvicorn == 0.13.4",
        "aiofiles == 0.6.0",
        "fastapi-versioning == 0.9.1",
        "commonwealth == 0.1.0",
        "loguru == 0.5.3",
    ],
)
