import gzip
import http
import json
import os
import shutil
import time
from typing import Any, Callable, Dict, List

import loguru
import requests
import speedtest
from loguru import logger
from typedefs import OnlineStatus


def formatter(record: "loguru.Record") -> str:
    # Note this function returns the string to be formatted, not the actual message to be logged
    record["extra"]["serialized"] = json.dumps(record["message"])
    return "{extra[serialized]}\n"


def is_online() -> bool:
    return get_latency() > 0


def get_latency() -> float:
    try:
        servers: List[str] = []
        st = speedtest.Speedtest()
        st.get_servers(servers)
        best_server = st.get_best_server()
        ping = best_server["latency"]
        return float(ping)
    except Exception:
        return -1.0


class TelemetryEngine:
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        label: str,
        endpoint: str,
        s3_endpoint: str,
        create_record: Callable[[Any], Any],
        interval: float,
        max_file_size: int,
        max_file_retention: int,
        buffer_folder: str,
        log_buffer: loguru._logger.Logger,  # type: ignore
    ):
        self.buffer_file = f"{buffer_folder}/{label}_usage.log"
        self.buffer_folder = buffer_folder

        self.telemetry_endpoint = endpoint
        self.telemetry_s3_endpoint = s3_endpoint
        self.create_record = create_record
        self.interval = interval

        self.log_buffer = log_buffer
        self.log_buffer.add(
            self.buffer_file,
            rotation=max_file_size,
            retention=max_file_retention,
            format=formatter,
            compression="gz",
        )

    def __call__(self) -> None:
        order = 0
        while True:
            order += 1
            record = self.create_record(order)
            if self.save(record) == "online":
                self.process_buffered_records()
            time.sleep(self.interval)

    def upload_file(self, file: str) -> bool:
        """
        This method requests to telemetry API a presigned url and upload the local archived files.
        """
        logger.info(f"uploading file... {file}")
        try:
            response = requests.get(self.telemetry_s3_endpoint, timeout=5).json()
            with open(file, "rb") as fh:
                files = {"file": (file, fh)}
                r = requests.post(response["url"], data=response["fields"], files=files, timeout=300)
                if r.status_code == http.client.NO_CONTENT:
                    logger.info("[Success!]")
                    return True
        except Exception as error:
            logger.info("Ground Control to Major Tom. Your circuit's dead, there's something wrong.")
            logger.error(f"error upload log file: {error}")

        return False

    def process_buffered_records(self) -> None:
        """
        Check in the buffered folder if there are archived logs to upload. If the agent connects before an archive
        is created it will also archive the current buffer file and upload it.
        """
        for file in os.listdir(self.buffer_folder):
            file_path = os.path.join(self.buffer_folder, file)

            # Upload regular archive
            if file_path.endswith(".log.gz") and self.upload_file(file_path):
                os.remove(file_path)
                continue

            # Archive current buffer and upload it
            if file_path == self.buffer_file and os.path.getsize(file_path):
                timestamp = int(time.time())
                tmp_name = file_path.replace(".log", f".{timestamp}.log.gz")
                with open(file_path, "rb") as f_in, gzip.open(tmp_name, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                os.remove(file_path)
                if self.upload_file(tmp_name):
                    os.remove(tmp_name)
        with open(self.buffer_file, "w", encoding="utf-8"):
            # create new empty file if not there
            pass

    def save(self, record: Dict[str, Any]) -> OnlineStatus:
        """
        Try to POST the telemetry payload, if it fails for any reason, we buffer it locally.
        """
        try:
            r = requests.post(self.telemetry_endpoint, json=record, timeout=5)
            if r.status_code == http.client.CREATED:
                return OnlineStatus.ONLINE
        except Exception as error:
            logger.info("Ground Control to Major Tom. Your circuit's dead, there's something wrong.")
            logger.error(f"error posting telemetry to Ground Control: {error}")

        self.log_buffer.info(record)
        return OnlineStatus.OFFLINE
