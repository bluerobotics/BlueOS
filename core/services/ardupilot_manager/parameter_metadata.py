import asyncio
import json
import lzma
import time
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp
from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from loguru import logger

COMPONENT_METADATA_MESSAGE_ID = 397
PARAMETER_METADATA_TYPE = 1
MAVFTP_ACK = 128
MAVFTP_NACK = 129
MAVFTP_OPEN_FILE_READ_ONLY = 4
MAVFTP_READ_FILE = 5
MAVFTP_TERMINATE_SESSION = 1
MAVFTP_PAYLOAD_SIZE = 251
MAVFTP_DATA_SIZE = 239
MAX_METADATA_FILE_SIZE = 2 * 1024 * 1024


class ParameterMetadataError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParameterMetadataSnapshot:
    document: Dict[str, Any]
    file_crc: int

    @property
    def etag(self) -> str:
        return f'"{self.file_crc}"'


@dataclass
class AdvertisementState:
    counter: int = -1
    key: Optional[tuple[int, str]] = None
    baseline_initialized: bool = False
    failed_key: Optional[tuple[int, str]] = None
    failed_attempts: int = 0
    retry_at: float = 0.0


@dataclass
class RequestState:
    attempts: int = 0
    next_at: float = 0.0


@dataclass(frozen=True)
class MavlinkFtpReply:
    session: int
    data: bytes


