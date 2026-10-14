"""Paged chunk index for recordings that may have no summary yet.

A full MCAP reader decompresses every chunk body. Playback only needs headers and
message-index channel ids so nginx can Range-request the bodies, so this walk
parses record headers then seeks past payloads.
"""

from __future__ import annotations

import asyncio
import base64
import struct
from enum import IntEnum
from os import stat_result
from pathlib import Path
from typing import IO, Dict, List

from loguru import logger
from pydantic import BaseModel

# Same eight bytes the MCAP spec uses for file magic.
MCAP_MAGIC = bytes((137, 77, 67, 65, 80, 48, 13, 10))
MAGIC_SIZE = 8
RECORD_HEADER_SIZE = 9
FOOTER_RECORD_SIZE = RECORD_HEADER_SIZE + 20


class Opcode(IntEnum):
    HEADER = 0x01
    FOOTER = 0x02
    SCHEMA = 0x03
    CHANNEL = 0x04
    CHUNK = 0x06
    MESSAGE_INDEX = 0x07
    METADATA = 0x0C
    DATA_END = 0x0F


class EndOfFile(Exception):
    pass


class ReadDataStream:
    def __init__(self, stream: IO[bytes]) -> None:
        self._count = 0
        self._stream = stream

    @property
    def count(self) -> int:
        return self._count

    def read(self, length: int) -> bytes:
        if length == 0:
            return b""
        data = self._stream.read(length)
        self._count += len(data)
        if data == b"":
            raise EndOfFile()
        return data

    def read2(self) -> int:
        return int(struct.unpack("<H", self.read(2))[0])

    def read4(self) -> int:
        return int(struct.unpack("<I", self.read(4))[0])

    def read8(self) -> int:
        return int(struct.unpack("<Q", self.read(8))[0])


METADATA_OPCODES = (Opcode.HEADER, Opcode.SCHEMA, Opcode.CHANNEL, Opcode.METADATA)

# ponytail: one walk at a time so a large needs_repair scan cannot saturate the disk; per-file locks
# if concurrent players become common.
index_walk_semaphore = asyncio.Semaphore(1)
# Resolved path -> (inode, size, mtime_ns, footer). Finished files do not grow, so the footer
# is reused until the file is replaced or deleted.
recording_footer_cache: Dict[str, tuple[int, int, int, tuple[int, int] | None]] = {}


class ChunkIndexEntry(BaseModel):
    start_time: str
    end_time: str
    offset: int
    length: int
    compression: str
    compressed_size: int
    uncompressed_size: int
    channel_ids: List[int]
    message_index_length: int


class RecordingIndex(BaseModel):
    size: int
    offset: int
    closed: bool
    chunks: List[ChunkIndexEntry]
    message_counts: Dict[str, str]
    records: str


def read_mcap_footer(mcap_path: Path, size: int | None = None) -> tuple[int, int] | None:
    try:
        if size is None:
            size = mcap_path.stat().st_size
        if size < (MAGIC_SIZE * 2) + FOOTER_RECORD_SIZE:
            return None
        with mcap_path.open("rb") as recording:
            recording.seek(size - MAGIC_SIZE - FOOTER_RECORD_SIZE)
            footer_bytes = recording.read(FOOTER_RECORD_SIZE + MAGIC_SIZE)
    except OSError as exception:
        logger.warning(f"Failed to read MCAP footer of {mcap_path}: {exception}")
        return None

    if len(footer_bytes) != FOOTER_RECORD_SIZE + MAGIC_SIZE or not footer_bytes.endswith(MCAP_MAGIC):
        return None
    if footer_bytes[0] != Opcode.FOOTER:
        return None
    try:
        summary_start, summary_offset_start, _summary_crc = struct.unpack(
            "<QQI", footer_bytes[RECORD_HEADER_SIZE:FOOTER_RECORD_SIZE]
        )
    except struct.error:
        return None
    return summary_start, summary_offset_start


def mcap_is_indexed(mcap_path: Path) -> bool:
    footer = read_mcap_footer(mcap_path)
    return footer is not None and footer[0] > 0


def footer_for_listing(path: Path, stat: stat_result, *, is_open: bool) -> tuple[int, int] | None:
    if is_open:
        return None
    cache_key = str(path.resolve())
    identity = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
    cached = recording_footer_cache.get(cache_key)
    if cached is not None and cached[:3] == identity:
        return cached[3]
    footer = read_mcap_footer(path, size=stat.st_size)
    recording_footer_cache[cache_key] = (*identity, footer)
    return footer


def prune_recording_footer_cache(keep: set[str]) -> None:
    for cache_key in [key for key in recording_footer_cache if key not in keep]:
        recording_footer_cache.pop(cache_key, None)


