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

from commonwealth.utils.general import delete_everything, limit_ram_usage
from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger

SERVICE_NAME = "log-zipper"

limit_ram_usage()


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Periodically scan a directory and zip files older than one hour")
    parser.add_argument("path", help="Directory path or glob to scan")
    parser.add_argument("-a", "--max-age-minutes", type=int, default=10, help="Maximum age for files in minutes")
    args = parser.parse_args()

    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    init_logger(SERVICE_NAME)

    # Enforce path parameter
    if not glob.has_magic(args.path) and not os.path.isdir(args.path):
        parser.error(f"Invalid path: {args.path}")

    # We need to transform from minutes to seconds, since this is what time and st_mtime returns
    max_age_seconds = args.max_age_minutes * 60

    while True:
        now = time.time()
        logger.info(f"Scanning {args.path} for files older than {str(datetime.timedelta(seconds=max_age_seconds))}...")

        # Get the root directories of all files
        files = glob.glob(args.path, recursive=True)
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
            zipped_file = f"{folder}/{folder_name}-{timestamp}.gz"
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