class MavlinkFtpReader:
    def __init__(self, vehicle_manager: VehicleManager) -> None:
        self._vehicle_manager = vehicle_manager
        self._lock = asyncio.Lock()
        self._sequence = 0
        self._target_component = vehicle_manager.target_component

    async def download(self, uri: str) -> bytes:
        path, target_component = self._path_from_uri(uri)
        async with self._lock:
            self._target_component = target_component or self._vehicle_manager.target_component
            try:
                return await asyncio.wait_for(self._download(path), timeout=45.0)
            finally:
                self._target_component = self._vehicle_manager.target_component

    async def _download(self, path: str) -> bytes:
        session = 0
        opened = False
        try:
            open_reply = await self._request(session, MAVFTP_OPEN_FILE_READ_ONLY, 0, path.encode("utf-8"))
            opened = True
            session = open_reply.session
            if len(open_reply.data) < 4:
                raise ParameterMetadataError("MAVFTP open response did not include a file size")
            file_size = int.from_bytes(open_reply.data[:4], byteorder="little")
            if file_size > MAX_METADATA_FILE_SIZE:
                raise ParameterMetadataError(f"metadata file is too large: {file_size} bytes")

            content = bytearray()
            while len(content) < file_size:
                read_size = min(MAVFTP_DATA_SIZE, file_size - len(content))
                read_reply = await self._request(session, MAVFTP_READ_FILE, len(content), read_size)
                if read_reply.session != session:
                    raise ParameterMetadataError("MAVFTP session changed during download")
                if not read_reply.data or len(read_reply.data) > read_size:
                    raise ParameterMetadataError("MAVFTP returned an invalid read size")
                content.extend(read_reply.data)
            if len(content) != file_size:
                raise ParameterMetadataError("MAVFTP returned an unexpected file size")
            return bytes(content)
        finally:
            if opened:
                try:
                    await self._request(session, MAVFTP_TERMINATE_SESSION, 0)
                except Exception as error:  # A failed close must not replace the download result.
                    logger.warning(f"Failed to close MAVFTP metadata session: {error}")

    async def _request(
        self,
        session: int,
        opcode: int,
        offset: int,
        data_or_size: bytes | int = b"",
    ) -> MavlinkFtpReply:
        data = data_or_size if isinstance(data_or_size, bytes) else b""
        size = len(data) if isinstance(data_or_size, bytes) else data_or_size
        if len(data) > MAVFTP_DATA_SIZE:
            raise ParameterMetadataError("MAVFTP request data is too large")
        payload = [0] * MAVFTP_PAYLOAD_SIZE
        payload[0:2] = self._sequence.to_bytes(2, byteorder="little")
        payload[2] = session
        payload[3] = opcode
        payload[4] = size
        payload[8:12] = offset.to_bytes(4, byteorder="little")
        payload[12 : 12 + len(data)] = data

        baseline_counter = await self._reply_counter()
        message = {
            "type": "FILE_TRANSFER_PROTOCOL",
            "target_network": 0,
            "target_system": self._vehicle_manager.target_system,
            "target_component": self._target_component,
            "payload": payload,
        }
        for attempt in range(3):
            await self._vehicle_manager.mavlink2rest.send_mavlink_message(message)
            try:
                return await self._wait_for_reply(baseline_counter, opcode)
            except asyncio.TimeoutError:
                if attempt == 2:
                    raise ParameterMetadataError("MAVFTP request timed out") from None
        raise ParameterMetadataError("MAVFTP request failed")

    async def _reply_counter(self) -> int:
        try:
            response = await self._vehicle_manager.mavlink2rest.get_mavlink_message(
                "FILE_TRANSFER_PROTOCOL",
                self._vehicle_manager.target_system,
                self._target_component,
            )
            return int(response["status"]["time"]["counter"])
        except Exception:
            return -1

    async def _wait_for_reply(self, baseline_counter: int, request_opcode: int) -> MavlinkFtpReply:
        deadline = time.monotonic() + 0.75
        expected_sequence = (self._sequence + 1) & 0xFFFF
        while time.monotonic() < deadline:
            try:
                response = await self._vehicle_manager.mavlink2rest.get_mavlink_message(
                    "FILE_TRANSFER_PROTOCOL",
                    self._vehicle_manager.target_system,
                    self._target_component,
                )
                counter = int(response["status"]["time"]["counter"])
                payload = response["message"]["payload"]
                reply_sequence = int.from_bytes(bytes(payload[0:2]), byteorder="little")
                if counter != baseline_counter and reply_sequence == expected_sequence and payload[5] == request_opcode:
                    self._sequence = reply_sequence
                    if payload[3] == MAVFTP_NACK:
                        error = payload[12] if payload[4] else "unknown"
                        raise ParameterMetadataError(f"MAVFTP request was rejected: {error}")
                    if payload[3] != MAVFTP_ACK:
                        raise ParameterMetadataError(f"unexpected MAVFTP opcode: {payload[3]}")
                    return MavlinkFtpReply(session=payload[2], data=bytes(payload[12 : 12 + payload[4]]))
            except ParameterMetadataError:
                raise
            except Exception:
                pass
            await asyncio.sleep(0.02)
        raise asyncio.TimeoutError

    @staticmethod
    def _path_from_uri(uri: str) -> tuple[str, Optional[int]]:
        if not uri.startswith("mftp://") or "?" in uri or "#" in uri:
            raise ParameterMetadataError(f"unsupported metadata URI: {uri}")
        path = uri.removeprefix("mftp://")
        target_component = None
        if path.startswith("comp="):
            selector, separator, path = path.partition(":")
            component_text = selector.removeprefix("comp=")
            if not separator or not component_text.isdigit():
                raise ParameterMetadataError(f"invalid MAVFTP component selector: {uri}")
            target_component = int(component_text)
            if not 1 <= target_component <= 255:
                raise ParameterMetadataError(f"invalid MAVFTP component selector: {uri}")

        relative_parts = path.removeprefix("/").split("/")
        if (
            not path
            or any(part in ("", ".", "..") for part in relative_parts)
            or len(path.encode("utf-8")) > MAVFTP_DATA_SIZE
        ):
            raise ParameterMetadataError(f"invalid MAVFTP metadata path: {path}")
        return path, target_component


class MetadataFileReader:
    def __init__(self, vehicle_manager: VehicleManager) -> None:
        self._mavftp = MavlinkFtpReader(vehicle_manager)

    async def download(self, uri: str) -> bytes:
        if uri.startswith("mftp://"):
            return await self._mavftp.download(uri)
        if uri.startswith("https://"):
            return await self._download_https(uri)
        raise ParameterMetadataError(f"unsupported metadata URI: {uri}")

    @staticmethod
    async def _download_https(uri: str) -> bytes:
        timeout = aiohttp.ClientTimeout(total=15.0, connect=3.0, sock_read=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(uri, allow_redirects=True) as response:
                response.raise_for_status()
                if response.url.scheme != "https":
                    raise ParameterMetadataError("metadata HTTPS redirect changed scheme")
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) > MAX_METADATA_FILE_SIZE:
                    raise ParameterMetadataError("metadata HTTPS file is too large")
                content = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    content.extend(chunk)
                    if len(content) > MAX_METADATA_FILE_SIZE:
                        raise ParameterMetadataError("metadata HTTPS file is too large")
                return bytes(content)


