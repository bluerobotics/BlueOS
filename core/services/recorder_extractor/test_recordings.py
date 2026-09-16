import os
import struct
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

_SERVICE_DIRECTORY = str(Path(__file__).resolve().parent)
sys.path.insert(0, _SERVICE_DIRECTORY)

import main

MCAP_MAGIC = main.MCAP_MAGIC


@pytest.fixture(autouse=True)
def clear_recording_footer_cache() -> None:
    main.recording_footer_cache.clear()


def prefixed_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def mcap_record(opcode: int, payload: bytes) -> bytes:
    return bytes([opcode]) + struct.pack("<Q", len(payload)) + payload


def build_indexed_mcap(summary_offset_start: int = 0) -> bytes:
    header = mcap_record(0x01, prefixed_string("") + prefixed_string("test"))
    data = MCAP_MAGIC + header
    summary_start = len(data)
    footer_payload = struct.pack("<QQI", summary_start, summary_offset_start, 0)
    return data + mcap_record(0x02, footer_payload) + MCAP_MAGIC


def test_recording_state_priority() -> None:
    assert main.recording_state("live.mcap", True, (100, 200)) == "recording"
    assert main.recording_state("live.mcap", False, (100, 200)) == "ready"
    assert main.recording_state("live.mcap", False, None) == "needs_repair"
    assert main.recording_state("live.mcap", False, (0, 0)) == "needs_repair"
    main.processing_mcap_files.add("repairing.mcap")
    assert main.recording_state("repairing.mcap", False, (100, 200)) == "repairing"
    main.processing_mcap_files.discard("repairing.mcap")


def test_created_from_filename_prefers_embedded_timestamp() -> None:
    stat = os.stat_result((0, 0, 0, 0, 0, 0, 1000.0, 2000.0, 0, 0))
    created = main.created_from_filename("recorder_20240102_030405.mcap", stat)
    assert created == main.parse_utc_timestamp("20240102", "030405")


def test_read_mcap_footer_without_summary_offset_section(tmp_path: Path) -> None:
    mcap_path = tmp_path / "indexed.mcap"
    mcap_path.write_bytes(build_indexed_mcap(summary_offset_start=0))

    footer = main.read_mcap_footer(mcap_path)
    assert footer is not None
    assert footer[0] > 0
    assert main.mcap_is_indexed(mcap_path)


def test_resolve_recording_rejects_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder_dir = tmp_path / "recorder"
    recorder_dir.mkdir()
    outside = tmp_path / "outside.mcap"
    outside.write_bytes(b"not-a-recording")
    monkeypatch.setattr(main, "RECORDER_DIR", recorder_dir)

    with pytest.raises(HTTPException) as error:
        main.resolve_recording("../outside.mcap")
    assert error.value.status_code == 400


def test_copy_recording_prefix_copies_stat_size(tmp_path: Path) -> None:
    source_path = tmp_path / "source.mcap"
    destination_path = tmp_path / "destination.mcap"
    payload = b"abcdefghij" * 20
    source_path.write_bytes(payload)

    main.copy_recording_prefix(source_path, destination_path)

    assert destination_path.read_bytes() == payload


def test_ensure_disk_space_for_split_rejects_when_full(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class DiskUsage:
        free = 10

    monkeypatch.setattr("main.shutil.disk_usage", lambda _path: DiskUsage())
    with pytest.raises(HTTPException) as error:
        main.ensure_disk_space_for_split(tmp_path, 100)
    assert error.value.status_code == 507


@pytest.mark.asyncio
async def test_list_recordings_skips_vanished_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder_dir = tmp_path / "recorder"
    recorder_dir.mkdir()
    kept = recorder_dir / "recorder_20240102_030405.mcap"
    kept.write_bytes(build_indexed_mcap())
    vanished = recorder_dir / "vanished.mcap"
    vanished.write_bytes(b"gone")
    monkeypatch.setattr(main, "RECORDER_DIR", recorder_dir)
    monkeypatch.setattr(main, "open_files_under", lambda _path: set())

    async def recording_is_open(path: Path, _open_files: set[Path] | None) -> bool:
        if path.name == "vanished.mcap":
            path.unlink()
        return False

    monkeypatch.setattr(main, "recording_is_open", recording_is_open)

    files = await main.list_recordings()
    assert [recording.name for recording in files] == ["recorder_20240102_030405.mcap"]


@pytest.mark.asyncio
async def test_list_recordings_reuses_footer_of_unchanged_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder_dir = tmp_path / "recorder"
    recorder_dir.mkdir()
    kept = recorder_dir / "recorder_20240102_030405.mcap"
    kept.write_bytes(build_indexed_mcap())
    monkeypatch.setattr(main, "RECORDER_DIR", recorder_dir)
    monkeypatch.setattr(main, "open_files_under", lambda _path: set())

    reads = {"count": 0}
    original = main.read_mcap_footer

    def counting_read(mcap_path: Path, size: int | None = None) -> tuple[int, int] | None:
        reads["count"] += 1
        return original(mcap_path, size=size)

    monkeypatch.setattr(main, "read_mcap_footer", counting_read)

    first = await main.list_recordings()
    second = await main.list_recordings()
    assert reads["count"] == 1
    assert first[0].state == "ready"
    assert second[0].state == "ready"

    kept.write_bytes(build_indexed_mcap() + b"x")
    third = await main.list_recordings()
    assert reads["count"] == 2
    assert third[0].size_bytes == kept.stat().st_size


@pytest.mark.asyncio
async def test_list_recordings_skips_footer_of_open_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder_dir = tmp_path / "recorder"
    recorder_dir.mkdir()
    live = recorder_dir / "recorder_20240102_030405.mcap"
    live.write_bytes(build_indexed_mcap())
    monkeypatch.setattr(main, "RECORDER_DIR", recorder_dir)
    monkeypatch.setattr(main, "open_files_under", lambda _path: {live.resolve()})

    reads = {"count": 0}
    original = main.read_mcap_footer

    def counting_read(mcap_path: Path, size: int | None = None) -> tuple[int, int] | None:
        reads["count"] += 1
        return original(mcap_path, size=size)

    monkeypatch.setattr(main, "read_mcap_footer", counting_read)

    files = await main.list_recordings()
    assert reads["count"] == 0
    assert files[0].state == "recording"
