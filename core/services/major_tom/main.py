#! /usr/bin/env python3
import copy
import datetime
import logging
import sys
import time
import uuid
from typing import Any, Dict
from zoneinfo import ZoneInfo

import loguru
from commonwealth.utils.general import (
    local_hardware_identifier,
    local_unique_identifier,
)
from commonwealth.utils.logs import init_logger

from src.core import TelemetryEngine, get_latency
from src.metrics import Metrics
from src.typedefs import AnonymousTelemetryRecord, DefaultPayload

LOG_SESSION_UUID = str(uuid.uuid4())

SERVICE_NAME = "major_tom"
LOG_FOLDER_PATH = f"/var/logs/blueos/services/{SERVICE_NAME}/buffer"

TELEMETRY_ENDPOINT = "https://telemetry.blueos.cloud/api/v1/anonymous/"
S3_TELEMETRY_ENDPOINT = "https://telemetry.blueos.cloud/api/v1/anonymous/s3/"


def compose_default_record(order: int) -> Dict[str, Any]:
    date_time_utc = datetime.datetime.now(ZoneInfo("UTC")).isoformat()
    payload = DefaultPayload(
        log_session_uuid=LOG_SESSION_UUID,
        order=order,
        timestamp=date_time_utc,
        hardware_id=local_hardware_identifier(),
        blueos_id=local_unique_identifier(),
        data=None,
    )

    start_probing = time.time()
    metrics = Metrics()
    record = AnonymousTelemetryRecord(
        time.clock_gettime(time.CLOCK_BOOTTIME),
        get_latency(),
        metrics.memory.total,
        metrics.memory.used,
        metrics.disk.total,
        metrics.disk.used,
        metrics.installed_extensions,
        metrics.installed_version,
        0,
    )
    record.probe_time = time.time() - start_probing
    payload.data = record
    return payload.json()


if __name__ == "__main__":

    # this is required to have two loggers in the same process
    # see https://loguru.readthedocs.io/en/latest/resources/recipes.html#creating-independent-loggers-with-separate-set-of-handlers
    loguru.logger.remove()
    log_buffer = copy.deepcopy(loguru.logger)

    logging.basicConfig(level=logging.INFO)
    loguru.logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    init_logger(SERVICE_NAME)
    loguru.logger.info(f"Starting Major Tom, session UUID: {LOG_SESSION_UUID}")
    TelemetryEngine(
        label="anonymous",  # used to tag telemetry type. we may have non-anonymous telemetry in the future
        endpoint=TELEMETRY_ENDPOINT,
        s3_endpoint=S3_TELEMETRY_ENDPOINT,
        create_record=compose_default_record,
        interval=60 * 5,  # 5 minutes
        max_file_size=1024 * 1024,  # 1Mb
        max_file_retention=10,
        buffer_folder=LOG_FOLDER_PATH,
        log_buffer=log_buffer,
    )()