class ParameterMetadataManager:
    def __init__(
        self,
        vehicle_manager: VehicleManager,
        file_reader: Optional[MetadataFileReader] = None,
    ) -> None:
        self._vehicle_manager = vehicle_manager
        self._file_reader = file_reader or MetadataFileReader(vehicle_manager)
        self._refresh_lock = asyncio.Lock()
        self._advertisement = AdvertisementState()
        self._request = RequestState()
        self._snapshot: Optional[ParameterMetadataSnapshot] = None
        self._generation = 0

    @property
    def snapshot(self) -> Optional[ParameterMetadataSnapshot]:
        return self._snapshot

    def reset_for_boot(self) -> None:
        self._generation += 1
        self._advertisement = AdvertisementState()
        self._request = RequestState()
        self._snapshot = None

    async def refresh_from_vehicle(self) -> None:
        async with self._refresh_lock:
            baseline = await self._latest_advertisement()
            baseline_counter = baseline[0] if baseline is not None else -1
            await self._vehicle_manager.request_message(COMPONENT_METADATA_MESSAGE_ID)

            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                advertisement = await self._latest_advertisement()
                if advertisement is not None and advertisement[0] != baseline_counter:
                    self._advertisement.counter = advertisement[0]
                    self._advertisement.baseline_initialized = True
                    await self._update_from_advertisement(advertisement[1], time.monotonic())
                    return
                await asyncio.sleep(0.02)

    async def refresh(self, allow_request: bool = True) -> None:
        if self._refresh_lock.locked():
            return
        async with self._refresh_lock:
            baseline = await self._latest_advertisement()
            if not self._advertisement.baseline_initialized:
                self._advertisement.counter = baseline[0] if allow_request and baseline is not None else -1
                self._advertisement.baseline_initialized = True

            now = time.monotonic()
            if self._request.attempts < 3 and now >= self._request.next_at and self._snapshot is None and allow_request:
                try:
                    await self._vehicle_manager.request_message(COMPONENT_METADATA_MESSAGE_ID)
                    self._request.attempts += 1
                    self._request.next_at = now + 2.0
                except Exception as error:
                    self._request.attempts += 1
                    self._request.next_at = now + 2.0
                    logger.warning(f"Failed to request parameter metadata advertisement: {error}")
                    return

            advertisement = await self._latest_advertisement()
            if advertisement is None:
                return
            if advertisement[0] == self._advertisement.counter and self._advertisement.failed_key is None:
                return
            if advertisement[0] != self._advertisement.counter and self._advertisement.failed_key is not None:
                self._advertisement.failed_key = None
                self._advertisement.failed_attempts = 0
                self._advertisement.retry_at = 0.0
            self._advertisement.counter = advertisement[0]
            await self._update_from_advertisement(advertisement[1], now)

    async def _update_from_advertisement(self, advertisement: Dict[str, Any], now: float) -> None:
        try:
            advertisement_key = (
                self._require_crc(advertisement.get("file_crc")),
                self._decode_uri(advertisement.get("uri")),
            )
        except ParameterMetadataError as error:
            logger.warning(f"Failed to update parameter metadata: {error}")
            return
        if advertisement_key == self._advertisement.key:
            return
        if advertisement_key != self._advertisement.failed_key:
            self._advertisement.failed_key = None
            self._advertisement.failed_attempts = 0
            self._advertisement.retry_at = 0.0
        elif self._advertisement.failed_attempts >= 3 or now < self._advertisement.retry_at:
            return
        generation = self._generation
        try:
            snapshot = await self._load_snapshot(advertisement)
        except Exception as error:
            self._advertisement.failed_key = advertisement_key
            self._advertisement.failed_attempts += 1
            self._advertisement.retry_at = now + 2 ** (self._advertisement.failed_attempts - 1)
            logger.warning(f"Failed to update parameter metadata: {error}")
            return
        if generation == self._generation:
            self._snapshot = snapshot
            self._advertisement.key = advertisement_key
            self._advertisement.failed_key = None
            self._advertisement.failed_attempts = 0
            self._advertisement.retry_at = 0.0

    async def _latest_advertisement(self) -> Optional[tuple[int, Dict[str, Any]]]:
        try:
            response = await self._vehicle_manager.mavlink2rest.get_mavlink_message(
                "COMPONENT_METADATA",
                self._vehicle_manager.target_system,
                self._vehicle_manager.target_component,
            )
            return int(response["status"]["time"]["counter"]), response["message"]
        except Exception:
            return None

    async def _load_snapshot(self, advertisement: Dict[str, Any]) -> ParameterMetadataSnapshot:
        general_crc = self._require_crc(advertisement.get("file_crc"))
        general_uri = self._decode_uri(advertisement.get("uri"))
        if not general_uri.startswith("mftp://"):
            raise ParameterMetadataError("general metadata must use MAVFTP")
        general_file = await self._file_reader.download(general_uri)
        self._validate_crc(general_file, general_crc)
        general = self._decode_document(self._decompress_if_needed(general_uri, general_file))

        metadata_types = general.get("metadataTypes")
        general_version = general.get("version")
        if not isinstance(general_version, int) or general_version < 1:
            raise ParameterMetadataError("general metadata version must be at least 1")
        if not isinstance(metadata_types, list):
            raise ParameterMetadataError("general metadata has no metadataTypes list")
        parameter_metadata = next(
            (
                metadata
                for metadata in metadata_types
                if isinstance(metadata, dict) and metadata.get("type") == PARAMETER_METADATA_TYPE
            ),
            None,
        )
        if parameter_metadata is None:
            raise ParameterMetadataError("general metadata has no parameter metadata entry")

        parameter_crc = self._require_crc(parameter_metadata.get("fileCrc"))
        parameter_uri = parameter_metadata.get("uri")
        if not isinstance(parameter_uri, str):
            raise ParameterMetadataError("parameter metadata URI is invalid")
        parameter_file = await self._file_reader.download(parameter_uri)
        self._validate_crc(parameter_file, parameter_crc)
        document = self._decode_document(self._decompress_if_needed(parameter_uri, parameter_file))
        self._validate_parameter_document(document)
        return ParameterMetadataSnapshot(document=document, file_crc=parameter_crc)

    @staticmethod
    def _decode_uri(value: Any) -> str:
        if isinstance(value, str):
            return value.rstrip("\x00")
        if not isinstance(value, list) or not all(isinstance(item, int) and 0 <= item <= 255 for item in value):
            raise ParameterMetadataError("component metadata URI is invalid")
        try:
            return bytes(value).split(b"\x00", maxsplit=1)[0].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ParameterMetadataError("component metadata URI is not UTF-8") from error

    @staticmethod
    def _decode_document(content: bytes) -> Dict[str, Any]:
        try:
            document = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ParameterMetadataError("metadata file is not valid JSON") from error
        if not isinstance(document, dict):
            raise ParameterMetadataError("metadata document must be an object")
        return document

    @staticmethod
    def _decompress_if_needed(uri: str, content: bytes) -> bytes:
        if not uri.split("?", maxsplit=1)[0].lower().endswith(".xz"):
            return content
        decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=32 * 1024 * 1024)
        output = bytearray()
        pending = content
        try:
            while True:
                size_before = len(output)
                remaining = MAX_METADATA_FILE_SIZE + 1 - size_before
                output.extend(decompressor.decompress(pending, max_length=remaining))
                pending = b""
                if len(output) > MAX_METADATA_FILE_SIZE:
                    raise ParameterMetadataError("decompressed metadata file is too large")
                if bool(getattr(decompressor, "eof")):
                    if getattr(decompressor, "unused_data"):
                        raise ParameterMetadataError("metadata XZ file has trailing data")
                    return bytes(output)
                if bool(getattr(decompressor, "needs_input")):
                    raise ParameterMetadataError("metadata XZ file is truncated")
                if len(output) == size_before:
                    raise ParameterMetadataError("metadata XZ file is invalid")
        except lzma.LZMAError as error:
            raise ParameterMetadataError("metadata XZ file is invalid") from error

    @staticmethod
    def _require_crc(value: Any) -> int:
        if not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
            raise ParameterMetadataError("metadata CRC is invalid")
        return value

    @staticmethod
    def _validate_crc(content: bytes, expected: int) -> None:
        actual = zlib.crc32(content, 0xFFFFFFFF) ^ 0xFFFFFFFF
        if actual != expected:
            raise ParameterMetadataError(f"metadata CRC mismatch: expected {expected}, got {actual}")

    @staticmethod
    def _validate_parameter_document(document: Dict[str, Any]) -> None:
        version = document.get("version")
        if not isinstance(version, int) or version < 3 or not isinstance(document.get("parameters"), list):
            raise ParameterMetadataError("parameter metadata version must be at least 3")
        names = set()
        for parameter in document["parameters"]:
            if not isinstance(parameter, dict) or not isinstance(parameter.get("name"), str):
                raise ParameterMetadataError("parameter metadata contains an invalid entry")
            name = parameter["name"]
            if not name or name in names:
                raise ParameterMetadataError(f"parameter metadata contains an invalid name: {name}")
            names.add(name)
