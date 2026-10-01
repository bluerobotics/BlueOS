import asyncio
import os
import pathlib
import pty

import pytest
from exceptions import FirmwareUploadFail
from firmware.FirmwareUpload import FirmwareUploader

# Mimics ArduPilot's uploader.py: no explicit flush and, after refusing a firmware for another board, retries forever
MISMATCHED_BOARD_UPLOADER = """
with open(os.path.join(os.path.dirname(__file__), "uploader.pid"), "w", encoding="utf-8") as pid_file:
    pid_file.write(str(os.getpid()))
print("WARNING: Firmware not suitable for this board (board_type=9 (fmuv3) board_id=1013 (None))")
while True:
    time.sleep(1)
"""

FAILING_UPLOADER = """
sys.exit("ERROR: Program CRC failed")
"""


def install_fake_uploader(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    uploader_path = tmp_path / FirmwareUploader.binary_name()
    header = '#!/usr/bin/env python3\nimport os\nimport sys\nimport time\n\nif "--help" in sys.argv:\n    sys.exit(0)\n'
    uploader_path.write_text(header + body, encoding="utf-8")
    uploader_path.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")


@pytest.mark.timeout(30)
def test_upload_fails_fast_on_board_id_mismatch(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_uploader(tmp_path, monkeypatch, MISMATCHED_BOARD_UPLOADER)
    bootloader, autopilot_port = pty.openpty()
    uploader = FirmwareUploader()
    uploader.set_autopilot_port(pathlib.Path(os.ttyname(autopilot_port)))

    with pytest.raises(FirmwareUploadFail, match="Firmware not suitable for this board"):
        asyncio.run(uploader.upload(tmp_path / "custom.apj"))

    uploader_pid = int((tmp_path / "uploader.pid").read_text(encoding="utf-8"))
    assert not pathlib.Path(f"/proc/{uploader_pid}").exists(), "uploader process was left running"
    os.set_blocking(bootloader, False)
    boot_command = os.read(bootloader, 16)
    os.close(bootloader)
    os.close(autopilot_port)
    assert boot_command == b"\x30\x20", "bootloader was not asked to boot the existing firmware"


@pytest.mark.timeout(30)
def test_upload_reports_uploader_failure(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_uploader(tmp_path, monkeypatch, FAILING_UPLOADER)

    with pytest.raises(FirmwareUploadFail, match="non-zero code 1.*Program CRC failed"):
        asyncio.run(FirmwareUploader().upload(tmp_path / "custom.apj"))
