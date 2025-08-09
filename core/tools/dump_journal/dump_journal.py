#!/usr/bin/env python3

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from commonwealth.utils.commands import run_command

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_boot_info(boot_index: int) -> Optional[dict]:
    try:
        result = run_command("journalctl --list-boots --output=json")
        if result.returncode != 0:
            logger.error(f"Failed to get boot list: {result.stderr}")
            return None
        boots = json.loads(result.stdout)
        boots_dict = {boot["index"]: boot for boot in boots}
        if boot_index not in boots_dict:
            logger.error(f"Boot index {boot_index} not found in boot list")
            return None
        return boots_dict[boot_index]
    except Exception as e:
        logger.error(f"Error getting boot info: {e}")
        return None


def dump_latest_journal_logs(output_dir: str = "/var/logs/blueos/services/journal/", boot_index: int = -1) -> bool:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    boot_info = get_boot_info(boot_index)
    if not boot_info:
        return False

    # Extract boot ID and timestamp
    boot_id = boot_info.get("boot_id", "unknown")
    first_entry = boot_info.get("first_entry", 0)

    # Convert timestamp to datetime
    try:
        dt = datetime.fromtimestamp(first_entry / 1000000)  # Convert microseconds to seconds
        timestamp_formatted = dt.strftime("%Y%m%d_%H%M%S")
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing timestamp: {e}")
        timestamp_formatted = "unknown_time"

    # Create filename: timestamp_uuid_short.log
    uuid_short = boot_id[:8] if boot_id != "unknown" else "unknown"
    filename = f"{timestamp_formatted}_{uuid_short}.log"
    filepath = Path(output_dir) / filename

    logger.info(f"Dumping latest journal logs for boot {boot_id}")
    logger.info(f"Filename: {filename}")

    # Get the journal logs for the specified boot with loguru-like format
    # --output=short-iso provides timestamps and log levels in ISO format

    cmd = f"journalctl -b {boot_index} --output=short-iso"
    result = run_command(cmd)
    if result.returncode != 0:
        logger.error(f"Failed to get journal logs: {result.stderr}")
        return False

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Journal logs for boot {boot_id}\n")
        f.write(f"# Boot started: {dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# Format: ISO timestamps with log levels (loguru-like)\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("#" + "=" * 60 + "\n\n")
        f.write(result.stdout)

    logger.info(f"Logs saved to: {filepath}")
    return True


if __name__ == "__main__":
    import sys

    boot = int(sys.argv[1]) if len(sys.argv) > 1 else -1

    dump_latest_journal_logs(boot_index=boot)
