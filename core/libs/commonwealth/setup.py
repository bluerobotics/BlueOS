import setuptools

with open("README.md", "r") as readme:
    long_description = readme.read()

setuptools.setup(
    name="commonwealth",
    version="0.1.0",
    description="Companion library to share common code.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    packages=setuptools.find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "loguru == 0.5.3",
    ],
)
