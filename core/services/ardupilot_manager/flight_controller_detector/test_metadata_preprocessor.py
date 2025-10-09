import json
from pathlib import Path
from typing import Dict, Any

from .metadata_preprocessor import ManifestHandler


def test_pixhawk_and_cube_entries() -> None:
    """Test that we have entries for both Pixhawk and Cube devices."""
    # Generate the boards.json data
    handler = ManifestHandler()
    boards_file = Path("test_boards.json")

    try:
        # Process and export the data
        handler.process_and_export(boards_file)

        # Load the generated data
        with open(boards_file, "r", encoding="utf-8") as f:
            boards_data: Dict[str, Dict[str, Any]] = json.load(f)

        # Check for Pixhawk and Cube entries
        pixhawk_entries = []
        cube_entries = []

        for usb_id, boards in boards_data.items():
            for board_name in boards.keys():
                if "pixhawk" in board_name.lower():
                    pixhawk_entries.append(board_name)
                elif "cube" in board_name.lower():
                    cube_entries.append(board_name)

        # Verify we have both types
        assert len(pixhawk_entries) > 0, f"No Pixhawk entries found. Available entries: {list(boards_data.keys())}"
        assert len(cube_entries) > 0, f"No Cube entries found. Available entries: {list(boards_data.keys())}"

        # Check for specific expected variants
        expected_pixhawk = ["Pixhawk1", "Pixhawk4", "Pixhawk6X"]
        expected_cube = ["CubeBlack", "CubeOrange", "CubePurple"]

        found_pixhawk_variants = [
            entry for entry in pixhawk_entries if any(variant in entry for variant in expected_pixhawk)
        ]
        found_cube_variants = [entry for entry in cube_entries if any(variant in entry for variant in expected_cube)]

        assert len(found_pixhawk_variants) > 0, f"Expected Pixhawk variants not found. Found: {pixhawk_entries}"
        assert len(found_cube_variants) > 0, f"Expected Cube variants not found. Found: {cube_entries}"

        # Verify data structure
        assert len(boards_data) > 0, "No USB IDs found in data"
        for usb_id, boards in boards_data.items():
            assert len(boards) > 0, f"USB ID {usb_id} has no board mappings"
            for board_name, board_id in boards.items():
                assert isinstance(board_id, int), f"Board ID for {board_name} should be an integer"
                assert board_id > 0, f"Board ID for {board_name} should be positive"

    finally:
        # Clean up
        if boards_file.exists():
            boards_file.unlink()
