import pathlib
import re
import threading

from loguru import logger

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
