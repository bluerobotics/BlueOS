import gzip
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import requests


class ManifestHandler:
    """
    Handles downloading and processing the ArduPilot firmware manifest to extract USB device information.
    """

    CACHE_MAX_AGE_DAYS = 10

    def __init__(self) -> None:
        """Initialize the manifest handler."""
        self._usb_devices: Dict[str, list[str]] = {}
        self.manifest_url = "https://firmware.ardupilot.org/manifest.json.gz"

    def is_file_valid(self, file_path: Path) -> bool:
        """
        Check if the file exists and is not too old.

        Args:
            file_path: Path to the file to check.

        Returns:
            bool: True if file exists and is valid, False otherwise.
        """
        if not file_path.exists():
            return False

        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        age = datetime.now() - file_time
        return age.days < self.CACHE_MAX_AGE_DAYS

    def load_existing_data(self, file_path: Path) -> bool:
        """
        Load USB devices data from an existing file if available and valid.

        Args:
            file_path: Path to the file.

        Returns:
            bool: True if file was loaded successfully, False otherwise.
        """
        try:
            if self.is_file_valid(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    self._usb_devices = json.load(f)
                return True
        except (json.JSONDecodeError, OSError):
            pass
        return False

    def _format_usb_id(self, usb_id: str) -> str:
        """
        Convert USB ID to 'vid:pid' format.

        Args:
            usb_id: USB ID string in '0xVID/0xPID' or 'VID:PID' format.

        Returns:
            Formatted USB ID in 'vid:pid' format.
        """
        if "/" in usb_id:  # Handle '0xVID/0xPID' format
            vid, pid = usb_id.split("/")
            vid = vid.replace("0x", "").lower()
            pid = pid.replace("0x", "").lower()
            return f"{vid}:{pid}"
        return usb_id.lower()  # Already in correct format

    def download_manifest(self) -> Any:
        """
        Download and decompress the manifest from the ArduPilot server.

        Returns:
            The decompressed manifest as a dictionary.

        Raises:
            RuntimeError: If there is an issue downloading or parsing the manifest.
        """
        try:
            response = requests.get(self.manifest_url, timeout=10)
            response.raise_for_status()

            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz_file:
                return json.loads(gz_file.read().decode("utf-8"))
        except requests.RequestException as e:
            raise e
        except json.JSONDecodeError as e:
            raise e
        except Exception as e:
            raise e

    def parse_manifest(self, manifest_data: dict[str, list[str]]) -> None:
        """
        Extract USB device information from the manifest data.

        Args:
            manifest_data: Raw manifest data as a dictionary.
        """
        self._usb_devices.clear()

        def process_node(node: Any) -> None:
            if isinstance(node, dict):
                if "USBID" in node and "platform" in node:
                    usb_id = node["USBID"]
                    platform = node["platform"]

                    # Handle both single USB ID and lists of USB IDs
                    usb_ids = [usb_id] if isinstance(usb_id, str) else usb_id

                    for uid in usb_ids:
                        formatted_uid = self._format_usb_id(uid)
                        self._usb_devices.setdefault(formatted_uid, [])

                        if platform not in self._usb_devices[formatted_uid]:
                            self._usb_devices[formatted_uid].append(platform)

                # Recursively process all values in the dictionary
                for value in node.values():
                    process_node(value)
            elif isinstance(node, list):
                # Recursively process all items in the list
                for item in node:
                    process_node(item)

        process_node(manifest_data)

    def export_json(self, output_file: Path) -> None:
        """
        Export USB device information to a JSON file.

        Args:
            output_file: Path to the output JSON file.
        """
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self._usb_devices, f, indent=2)

    def process_and_export(self, output_file: Path) -> None:
        """
        Download manifest, process it, and export the USB device information to a file.
        If a valid file exists and is not too old, use it instead of downloading new data.

        Args:
            output_file: Path to the output JSON file.

        Raises:
            RuntimeError: If there is an issue during processing.
        """
        # Try to load from existing file first
        if self.load_existing_data(output_file):
            print(f"Using existing data from {output_file}")
            # Print summary of existing data
            device_count = len(self._usb_devices)
            platform_count = sum(len(platforms) for platforms in self._usb_devices.values())
            print(f"\nFound {device_count} unique USB IDs")
            print(f"Total platform mappings: {platform_count}")
            return

        # If file is invalid or too old, download and process new data
        print("Downloading manifest...")
        manifest_data = self.download_manifest()

        print("Processing manifest...")
        self.parse_manifest(manifest_data)
        self.export_json(output_file)

        print(f"Successfully exported USB device information to {output_file}")

        # Print summary
        device_count = len(self._usb_devices)
        platform_count = sum(len(platforms) for platforms in self._usb_devices.values())
        print(f"\nFound {device_count} unique USB IDs")
        print(f"Total platform mappings: {platform_count}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python metadata_preprocessor.py <output_file>")
        sys.exit(1)

    try:
        handler = ManifestHandler()
        handler.process_and_export(Path(sys.argv[1]))
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
