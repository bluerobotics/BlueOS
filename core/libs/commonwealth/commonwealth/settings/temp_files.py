import filecmp
import json
import pathlib
import re
import threading
from datetime import datetime, timezone

from loguru import logger

from commonwealth.settings.exceptions import BadSettingsFile, MigrationFail

save_lock = threading.Lock()


def clear_temp_files(folder: pathlib.Path) -> None:
    """Clear leftover fixed-name temporary files from older saves"""
    # Only remove the legacy settings-N.tmp name. Unique per-save temps are left alone; finally
    # cleans normal failures, and SIGKILL orphans are tiny settings JSON leftovers.
    # Must use the same non-reentrant lock as settings save() so we never unlink a .tmp file while
    # save() is still writing and about to os.replace() it.
    with save_lock:
        for temp_file in folder.glob("*.tmp"):
            if re.fullmatch(r"settings-\d+\.tmp", temp_file.name) is None:
                continue
            try:
                temp_file.unlink()
            except Exception as exception:
                logger.debug(f"Failed to clear temporary file {temp_file}: {exception}")


MAX_INVALID_COPIES = 5


def move_invalid_file_aside(file_path: pathlib.Path, exception: Exception) -> bool:
    """Returns False if the file could not be moved aside and must be left untouched"""
    # Only these messages are known to never echo setting values (they could hold passwords)
    reason = (
        str(exception)
        if isinstance(exception, (json.JSONDecodeError, BadSettingsFile, MigrationFail))
        else type(exception).__name__
    )
    try:
        copies = sorted(file_path.parent.glob(f"{file_path.name}.invalid-*"))
        same_copy = next((copy for copy in copies if filecmp.cmp(file_path, copy, shallow=False)), None)
        if same_copy:
            file_path.unlink()
            logger.warning(f"Invalid settings file {file_path} ({reason}) is already kept in {same_copy}")
            return True
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        target = file_path.with_name(f"{file_path.name}.invalid-{timestamp}")
        file_path.rename(target)
        logger.warning(f"Invalid settings file {file_path} ({reason}) was kept as {target}")
    except OSError as error:
        logger.error(f"Failed to move invalid settings file {file_path} aside: {error}")
        return False

    # Bounds the copies when something keeps producing new bad files on every load. The oldest copy is kept
    # because it is the one most likely to hold the user's real data.
    try:
        for old_copy in sorted([*copies, target])[1 : -(MAX_INVALID_COPIES - 1)]:
            old_copy.unlink()
    except OSError as error:
        logger.error(f"Failed to prune old invalid settings copies: {error}")
    return True
