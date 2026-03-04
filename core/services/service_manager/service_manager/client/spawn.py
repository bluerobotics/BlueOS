"""Daemon auto-spawn logic."""
# pylint: disable=import-outside-toplevel

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from service_manager.config import AgentConfig
from service_manager.daemon import PidLock


def spawn_daemon(config_path: Path | None = None, timeout: float = 10.0) -> bool:
    """
    Spawn the daemon if not running.

    Returns True if daemon is running (either already or after spawn).
    """
    config = AgentConfig.load_or_default(config_path)

    # Check if already running via PID file
    if PidLock.is_running(config.pid_file):
        return True

    # Spawn daemon
    args = [sys.executable, "-m", "service_manager"]
    if config_path:
        args.extend(["--config", str(config_path)])

    try:
        # pylint: disable-next=consider-using-with
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        print(f"Failed to spawn daemon: {e}", file=sys.stderr)
        return False

    # Wait for daemon to become available
    from service_manager.client.http import ServiceManagerClient

    client = ServiceManagerClient(config.base_url)
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        if client.is_available():
            return True
        time.sleep(0.2)

    # Check PID file as fallback
    return PidLock.is_running(config.pid_file)


def ensure_daemon(config_path: Path | None = None) -> bool:
    """Ensure daemon is running, spawn if needed."""
    from service_manager.client.http import ServiceManagerClient

    config = AgentConfig.load_or_default(config_path)
    client = ServiceManagerClient(config.base_url)

    if client.is_available():
        return True

    return spawn_daemon(config_path)
