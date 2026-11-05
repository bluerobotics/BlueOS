import json
from pathlib import Path
from typing import Any

import appdirs
from loguru import logger


class EnvironmentManager:
    """Wrapper for managing environment variables that should be persisted
    across reboots."""

    BOOTSTRAP_STARTUP_FILE = Path(appdirs.user_config_dir("bootstrap"), "startup.json")

    @staticmethod
    def set_variable(key: str, value: Any) -> None:
        # we currently persist environment variables through the
        # bootstrap/startup.json config file
        with open(EnvironmentManager.BOOTSTRAP_STARTUP_FILE, "r+", encoding="utf-8") as startup_file:
            settings = json.load(startup_file)
            environment = settings["core"].get("environment", [])
            environment = [variable for variable in environment if not variable.startswith(f"{key}=")]
            environment.append(f"{key}={value}")
            settings["core"]["environment"] = environment

            startup_file.seek(0)
            startup_file.write(json.dumps(settings, indent=2))
            startup_file.truncate()

        logger.info(f"Set bootstrap environment variable {key}={value}.")
