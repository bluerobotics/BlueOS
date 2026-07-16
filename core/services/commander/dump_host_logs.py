#!/usr/bin/env python3
"""Collect host diagnostics into the system logs folder for support downloads."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Dict, List, Optional, Tuple

from loguru import logger

DEFAULT_OUTPUT_DIR = Path(os.environ.get("BLUEOS_LOG_FOLDER_PATH", "/var/logs/blueos")) / "host_diagnostics"


async def _run(command: str) -> Tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "bash",
        "-lc",
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    returncode = process.returncode if process.returncode is not None else 1
    return (
        returncode,
        stdout_bytes.decode(errors="replace"),
        stderr_bytes.decode(errors="replace"),
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", errors="replace")


# Dump file preamble: "# <title>", "# generated: <UTC ISO>", "# command: …", "# return_code: …",
# optional "# stderr:" block, then a "#====…" separator. Consumers of the zip can rely on this.
def _header(title: str, command: str, returncode: int, stderr: str) -> str:
    header = (
        f"# {title}\n"
        f"# generated: {datetime.now(timezone.utc).isoformat()}\n"
        f"# command: {command}\n"
        f"# return_code: {returncode}\n"
    )
    if stderr.strip():
        header += f"# stderr:\n{stderr.rstrip()}\n"
    header += "#" + "=" * 60 + "\n\n"
    return header


async def dump_journal(output_dir: Path, boot_index: int, filename: str) -> Optional[str]:
    command = f"journalctl -b {boot_index} --no-pager --output=short-iso"
    returncode, stdout, stderr = await _run(command)
    if returncode != 0 and not stdout.strip():
        logger.warning(f"Failed to dump journal boot {boot_index}: {stderr}")
        return f"journal/{filename}: failed ({stderr.strip() or returncode})"

    _write_text(
        output_dir / "journal" / filename,
        _header(f"journalctl boot index {boot_index}", command, returncode, stderr) + stdout,
    )
    return None


async def dump_dmesg(output_dir: Path) -> Optional[str]:
    stderr = ""
    returncode = 1
    for command in ("dmesg --ctime --color=never", "dmesg -T", "dmesg"):
        returncode, stdout, stderr = await _run(command)
        if returncode == 0 or stdout.strip():
            _write_text(
                output_dir / "kernel" / "dmesg.log",
                _header("dmesg", command, returncode, stderr) + stdout,
            )
            return None

    logger.warning(f"Failed to dump dmesg: {stderr}")
    return f"kernel/dmesg.log: failed ({stderr.strip() or returncode})"


async def dump_kernel_journal(output_dir: Path) -> Optional[str]:
    command = "journalctl -k -b 0 --no-pager --output=short-iso"
    returncode, stdout, stderr = await _run(command)
    if returncode != 0 and not stdout.strip():
        logger.warning(f"Failed to dump kernel journal: {stderr}")
        return f"kernel/journal_kernel.log: failed ({stderr.strip() or returncode})"

    _write_text(
        output_dir / "kernel" / "journal_kernel.log",
        _header("journalctl -k (current boot)", command, returncode, stderr) + stdout,
    )
    return None


async def dump_lsusb(output_dir: Path) -> Optional[str]:
    command = "lsusb -v"
    returncode, stdout, stderr = await _run(command)
    command_label = command
    if returncode != 0 or not stdout.strip():
        # usbutils is not shipped in blueos-core; privileged sysfs still has the data.
        command = r"""
set +e
if [ -r /sys/kernel/debug/usb/devices ]; then
  cat /sys/kernel/debug/usb/devices
  exit 0
fi
for d in /sys/bus/usb/devices/[0-9]*; do
  [ -d "$d" ] || continue
  echo "=== $(basename "$d") ==="
  for f in idVendor idProduct manufacturer product serial speed devnum busnum; do
    [ -f "$d/$f" ] && printf '%s: %s\n' "$f" "$(cat "$d/$f")"
  done
  echo
done
"""
        command_label = "sysfs usb dump"
        returncode, stdout, stderr = await _run(command)

    if returncode != 0 and not stdout.strip():
        logger.warning(f"Failed to dump USB devices: {stderr}")
        return f"host/lsusb.txt: failed ({stderr.strip() or returncode})"

    _write_text(
        output_dir / "host" / "lsusb.txt",
        _header("USB devices", command_label, returncode, stderr) + stdout,
    )
    return None


async def dump_snapshot(output_dir: Path) -> Optional[str]:
    blueos_version = os.environ.get("GIT_DESCRIBE_TAGS", "unknown")
    script = r"""
set +e
sep() { printf '\n### %s\n' "$1"; }

sep "OS release / kernel"
cat /etc/os-release 2>/dev/null
echo
uname -a

sep "Uptime / load"
uptime
cat /proc/loadavg

sep "Memory"
free -m

sep "Disk"
df -h

sep "Time"
timedatectl 2>/dev/null || date -u

sep "Network addresses"
ip -br addr 2>/dev/null || ip addr
echo
ip route

sep "Docker containers"
docker ps -a

sep "Docker info (summary)"
docker info 2>&1 | head -n 80

sep "Raspberry Pi throttled / temp / firmware"
vcgencmd get_throttled 2>/dev/null
vcgencmd measure_temp 2>/dev/null
vcgencmd version 2>/dev/null
vcgencmd bootloader_version 2>/dev/null
[ -f /sys/class/thermal/thermal_zone0/temp ] && echo "thermal_zone0: $(cat /sys/class/thermal/thermal_zone0/temp)"

sep "Hardware / machine ids"
echo hardware-uuid:
cat /etc/blueos/hardware-uuid 2>/dev/null
echo
echo machine-id:
cat /etc/machine-id 2>/dev/null

sep "USB topology"
ls -1 /sys/bus/usb/devices 2>/dev/null
"""
    returncode, stdout, stderr = await _run(script)

    body = [
        "# Host diagnostic snapshot",
        f"# generated: {datetime.now(timezone.utc).isoformat()}",
        f"# blueos_version: {blueos_version}",
        f"# return_code: {returncode}",
        "#" + "=" * 60,
        "",
        "### BlueOS version (from core container)",
        blueos_version,
        "",
    ]
    if stderr.strip():
        body.extend(["### collector stderr", stderr.rstrip(), ""])
    body.append(stdout if stdout.strip() else "# (empty snapshot stdout)")

    try:
        _write_text(output_dir / "host" / "snapshot.txt", "\n".join(body) + "\n")
    except Exception as error:  # noqa: BLE001
        logger.error(f"Failed to write host snapshot: {error}")
        return f"host/snapshot.txt: failed ({error})"
    return None


async def prepare_system_logs(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    """Dump host diagnostics into output_dir. Best-effort; does not raise on section failures."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks: List[Awaitable[Optional[str]]] = [
        dump_journal(output_dir, 0, "current_boot.log"),
        dump_journal(output_dir, -1, "previous_boot.log"),
        dump_dmesg(output_dir),
        dump_kernel_journal(output_dir),
        dump_lsusb(output_dir),
        dump_snapshot(output_dir),
    ]

    errors: List[str] = []
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            logger.error(f"Diagnostic dump task failed: {result}")
            errors.append(str(result))
        elif result:
            errors.append(result)

    logger.info(f"Host diagnostics written to {output_dir} (errors={len(errors)})")
    return {"output_dir": str(output_dir), "errors": errors}
