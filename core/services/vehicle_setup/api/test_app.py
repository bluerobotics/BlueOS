"""The real app under a real uvicorn: checks the websocket library is installed and the upgrade is served.

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
async def test_websocket_sends_the_current_value_on_subscribe() -> None:
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
                    websocket = await session.ws_connect(f"http://127.0.0.1:{port}/ws")
                    break
                except aiohttp.ClientConnectionError:
                    await asyncio.sleep(0.05)
            async with websocket:
                await websocket.send_json({"subscribe": f"vehicle-setup/state/{GYRO}"})
                assert await websocket.receive_json() == {"topic": f"vehicle-setup/state/{GYRO}", "payload": None}
            async with session.get(f"http://127.0.0.1:{port}/v1.0/state/{GYRO}") as response:
                assert response.status == 200 and await response.json() is None
            for unknown in ("nothing", "calibration", "calibration/magnetometer"):
                async with session.get(f"http://127.0.0.1:{port}/v1.0/state/{unknown}") as response:
                    assert response.status == 404
    finally:
        server.terminate()
        server.wait(5)
        listener.close()
