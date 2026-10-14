import asyncio
import base64
import os
import struct
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

_SERVICE_DIRECTORY = str(Path(__file__).resolve().parent)
sys.path.insert(0, _SERVICE_DIRECTORY)

import main
import mcap_index

MCAP_MAGIC = mcap_index.MCAP_MAGIC


@pytest.fixture(autouse=True)
def clear_recording_footer_cache() -> None:
    mcap_index.recording_footer_cache.clear()
    main.repair_jobs.clear()


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


def build_chunk_payload(
    start_time: int,
    end_time: int,
    compression: str,
    records_size: int,
    body_fill: bytes = b"",
) -> bytes:
    body = body_fill if len(body_fill) == records_size else (b"\x00" * records_size)
    return (
        struct.pack("<QQQI", start_time, end_time, records_size * 2, 0)
        + prefixed_string(compression)
        + struct.pack("<Q", records_size)
        + body
    )


def build_message_index_payload(channel_id: int, entry_count: int) -> bytes:
    entries_byte_length = entry_count * 16
    return struct.pack("<HI", channel_id, entries_byte_length) + (b"\x00" * entries_byte_length)


def build_chunked_mcap(
    *,
    chunks: list[tuple[int, int, str, int, list[tuple[int, int]]]],
    leading_records: list[bytes] | None = None,
    trailing: bytes = b"",
    chunk_body_fill: bytes | None = None,
) -> bytes:
    data = bytearray(MCAP_MAGIC)
    if leading_records:
        data.extend(b"".join(leading_records))
    for start_time, end_time, compression, records_size, message_indexes in chunks:
        body_fill = chunk_body_fill if chunk_body_fill is not None else b""
        chunk_payload = build_chunk_payload(
            start_time,
            end_time,
            compression,
            records_size,
            body_fill=body_fill,
        )
        data.extend(mcap_record(0x06, chunk_payload))
        for channel_id, entry_count in message_indexes:
            data.extend(mcap_record(0x07, build_message_index_payload(channel_id, entry_count)))
    data.extend(trailing)
    return bytes(data)


def walk_mcap_index_pages(mcap_path: Path, page_limit: int) -> list[mcap_index.RecordingIndex]:
    pages: list[mcap_index.RecordingIndex] = []
    offset = 0
    while True:
        page = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=offset, limit=page_limit)
        pages.append(page)
        if page.closed or page.offset >= page.size:
            break
        if page.offset == offset:
            break
        offset = page.offset
    return pages


def merge_paged_chunk_indexes(
    pages: list[mcap_index.RecordingIndex],
) -> tuple[list[mcap_index.ChunkIndexEntry], dict[str, str]]:
    chunks: list[mcap_index.ChunkIndexEntry] = []
    message_counts: dict[str, str] = {}
    for page in pages:
        chunks.extend(page.chunks)
        for channel_id, count in page.message_counts.items():
            message_counts[channel_id] = str(int(message_counts.get(channel_id, "0")) + int(count))
    return chunks, message_counts


def test_recording_state_priority() -> None:
    assert main.recording_state("live.mcap", True, (100, 200)) == "recording"
    assert main.recording_state("live.mcap", False, (100, 200)) == "ready"
    assert main.recording_state("live.mcap", False, None) == "needs_repair"
    assert main.recording_state("live.mcap", False, (0, 0)) == "needs_repair"
    main.repair_jobs["repairing.mcap"] = main.RepairJob()
    assert main.recording_state("repairing.mcap", False, (100, 200)) == "repairing"
    main.repair_jobs.pop("repairing.mcap")


