import json
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

from flight_controller_detector.metadata_preprocessor import ManifestHandler
from typedefs import Platform


class SerialAttr(str, Enum):
    product = "product"
    manufacturer = "manufacturer"


class SerialBoardIdentifier(BaseModel):
    attribute: SerialAttr
    id_value: str
    platform: Platform


def get_boards_cache_path() -> Path:
    """Get the path to the boards cache file."""
    cache_dir = Path("/usr/blueos/userdata/.cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "boards.json"


def load_board_identifiers() -> List[SerialBoardIdentifier]:
    """Load board identifiers from the manifest, using cache when possible."""
    boards_path = get_boards_cache_path()
    boards_path.parent.mkdir(parents=True, exist_ok=True)

    # Process manifest and update cache if needed
    handler = ManifestHandler()
    handler.process_and_export(boards_path)

    with open(boards_path, encoding="utf-8") as f:
        json_data = json.load(f)

    # Extract all unique board names from the new structure
    board_names = set()
    for boards_list in json_data.values():
        if isinstance(boards_list, list) and boards_list:
            # Check if it's the new format (list of objects) or old format (list of strings)
            if isinstance(boards_list[0], dict):
                # New format: extract board_name from objects
                board_names.update(board["board_name"] for board in boards_list if "board_name" in board)
            else:
                # Old format: boards_list contains strings directly
                board_names.update(boards_list)

    return [
        SerialBoardIdentifier(attribute=SerialAttr.product, id_value=board_name, platform=Platform.GenericSerial)
        for board_name in board_names
    ]


def get_board_id_from_name(board_name: str) -> Optional[int]:
    """
    Get the board ID for a given board name by searching through the boards cache.

    Args:
        board_name: The name of the board to look up.

    Returns:
        Optional[int]: The board ID if found, None otherwise.
    """
    try:
        boards_path = get_boards_cache_path()

        # If cache doesn't exist, try to generate it
        if not boards_path.exists():
            handler = ManifestHandler()
            handler.process_and_export(boards_path)

        with open(boards_path, encoding="utf-8") as f:
            json_data = json.load(f)

        # Search through all USB IDs for the board name
        for boards_list in json_data.values():
            if isinstance(boards_list, list):
                for board in boards_list:
                    if isinstance(board, dict) and board.get("board_name") == board_name:
                        return board.get("board_id")
                    elif isinstance(board, str) and board == board_name:
                        # Old format doesn't have board IDs
                        return None

        return None
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None


def get_board_id_from_usb_id(vid: int, pid: int, board_name: Optional[str] = None) -> Optional[int]:
    """
    Get the board ID for a given USB VID:PID combination, optionally filtering by board name.

    Args:
        vid: USB Vendor ID
        pid: USB Product ID
        board_name: Optional board name to filter results when multiple boards share the same USB ID

    Returns:
        Optional[int]: The board ID if found, None otherwise.
    """
    try:
        boards_path = get_boards_cache_path()

        # If cache doesn't exist, try to generate it
        if not boards_path.exists():
            handler = ManifestHandler()
            handler.process_and_export(boards_path)

        with open(boards_path, encoding="utf-8") as f:
            json_data = json.load(f)

        # Format USB ID as vid:pid (lowercase hex)
        usb_id = f"{vid:04x}:{pid:04x}"

        if usb_id in json_data:
            boards_list = json_data[usb_id]
            if isinstance(boards_list, list):
                for board in boards_list:
                    if isinstance(board, dict):
                        # If board_name is specified, filter by it
                        return board.get("board_id")
                    elif isinstance(board, str):
                        # Old format doesn't have board IDs
                        return None

        return None
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None


# Load dynamic board identifiers from manifest
identifiers = load_board_identifiers()
