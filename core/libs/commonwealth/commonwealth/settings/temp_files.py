import pathlib
import threading

from loguru import logger

save_lock = threading.Lock()


def clear_temp_files(folder: pathlib.Path) -> None:
    # Must use the same non-reentrant lock as settings save() so we never unlink a .tmp file while
    # save() is still writing and about to os.replace() it.
    with save_lock:
        for temp_file in folder.glob("*.tmp"):
            try:
                temp_file.unlink()
            except Exception as exception:
                logger.debug(f"Failed to clear temporary file {temp_file}: {exception}")