def test_interrupted_repairs_are_discarded_but_recordings_are_kept(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(main, "ensure_recorder_dir", lambda: tmp_path)
    leftover = tmp_path / f"tmp1234{main.RECOVER_SUFFIX}"
    leftover.write_bytes(b"partial copy")
    recording = tmp_path / "recorder.mcap"
    recording.write_bytes(b"a recording")

    main.discard_interrupted_repairs()

    assert not leftover.exists()
    assert recording.exists()


def test_cancelled_repair_is_not_reported_as_a_failure() -> None:
    async def refuse(*_args: object) -> None:
        raise main.RepairFailed("mcap recover exited with -15")

    original = main.recover_mcap
    main.recover_mcap = refuse  # type: ignore[assignment]
    try:
        main.repair_jobs["cancelled.mcap"] = main.RepairJob(cancelled=True)
        asyncio.run(main.process_recording(Path("cancelled.mcap"), "cancelled.mcap"))
        assert "cancelled.mcap" not in main.repair_jobs

        main.repair_jobs["broken.mcap"] = main.RepairJob()
        asyncio.run(main.process_recording(Path("broken.mcap"), "broken.mcap"))
        assert main.repair_jobs.pop("broken.mcap").error == "mcap recover exited with -15"
    finally:
        main.recover_mcap = original  # type: ignore[assignment]


def test_read_input_offset_follows_the_kernel_file_position(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"0" * 4096)
    # Unbuffered, so the descriptor offset matches what was asked for rather than a read-ahead block.
    with sample.open("rb", buffering=0) as handle:
        handle.read(1024)
        assert main.read_input_offset(os.getpid(), sample) == 1024
    assert main.read_input_offset(os.getpid(), sample) is None


def test_created_from_filename_prefers_embedded_timestamp() -> None:
    stat = os.stat_result((0, 0, 0, 0, 0, 0, 1000.0, 2000.0, 0, 0))
    created = main.created_from_filename("recorder_20240102_030405.mcap", stat)
    assert created == main.parse_utc_timestamp("20240102", "030405")


def test_created_from_filename_reads_copy_snapshot_and_legacy_split_names() -> None:
    stat = os.stat_result((0, 0, 0, 0, 0, 0, 1000.0, 2000.0, 0, 0))
    copy = main.created_from_filename("recorder_20240102_030405.copy-2024-01-02T04-05-06Z.mcap", stat)
    snapshot = main.created_from_filename("recorder_20240102_030405.snapshot-2024-01-02T04-05-06Z.mcap", stat)
    legacy = main.created_from_filename("recorder_20240102_030405_split_20240102_040506.mcap", stat)
    expected = main.parse_utc_timestamp("20240102", "040506")
    assert copy == expected
    assert snapshot == expected
    assert legacy == expected


def test_read_mcap_footer_without_summary_offset_section(tmp_path: Path) -> None:
    mcap_path = tmp_path / "indexed.mcap"
    mcap_path.write_bytes(build_indexed_mcap(summary_offset_start=0))

    footer = mcap_index.read_mcap_footer(mcap_path)
    assert footer is not None
    assert footer[0] > 0
    assert mcap_index.mcap_is_indexed(mcap_path)


def test_resolve_recording_rejects_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder_dir = tmp_path / "recorder"
    recorder_dir.mkdir()
    outside = tmp_path / "outside.mcap"
    outside.write_bytes(b"not-a-recording")
    monkeypatch.setattr(main, "RECORDER_DIR", recorder_dir)

    with pytest.raises(HTTPException) as error:
        main.resolve_recording("../outside.mcap")
    assert error.value.status_code == 400


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
    original = mcap_index.read_mcap_footer

    def counting_read(mcap_path: Path, size: int | None = None) -> tuple[int, int] | None:
        reads["count"] += 1
        return original(mcap_path, size=size)

    monkeypatch.setattr(mcap_index, "read_mcap_footer", counting_read)

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
    original = mcap_index.read_mcap_footer

    def counting_read(mcap_path: Path, size: int | None = None) -> tuple[int, int] | None:
        reads["count"] += 1
        return original(mcap_path, size=size)

    monkeypatch.setattr(mcap_index, "read_mcap_footer", counting_read)

    files = await main.list_recordings()
    assert reads["count"] == 0
    assert files[0].state == "recording"


def test_walk_mcap_index_chunks_and_message_indexes(tmp_path: Path) -> None:
    schema = mcap_record(0x03, prefixed_string("schema") + prefixed_string("encoding") + b"data")
    channel = mcap_record(
        0x04,
        struct.pack("<H", 1) + prefixed_string("topic") + prefixed_string("encoding") + struct.pack("<I", 1),
    )
    mcap_bytes = build_chunked_mcap(
        leading_records=[schema, channel],
        chunks=[
            (1_000, 2_000, "lz4", 100, [(1, 3), (2, 5)]),
            (3_000, 4_000, "zstd", 200, [(2, 2), (1, 1)]),
            (5_000, 6_000, "lz4", 150, [(1, 4)]),
        ],
    )
    mcap_path = tmp_path / "chunked.mcap"
    mcap_path.write_bytes(mcap_bytes)

    index = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=0, limit=2000)
    assert index.size == len(mcap_bytes)
    assert index.offset == len(mcap_bytes)
    assert index.closed is False
    assert len(index.chunks) == 3
    assert index.chunks[0].start_time == "1000"
    assert index.chunks[0].end_time == "2000"
    assert index.chunks[0].compression == "lz4"
    assert index.chunks[0].compressed_size == 100
    assert index.chunks[0].uncompressed_size == 200
    assert index.chunks[0].channel_ids == [1, 2]
    first_message_index_length = (9 + len(build_message_index_payload(1, 3))) + (
        9 + len(build_message_index_payload(2, 5))
    )
    assert index.chunks[0].message_index_length == first_message_index_length
    assert index.chunks[0].offset == len(MCAP_MAGIC) + len(schema) + len(channel)
    assert index.chunks[0].length == 9 + len(build_chunk_payload(1_000, 2_000, "lz4", 100))
    assert index.message_counts == {"1": "8", "2": "7"}
    assert base64.standard_b64decode(index.records) == schema + channel


