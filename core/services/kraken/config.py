# This file is used to define general configurations for the app

SERVICE_NAME = "kraken"

DEFAULT_MANIFESTS = [
    {
        "identifier": "bluerobotics-production",
        "name": "BlueOS Extensions Repository",
        "url": "https://bluerobotics.github.io/BlueOS-Extensions-Repository/manifest.json",
    },
]

__all__ = ["SERVICE_NAME", "DEFAULT_MANIFESTS"]
