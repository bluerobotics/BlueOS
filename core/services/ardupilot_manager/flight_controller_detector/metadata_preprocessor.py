import gzip
import io
import json
import sys
from typing import Dict

import requests


class ManifestHandler:
    """
    Handles downloading and processing the ArduPilot firmware manifest to extract USB device information.
    """

    def __init__(self):
        """Initialize the manifest handler."""
        self._usb_devices: Dict[str, list] = {}
        self.manifest_url = "https://firmware.ardupilot.org/manifest.json.gz"

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

    def download_manifest(self) -> dict:
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
            raise RuntimeError(f"Error downloading manifest: {e}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Error parsing manifest JSON: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")

    def parse_manifest(self, manifest_data: dict):
        """
        Extract USB device information from the manifest data.

        Args:
            manifest_data: Raw manifest data as a dictionary.
        """
        self._usb_devices.clear()

        def process_node(node):
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

    def export_json(self, output_file: str):
        """
        Export USB device information to a JSON file.

        Args:
            output_file: Path to the output JSON file.
        """
        with open(output_file, "w") as f:
            json.dump(self._usb_devices, f, indent=2)


def main():
    if len(sys.argv) != 2:
        print("Usage: python manifest_handler.py <output_usb.json>")
        sys.exit(1)

    output_file = sys.argv[1]

    try:
        handler = ManifestHandler()
        print("Downloading manifest...")
        manifest_data = handler.download_manifest()

        print("Processing manifest...")
        handler.parse_manifest(manifest_data)
        handler.export_json(output_file)

        print(f"Successfully exported USB device information to {output_file}")

        # Print summary
        device_count = len(handler._usb_devices)
        platform_count = sum(len(platforms) for platforms in handler._usb_devices.values())
        print(f"\nFound {device_count} unique USB IDs")
        print(f"Total platform mappings: {platform_count}")

    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
