import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_api_root_redirects_to_relative_docs(version: str, tmp_path: Path) -> None:
    service_path = Path(__file__).parent
    environment = os.environ | {
        "PYTHONPATH": str(service_path / "api" / version / "routers"),
        "XDG_CONFIG_HOME": str(tmp_path),
    }
    script = 'import asyncio; from index import root; print(asyncio.run(root()).headers["location"])'

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=service_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.stdout == "docs\n"
