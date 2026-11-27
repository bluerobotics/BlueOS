"""The real app under a real uvicorn: checks it starts without a zenoh router and serves the states over GET.

It runs in a subprocess, since other services' tests load their own top-level `config` and `api`.
"""

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import aiohttp
import pytest

SERVICE = Path(__file__).resolve().parents[1]
GYRO = "calibration/gyroscope"


@pytest.mark.asyncio
async def test_states_are_served_over_get() -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("COV_CORE_")}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.app:app", "--fd", str(listener.fileno()), "--log-level", "warning"],
        cwd=SERVICE,
        env=environment,
        pass_fds=[listener.fileno()],
    )
    try:
        async with asyncio.timeout(5), aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(f"http://127.0.0.1:{port}/v1.0/state/{GYRO}") as response:
                        assert response.status == 200 and await response.json() is None
                    break
                except aiohttp.ClientConnectionError:
                    await asyncio.sleep(0.05)
            for unknown in ("nothing", "calibration", "calibration/magnetometer"):
                async with session.get(f"http://127.0.0.1:{port}/v1.0/state/{unknown}") as response:
                    assert response.status == 404
    finally:
        server.terminate()
        server.wait(5)
        listener.close()
