#!/usr/bin/env python3

import argparse
import datetime
import glob
import logging
import os
import pathlib
import time
import zipfile
from typing import List

from commonwealth.utils.general import delete_everything
from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger

SERVICE_NAME = "log-zipper"


def zip_files(files: List[str], output_path: str) -> None:
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipper:
        for file in files:
            logger.debug(f"Zipping {file}...")
            zipper.write(file)

    for file in files:
        try:
            delete_everything(pathlib.Path(file))
            logger.debug(f"Deleted file: {file}")
        except OSError as e:
            logger.debug(f"Error deleting file: {file} - {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Periodically scan a directory and zip files older than one hour")
    parser.add_argument("path", help="Directory path or glob to scan")
    parser.add_argument("-p", "--period", type=int, default=600, help="Interval in seconds to scan the directory")
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
            zipped_file = f"{folder}/{folder_name}-{timestamp}.zip"
            zip_files(local_files, zipped_file)
            logger.info(f"Created zip archive {zipped_file} with {len(local_files)} files.")

        logger.info(f"Sleeping for {str(datetime.timedelta(minutes=max_age))}...")
        time.sleep(args.period)


if __name__ == "__main__":
    main()
