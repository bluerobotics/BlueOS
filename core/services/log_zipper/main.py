#!/usr/bin/env python3

import argparse
import datetime
import glob
import gzip
import logging
import os
import pathlib
import time
from typing import List

from commonwealth.utils.general import available_disk_space_mb, delete_everything
from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger

SERVICE_NAME = "log-zipper"


def zip_files(files: List[str], output_path: str) -> None:
    for file in files:
        logger.debug(f"Zipping {file}...")
        with open(file, "rb") as f_in, gzip.open(output_path, "wb") as f_out:
            f_out.writelines(f_in)

    for file in files:
        try:
            delete_everything(pathlib.Path(file))
            logger.debug(f"Deleted file: {file}")
        except OSError as e:
            logger.debug(f"Error deleting file: {file} - {e}")


# pylint: disable=too-many-locals
def main() -> None:
    parser = argparse.ArgumentParser(description="Periodically scan a directory and zip files older than one hour")
    parser.add_argument("path", help="Directory path or glob to scan")
    parser.add_argument("-a", "--max-age-minutes", type=int, default=10, help="Maximum age for files in minutes")
    parser.add_argument(
        "-l",
        "--free-disk-limit",
        type=int,
        default=30,
        help="Minimum free disk (MB) allowed before starting deleting logs",
    )
    args = parser.parse_args()

    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    init_logger(SERVICE_NAME)

    # Enforce path parameter
    if not glob.has_magic(args.path) and not os.path.isdir(args.path):
        parser.error(f"Invalid path: {args.path}")

    # We need to transform from minutes to seconds, since this is what time and st_mtime returns
    max_age_seconds = args.max_age_minutes * 60

    zip_extension = "gz"

    while True:
        now = time.time()

        free_disk_space_mb = int(available_disk_space_mb())
        not_enough_space = free_disk_space_mb < args.free_disk_limit

        # Get the root directories of all files
        if not_enough_space:
            logger.warning(
                f"Available disk space is lower than our limit: {free_disk_space_mb}MB < {args.free_disk_limit}MB"
            )
            logger.warning(f"Going to delete all compressed files.. (*.{zip_extension})")
            files = glob.glob(args.path.replace(".log", ".gz"), recursive=True)
            pathlib_files = [pathlib.Path(file) for file in files]
            gz_files = [file for file in pathlib_files if file.is_file() and file.suffix == f".{zip_extension}"]
            for file in gz_files:
                logger.warning(f"Deleting {file}: {int(file.stat().st_size / 2**20)} MB")
                delete_everything(pathlib.Path(file))

        files = glob.glob(args.path, recursive=True)
        logger.info(f"Scanning {args.path} for files older than {str(datetime.timedelta(seconds=max_age_seconds))}...")
        files = [file for file in files if os.path.isfile(file) and os.stat(file).st_mtime < now - max_age_seconds]
        root_dirs = list(set(os.path.dirname(file) for file in files))
        root_dirs.sort()
        logger.info(f"Root folders: {root_dirs}")

        for folder in root_dirs:
            local_files = [file for file in files if folder in file]
            if not local_files:
                continue
            folder_name = os.path.basename(folder)
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            zipped_file = f"{folder}/{folder_name}-{timestamp}.{zip_extension}"
            zip_files(local_files, zipped_file)
            logger.info(f"Created zip archive {zipped_file} with {len(local_files)} files.")

        # There is no reason to sleep in a minor time than max age,
        # the reason is that if we want to zip files that are older than 60 minutes,
        # but we scan every 10 minutes and a new file is generated also in 10 minutes,
        # the result will be just a delay between the creation and the zip of old files,
        # every 10 minutes. We wait for longer than that to ensure that all files are older than max age.
        sleep_offset = max_age_seconds + 10
        logger.info(f"Sleeping for {str(datetime.timedelta(seconds=sleep_offset))}...")
        time.sleep(sleep_offset)


if __name__ == "__main__":
    main()