def test_walk_mcap_index_truncated_record_stops_at_start(tmp_path: Path) -> None:
    complete = build_chunked_mcap(
        chunks=[(1_000, 2_000, "lz4", 50, [(1, 1)])],
    )
    second_chunk = mcap_record(0x06, build_chunk_payload(3_000, 4_000, "lz4", 60))
    truncated = complete + second_chunk[:15]
    mcap_path = tmp_path / "truncated.mcap"
    mcap_path.write_bytes(truncated)

    index = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=0, limit=2000)
    assert len(index.chunks) == 1
    assert index.offset == len(complete)
    assert index.closed is False


def test_walk_mcap_index_resume_from_offset(tmp_path: Path) -> None:
    mcap_bytes = build_chunked_mcap(
        chunks=[
            (1_000, 2_000, "lz4", 50, [(1, 1)]),
            (3_000, 4_000, "lz4", 60, [(2, 2)]),
            (5_000, 6_000, "lz4", 70, [(1, 3)]),
        ],
    )
    mcap_path = tmp_path / "resume.mcap"
    mcap_path.write_bytes(mcap_bytes)

    first = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=0, limit=1)
    assert len(first.chunks) == 1
    assert first.chunks[0].start_time == "1000"

    second = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=first.offset, limit=2000)
    assert len(second.chunks) == 2
    assert second.chunks[0].start_time == "3000"
    assert second.chunks[1].start_time == "5000"
    assert second.offset == len(mcap_bytes)


def test_walk_mcap_index_limit_caps_chunks(tmp_path: Path) -> None:
    mcap_bytes = build_chunked_mcap(
        chunks=[
            (1_000, 2_000, "lz4", 40, [(1, 1)]),
            (3_000, 4_000, "lz4", 40, [(1, 1)]),
            (5_000, 6_000, "lz4", 40, [(1, 1)]),
        ],
    )
    mcap_path = tmp_path / "limited.mcap"
    mcap_path.write_bytes(mcap_bytes)

    first = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=0, limit=2)
    assert len(first.chunks) == 2
    second = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=first.offset, limit=2)
    assert len(second.chunks) == 1
    assert second.offset == len(mcap_bytes)