def _parse_chunk_index_entry(
    recording: IO[bytes],
    record_start: int,
    record_span: int,
    payload_length: int,
) -> ChunkIndexEntry | None:
    # Same field order as `mcap.records.Chunk.read`, without pulling the compressed body into memory.
    if payload_length < 40:
        return None
    stream = ReadDataStream(recording)
    try:
        message_start_time = stream.read8()
        message_end_time = stream.read8()
        uncompressed_size = stream.read8()
        stream.read4()
        compression_length = stream.read4()
        if payload_length < 40 + compression_length:
            return None
        compression = str(stream.read(compression_length), "utf-8")
        compressed_size = stream.read8()
    except (EndOfFile, UnicodeDecodeError, struct.error):
        return None
    if payload_length < stream.count + compressed_size:
        return None
    return ChunkIndexEntry(
        start_time=str(message_start_time),
        end_time=str(message_end_time),
        offset=record_start,
        length=record_span,
        compression=compression,
        compressed_size=compressed_size,
        uncompressed_size=uncompressed_size,
        channel_ids=[],
        message_index_length=0,
    )


def _apply_message_index(
    recording: IO[bytes],
    current_chunk: ChunkIndexEntry,
    record_span: int,
    payload_length: int,
    message_counts: Dict[str, str],
) -> bool:
    stream = ReadDataStream(recording)
    try:
        channel_id = stream.read2()
        entries_byte_length = stream.read4()
    except (EndOfFile, struct.error):
        return False
    if payload_length < stream.count:
        return False
    if channel_id not in current_chunk.channel_ids:
        current_chunk.channel_ids.append(channel_id)
    current_chunk.message_index_length += record_span
    key = str(channel_id)
    message_counts[key] = str(int(message_counts.get(key, "0")) + entries_byte_length // 16)
    return True


class McapIndexWalker:
    def __init__(self, size: int, from_offset: int) -> None:
        self.size = size
        self.offset = from_offset
        self.closed = False
        self.chunks: List[ChunkIndexEntry] = []
        self.message_counts: Dict[str, str] = {}
        self.records_bytes = bytearray()
        self.current_chunk: ChunkIndexEntry | None = None

    def to_index(self) -> RecordingIndex:
        records = base64.standard_b64encode(self.records_bytes).decode("ascii") if self.records_bytes else ""
        return RecordingIndex(
            size=self.size,
            offset=self.offset,
            closed=self.closed,
            chunks=self.chunks,
            message_counts=self.message_counts,
            records=records,
        )

    def validate_magic(self, recording: IO[bytes]) -> None:
        recording.seek(0)
        magic = recording.read(MAGIC_SIZE)
        if magic != MCAP_MAGIC:
            raise ValueError("Invalid MCAP magic.")
        self.offset = MAGIC_SIZE

    def _read_record_bounds(self, recording: IO[bytes]) -> tuple[bytes, int, int, int, int] | None:
        if self.size - self.offset < RECORD_HEADER_SIZE:
            return None

        record_start = self.offset
        recording.seek(record_start)
        header = recording.read(RECORD_HEADER_SIZE)
        if len(header) < RECORD_HEADER_SIZE:
            return None

        payload_length = struct.unpack_from("<Q", header, 1)[0]
        record_span = RECORD_HEADER_SIZE + payload_length
        record_end = record_start + record_span
        if record_end > self.size or record_end <= record_start:
            return None
        opcode = header[0]
        if payload_length == 0 and opcode not in (Opcode.DATA_END, Opcode.FOOTER):
            return None
        return header, record_start, payload_length, record_span, record_end

    def walk_record(self, recording: IO[bytes], chunk_limit: int) -> bool:
        bounds = self._read_record_bounds(recording)
        if bounds is None:
            return False

        header, record_start, payload_length, record_span, record_end = bounds
        opcode = header[0]
        continue_walk = True

        if opcode in (Opcode.DATA_END, Opcode.FOOTER):
            self.offset = record_end
            self.closed = True
            continue_walk = False
        elif opcode in METADATA_OPCODES:
            recording.seek(record_start)
            self.records_bytes.extend(recording.read(record_span))
            self.offset = record_end
        elif opcode == Opcode.CHUNK and len(self.chunks) >= chunk_limit:
            continue_walk = False
        elif opcode == Opcode.CHUNK:
            chunk_entry = _parse_chunk_index_entry(recording, record_start, record_span, payload_length)
            if chunk_entry is None:
                continue_walk = False
            else:
                self.current_chunk = chunk_entry
                self.chunks.append(chunk_entry)
                recording.seek(record_end)
                self.offset = record_end
        elif opcode == Opcode.MESSAGE_INDEX:
            if self.current_chunk is None:
                recording.seek(record_end)
                self.offset = record_end
            elif not _apply_message_index(
                recording, self.current_chunk, record_span, payload_length, self.message_counts
            ):
                continue_walk = False
            else:
                recording.seek(record_end)
                self.offset = record_end
        else:
            recording.seek(record_end)
            self.offset = record_end

        return continue_walk


def walk_mcap_index_sync(mcap_path: Path, from_offset: int, limit: int) -> RecordingIndex:
    walker = McapIndexWalker(mcap_path.stat().st_size, from_offset)
    with mcap_path.open("rb", buffering=8192) as recording:
        if from_offset == 0:
            walker.validate_magic(recording)
        while walker.walk_record(recording, limit):
            continue
    return walker.to_index()


async def walk_mcap_index(mcap_path: Path, from_offset: int, limit: int) -> RecordingIndex:
    async with index_walk_semaphore:
        return await asyncio.to_thread(walk_mcap_index_sync, mcap_path, from_offset, limit)
