# This file is used to define general configurations for the app

from typing import Dict, List

SERVICE_NAME = "kraken"

DEFAULT_MANIFESTS = [
    {
        "identifier": "bluerobotics-production",
        "name": "BlueOS Extensions Repository",
        "url": "https://raw.githubusercontent.com/bluerobotics/BlueOS-Extensions-Repository/refs/heads/gh-pages/manifest.json",
    },
]

DEFAULT_EXTENSIONS: List[Dict[str, str]] = []

DEFAULT_INJECTED_ENV_VARIABLES = [
    "MAV_SYSTEM_ID",
]

__all__ = ["SERVICE_NAME", "DEFAULT_MANIFESTS", "DEFAULT_EXTENSIONS", "DEFAULT_INJECTED_ENV_VARIABLES"]