def test_walk_mcap_index_paged_matches_single_walk(tmp_path: Path) -> None:
    mcap_bytes = build_chunked_mcap(
        chunks=[
            (
                index * 1_000,
                index * 1_000 + 500,
                "lz4",
                50 + index,
                [(1, index + 1), (2, index + 2), (3, index + 3)],
            )
            for index in range(7)
        ],
    )
    mcap_path = tmp_path / "paged.mcap"
    mcap_path.write_bytes(mcap_bytes)

    single = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=0, limit=20_000)
    pages = walk_mcap_index_pages(mcap_path, page_limit=2)
    paged_chunks, paged_message_counts = merge_paged_chunk_indexes(pages)

    assert [chunk.model_dump() for chunk in paged_chunks] == [chunk.model_dump() for chunk in single.chunks]
    assert paged_message_counts == single.message_counts

    single_offsets = [chunk.offset for chunk in single.chunks]
    paged_offsets = [chunk.offset for chunk in paged_chunks]
    assert paged_offsets == single_offsets
    assert len(set(paged_offsets)) == len(paged_offsets)

    for page in pages:
        if not page.chunks:
            continue
        last_chunk = page.chunks[-1]
        assert last_chunk.channel_ids == [1, 2, 3]
        assert last_chunk.message_index_length > 0


def test_walk_mcap_index_data_end_sets_closed(tmp_path: Path) -> None:
    mcap_bytes = build_chunked_mcap(
        chunks=[(1_000, 2_000, "lz4", 50, [(1, 1)])],
        trailing=mcap_record(0x0F, b""),
    )
    mcap_path = tmp_path / "finalized.mcap"
    mcap_path.write_bytes(mcap_bytes)

    index = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=0, limit=2000)
    assert index.closed is True
    assert index.offset == len(mcap_bytes)


def test_walk_mcap_index_skips_chunk_bodies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    large_body = b"x" * (2 * 1024 * 1024)
    mcap_bytes = build_chunked_mcap(
        chunks=[(1_000, 2_000, "lz4", len(large_body), [(1, 1)])],
        chunk_body_fill=large_body,
    )
    mcap_path = tmp_path / "large-chunk.mcap"
    mcap_path.write_bytes(mcap_bytes)

    bytes_read = {"value": 0}
    original_open = Path.open

    def counting_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        handle = original_open(self, *args, **kwargs)  # pylint: disable=consider-using-with
        original_read = handle.read

        def counting_read(size: int = -1) -> bytes:
            data = bytes(original_read(size))
            bytes_read["value"] += len(data)
            return data

        handle.read = counting_read
        return handle

    monkeypatch.setattr(Path, "open", counting_open)
    index = mcap_index.walk_mcap_index_sync(mcap_path, from_offset=0, limit=2000)

    assert len(index.chunks) == 1
    assert bytes_read["value"] < mcap_path.stat().st_size // 10


@pytest.mark.asyncio
async def test_get_recording_index_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder_dir = tmp_path / "recorder"
    recorder_dir.mkdir()
    mcap_bytes = build_chunked_mcap(chunks=[(1_000, 2_000, "lz4", 50, [(1, 2)])])
    recording = recorder_dir / "recorder_20240102_030405.mcap"
    recording.write_bytes(mcap_bytes)
    monkeypatch.setattr(main, "RECORDER_DIR", recorder_dir)

    index = await main.get_recording_index("recorder_20240102_030405.mcap", from_offset=0, limit=2000)
    assert index.chunks[0].compression == "lz4"
    assert index.message_counts == {"1": "2"}


@pytest.mark.asyncio
async def test_build_recording_file_includes_index_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder_dir = tmp_path / "recorder"
    recorder_dir.mkdir()
    recording = recorder_dir / "recorder_20240102_030405.mcap"
    recording.write_bytes(build_indexed_mcap())
    monkeypatch.setattr(main, "RECORDER_DIR", recorder_dir)

    file = await main.build_recording_file(recording, recorder_dir, is_open=False)
    assert file.index_url == "/recorder-extractor/v1.0/files/recorder_20240102_030405.mcap/index"
    assert file.download_url == "/userdata/recorder/recorder_20240102_030405.mcap"

    live = await main.build_recording_file(recording, recorder_dir, is_open=True)
    assert live.state == "recording"
    assert live.download_url == "/recorder-extractor/v1.0/files/recorder_20240102_030405.mcap/download"
