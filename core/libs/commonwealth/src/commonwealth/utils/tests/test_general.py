import sys

import pytest

from ..general import run_subprocess


@pytest.mark.asyncio
async def test_run_subprocess_captures_stdout_and_stderr() -> None:
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write('out'); sys.stderr.write('err')",
    ]
    returncode, stdout, stderr = await run_subprocess(command)

    assert returncode == 0
    assert stdout == b"out"
    assert stderr == b"err"


@pytest.mark.asyncio
async def test_run_subprocess_returns_nonzero_returncode() -> None:
    command = [sys.executable, "-c", "import sys; sys.exit(3)"]
    returncode, _stdout, _stderr = await run_subprocess(command)

    assert returncode == 3


@pytest.mark.asyncio
async def test_run_subprocess_merge_stderr_folds_into_stdout() -> None:
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write('out'); sys.stderr.write('err')",
    ]
    returncode, stdout, stderr = await run_subprocess(command, merge_stderr=True)

    assert returncode == 0
    assert stdout == b"outerr"
    assert stderr == b""
