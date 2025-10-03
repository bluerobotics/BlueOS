import gzip
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import requests
from loguru import logger


class ManifestHandler:
    """
    Handles downloading and processing the ArduPilot firmware manifest to extract USB device information.
    """

    CACHE_MAX_AGE_DAYS = 10

    def __init__(self) -> None:
        """Initialize the manifest handler."""
        self._usb_devices: Dict[str, Dict[str, Any]] = {}
        self.manifest_url = "https://firmware.ardupilot.org/manifest.json.gz"

    def is_file_valid(self, file_path: Path) -> bool:
        """
        Check if the file exists and is not too old.
        """
        if not file_path.exists():
            return False

        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        age = datetime.now() - file_time
        return age.days < self.CACHE_MAX_AGE_DAYS

    def load_existing_data(self, file_path: Path) -> bool:
        """
        Load USB devices data from an existing file if available and valid.
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
        """
        if "/" in usb_id:
            vid, pid = usb_id.split("/")
            vid = vid.replace("0x", "").lower()
            pid = pid.replace("0x", "").lower()
            return f"{vid}:{pid}"
        return usb_id.lower()  # Already in correct format

    def download_manifest(self, temp_file: Path) -> Any:
        """
        Download and decompress the manifest from the ArduPilot server directly to filesystem.
        """
        try:
            response = requests.get(self.manifest_url, timeout=10, stream=True)
            response.raise_for_status()

            # Decompress directly to filesystem
            with gzip.open(io.BytesIO(response.content), "rb") as gz_file:
                with open(temp_file, "wb") as out_file:
                    # Stream the decompressed data directly to disk
                    for chunk in iter(lambda: gz_file.read(8192), b""):
                        out_file.write(chunk)

            # Now load the decompressed JSON from disk
            with open(temp_file, "r", encoding="utf-8") as f:
                return json.load(f)

        except requests.RequestException as e:
            raise e
        except json.JSONDecodeError as e:
            raise e
        except Exception as e:
            raise e

    def parse_manifest(self, manifest_data: Dict[str, Any]) -> None:
        """
        Extract USB device information from the manifest data.
        The manifest has a simple structure: {'firmware': [list of entries]}
        """
        self._usb_devices.clear()

        # The manifest structure is simple: {'firmware': [list of entries]}
        firmware_list = manifest_data.get("firmware", [])

        for entry in firmware_list:
            # Each entry is a flat dictionary with USBID, platform, board_id
            if "USBID" in entry and "platform" in entry:
                usb_id = entry["USBID"]
                platform = entry["platform"]
                board_id = entry.get("board_id")

                # Handle both single USB ID and lists of USB IDs
                usb_ids = [usb_id] if isinstance(usb_id, str) else usb_id

                for uid in usb_ids:
                    formatted_uid = self._format_usb_id(uid)
                    self._usb_devices.setdefault(formatted_uid, {})

                    # Store board_name: board_id mapping
                    self._usb_devices[formatted_uid][platform] = board_id

    def process_and_export(self, output_file: Path) -> None:
        """
        Download manifest, process it, and export the USB device information to a file.
        If a valid file exists and is not too old, use it instead of downloading new data.
        """

        if self.load_existing_data(output_file):
            logger.info(f"Using existing data from {output_file}")
            device_count = len(self._usb_devices)
            board_count = sum(len(boards) for boards in self._usb_devices.values())
            logger.info(f"Found {device_count} unique USB IDs")
            logger.info(f"Total board mappings: {board_count}")
            return

        # If file is invalid or too old, download and process new data
        logger.info("Downloading manifest...")
        temp_file = output_file.with_suffix(".tmp")

        try:
            manifest_data = self.download_manifest(temp_file)

            logger.info("Processing manifest...")
            self.parse_manifest(manifest_data)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(self._usb_devices, f, indent=2)

            logger.success(f"Successfully exported USB device information to {output_file}")

            device_count = len(self._usb_devices)
            board_count = sum(len(boards) for boards in self._usb_devices.values())
            logger.info(f"Found {device_count} unique USB IDs")
            logger.info(f"Total board mappings: {board_count}")

        finally:
            if temp_file.exists():
                temp_file.unlink()
