import json
from pathlib import Path
from typing import Any, Dict

from loguru import logger


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> Any:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("Database not found")
        except json.decoder.JSONDecodeError as exception:
            logger.error(f"Failed to parse json in database file: {exception}")
        except Exception as exception:
            logger.exception(exception)

        return {}

    def write(self, data: Dict[str, Any]) -> None:
        # Just to be sure that we'll be able to load it later
        json_string = json.dumps(data)
        json.loads(json_string)

        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f)
