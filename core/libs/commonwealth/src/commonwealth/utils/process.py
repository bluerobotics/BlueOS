"""Helpers for retrieving process metadata used in telemetry publishing."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_process_name() -> str:
    """Return a human-readable name for the current process."""
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0:
        candidate = Path(argv0)
        if candidate.name:
            return candidate.name

    executable = getattr(sys, "executable", "") or ""
    if executable:
        name = Path(executable).name
        if name:
            return name

    return f"pid-{os.getpid()}"

