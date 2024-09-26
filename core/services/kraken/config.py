# This file is used to define general configurations for the app

SERVICE_NAME = "kraken"

DEFAULT_MANIFESTS = [
    {
        "identifier": "bluerobotics-production",
        "name": "BlueOS Extensions Repository",
        "url": "https://raw.githubusercontent.com/bluerobotics/BlueOS-Extensions-Repository/refs/heads/gh-pages/manifest.json",
    },
]

DEFAULT_EXTENSIONS = [
    {
        "identifier": "blueos.major_tom",
        "url": "https://blueos.cloud/major_tom/install",
    },
]

__all__ = ["SERVICE_NAME", "DEFAULT_MANIFESTS", "DEFAULT_EXTENSIONS"]
