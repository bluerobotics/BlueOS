#!/usr/bin/env python3

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from commonwealth.utils.commands import run_command

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_boot_list_table(output: str) -> list[dict]:
    """
    Parse journalctl --list-boots table format output.

    Format: <index> <boot_id> <start_time>—<end_time>
    Example: -12 8d18dbbee48a4a62868e139603ab7fd3 Fri 2025-09-05 13:17:01 BST—Fri 2025-09-05 13:44:34 BST
    """
    boots = []
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Match: <index> <boot_id> <rest of line>
        match = re.match(r"^\s*(-?\d+)\s+([0-9a-f]+)\s+(.+)$", line)
        if not match:
            continue

        index = int(match.group(1))
        boot_id = match.group(2)
        time_range = match.group(3)

        # Extract start time from the time range (before the em dash or en dash)
        # The separator is — (em dash U+2014) or – (en dash U+2013), NOT regular hyphen
        time_parts = re.split(r"[—–]", time_range, maxsplit=1)
        if time_parts:
            start_time_str = time_parts[0].strip()
            # Try to parse the timestamp - multiple formats possible
            # Format: "Fri 2025-09-05 13:17:01 BST"
            try:
                # Remove timezone abbreviation for simpler parsing
                time_no_tz = re.sub(r"\s+[A-Z]{2,4}$", "", start_time_str)
                # Parse without the weekday - split on first space to remove "Fri"
                date_time_part = time_no_tz.split(" ", 1)[1]
                dt = datetime.strptime(date_time_part, "%Y-%m-%d %H:%M:%S")
                first_entry = int(dt.timestamp() * 1000000)  # Convert to microseconds
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse timestamp '{start_time_str}': {e}")
                first_entry = 0
        else:
            first_entry = 0

        boots.append({"index": index, "boot_id": boot_id, "first_entry": first_entry})

    return boots


def get_boot_info(boot_index: int) -> Optional[dict]:
    try:
        result = run_command("journalctl --list-boots --output=json")
        if result.returncode != 0:
            logger.error(f"Failed to get boot list: {result.stderr}")
            return None

        # Try to parse as JSON first
        try:
            boots = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            # Fallback: journalctl has a bug where --output=json is ignored for --list-boots
            logger.warning(f"JSON parsing failed ({e}), falling back to table format parser")
            boots = parse_boot_list_table(result.stdout)

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
