import asyncio
import json
import lzma
import zlib
from types import SimpleNamespace
from typing import Any, Dict, Optional, cast
from unittest.mock import patch

from parameter_metadata import (
    MAX_METADATA_FILE_SIZE,
    MavlinkFtpReader,
    MetadataFileReader,
    ParameterMetadataError,
    ParameterMetadataManager,
)


def metadata_crc(content: bytes) -> int:
    return zlib.crc32(content, 0xFFFFFFFF) ^ 0xFFFFFFFF


def test_decode_uri_accepts_mavlink2rest_character_array() -> None:
    uri = list("mftp://@META/general.json") + ["\x00"] * 74
    assert ParameterMetadataManager._decode_uri(uri) == "mftp://@META/general.json"


class FakeMavlinkMessenger:
    def __init__(self) -> None:
        self.advertisement: Optional[Dict[str, Any]] = None

    async def get_mavlink_message(self, message_name: str, vehicle: int, component: int) -> Dict[str, Any]:
        del vehicle, component
        if message_name != "COMPONENT_METADATA" or self.advertisement is None:
            raise RuntimeError("message unavailable")
        return self.advertisement


class FakeFtpMessenger:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.counter = 0
        self.response: Optional[Dict[str, Any]] = None
        self.sessions: list[int] = []
        self.components: list[int] = []

    async def get_mavlink_message(self, message_name: str, vehicle: int, component: int) -> Dict[str, Any]:
        del vehicle, component
        if message_name != "FILE_TRANSFER_PROTOCOL" or self.response is None:
            raise RuntimeError("message unavailable")
        return self.response

    async def send_mavlink_message(self, message: Dict[str, Any]) -> None:
        self.components.append(message["target_component"])
        request = message["payload"]
        request_sequence = int.from_bytes(bytes(request[0:2]), byteorder="little")
        request_session = request[2]
        opcode = request[3]
        self.sessions.append(request_session)

        if opcode == 4:
            response_session = 7
            data = len(self.content).to_bytes(4, byteorder="little")
        elif opcode == 5:
            assert request_session == 7
            offset = int.from_bytes(bytes(request[8:12]), byteorder="little")
            data = self.content[offset : offset + request[4]]
            response_session = request_session
        else:
            assert opcode == 1
            assert request_session == 7
            data = b""
            response_session = request_session

        payload = [0] * 251
        payload[0:2] = ((request_sequence + 1) & 0xFFFF).to_bytes(2, byteorder="little")
        payload[2] = response_session
        payload[3] = 128
        payload[4] = len(data)
        payload[5] = opcode
        payload[12 : 12 + len(data)] = data
        self.counter += 1
        self.response = {
            "status": {"time": {"counter": self.counter}},
            "message": {"payload": payload},
        }


class FakeFtpVehicleManager:
    def __init__(self, content: bytes) -> None:
        self.target_system = 1
        self.target_component = 1
        self.mavlink2rest = FakeFtpMessenger(content)


class FakeVehicleManager:
    def __init__(self) -> None:
        self.target_system = 1
        self.target_component = 1
        self.mavlink2rest = FakeMavlinkMessenger()
        self.request_count = 0
        self.advertisement_on_request: Optional[Dict[str, Any]] = None

    async def request_message(self, message_id: int) -> None:
        assert message_id == 397
        self.request_count += 1
        if self.advertisement_on_request is not None:
            self.mavlink2rest.advertisement = self.advertisement_on_request


class FakeFtpReader:
    def __init__(self, files: Dict[str, bytes]) -> None:
        self.files = files
        self.downloads: list[str] = []

    async def download(self, uri: str) -> bytes:
        self.downloads.append(uri)
        return self.files[uri]


class FailingFileReader(FakeFtpReader):
    def __init__(self, files: Dict[str, bytes]) -> None:
        super().__init__(files)
        self.failures_remaining = 0
        self.attempt_count = 0

    async def download(self, uri: str) -> bytes:
        self.attempt_count += 1
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise ParameterMetadataError("temporary transfer failure")
        return await super().download(uri)


def documents(parameter_names: list[str], version: int = 3) -> tuple[bytes, bytes]:
    parameters = json.dumps(
        {
            "version": version,
            "parameters": [{"name": name, "type": "Int32", "default": 0} for name in parameter_names],
        },
        separators=(",", ":"),
    ).encode()
    general = json.dumps(
        {
            "version": 1,
            "metadataTypes": [
                {
                    "type": 1,
                    "uri": "mftp://@META/parameters.json",
                    "fileCrc": metadata_crc(parameters),
                    "uriFallback": "",
                    "fileCrcFallback": 0,
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    return general, parameters


def advertisement(counter: int, general: bytes) -> Dict[str, Any]:
    uri = list(b"mftp://@META/general.json\x00")
    return {
        "status": {"time": {"counter": counter}},
        "message": {"file_crc": metadata_crc(general), "uri": uri},
    }


def test_initial_hotswap_duplicate_and_invalid_metadata() -> None:
    async def run() -> None:
        vehicle = FakeVehicleManager()
        first_general, first_parameters = documents(["EK3_SRC1_TARGET"])
        files = {
            "mftp://@META/general.json": first_general,
            "mftp://@META/parameters.json": first_parameters,
        }
        ftp = FakeFtpReader(files)
        manager = ParameterMetadataManager(cast(Any, vehicle), cast(Any, ftp))

        await manager.refresh()
        assert vehicle.request_count == 1
        assert manager.__dict__["_snapshot"] is None

        vehicle.mavlink2rest.advertisement = advertisement(1, first_general)
        await manager.refresh()
        first_snapshot = manager.snapshot
        assert first_snapshot is not None
        assert first_snapshot.document["parameters"][0]["name"] == "EK3_SRC1_TARGET"
        assert first_snapshot.etag == f'"{metadata_crc(first_parameters)}"'
        assert ftp.downloads == [
            "mftp://@META/general.json",
            "mftp://@META/parameters.json",
        ]

        vehicle.mavlink2rest.advertisement = advertisement(2, first_general)
        await manager.refresh()
        assert len(ftp.downloads) == 2

        second_general, second_parameters = documents(["EK3_SRC1_TARGET", "EK3_SRC2_TARGET"])
        files["mftp://@META/general.json"] = second_general
        files["mftp://@META/parameters.json"] = second_parameters
        vehicle.mavlink2rest.advertisement = advertisement(3, second_general)
        await manager.refresh()
        assert manager.snapshot is not None
        assert len(manager.snapshot.document["parameters"]) == 2

        stale_snapshot = manager.snapshot
        bad_advertisement = advertisement(4, second_general)
        bad_advertisement["message"]["file_crc"] += 1
        vehicle.mavlink2rest.advertisement = bad_advertisement
        await manager.refresh()
        assert manager.snapshot is stale_snapshot

        manager.reset_for_boot()
        assert manager.__dict__["_snapshot"] is None
        await manager.refresh()
        assert vehicle.request_count == 2

    asyncio.run(run())


def test_passive_refresh_ingests_existing_advertisement_without_requesting() -> None:
    async def run() -> None:
        vehicle = FakeVehicleManager()
        general, parameters = documents(["EK3_SRC1_TARGET"])
        reader = FakeFtpReader(
            {
                "mftp://@META/general.json": general,
                "mftp://@META/parameters.json": parameters,
            }
        )
        vehicle.mavlink2rest.advertisement = advertisement(1, general)
        manager = ParameterMetadataManager(cast(Any, vehicle), cast(Any, reader))

        await manager.refresh(allow_request=False)

        assert vehicle.request_count == 0
        assert manager._request.attempts == 0
        assert manager.snapshot is not None
        assert manager.snapshot.document["parameters"][0]["name"] == "EK3_SRC1_TARGET"

    asyncio.run(run())


def test_explicit_refresh_requests_current_metadata_from_vehicle() -> None:
    async def run() -> None:
        vehicle = FakeVehicleManager()
        first_general, first_parameters = documents(["EK3_SRC1_TARGET"])
        files = {
            "mftp://@META/general.json": first_general,
            "mftp://@META/parameters.json": first_parameters,
        }
        reader = FakeFtpReader(files)
        manager = ParameterMetadataManager(cast(Any, vehicle), cast(Any, reader))

        vehicle.mavlink2rest.advertisement = advertisement(1, first_general)
        await manager.refresh(allow_request=False)
        assert manager.snapshot is not None
        assert len(manager.snapshot.document["parameters"]) == 1

        second_general, second_parameters = documents(["EK3_SRC1_TARGET", "EK3_SRC2_TARGET"])
        files["mftp://@META/general.json"] = second_general
        files["mftp://@META/parameters.json"] = second_parameters
        vehicle.advertisement_on_request = advertisement(2, second_general)

        await manager.refresh_from_vehicle()

        assert vehicle.request_count == 1
        assert manager.snapshot is not None
        assert len(manager.snapshot.document["parameters"]) == 2

    asyncio.run(run())


def test_metadata_validation_and_mavftp_uri_boundaries() -> None:
    valid = b'{"version":3,"parameters":[]}'
    assert metadata_crc(b"123456789") == 0x2DFD2D88
    ParameterMetadataManager._validate_crc(valid, metadata_crc(valid))
    assert MavlinkFtpReader._path_from_uri("mftp://@META/parameters.json") == (
        "@META/parameters.json",
        None,
    )
    assert MavlinkFtpReader._path_from_uri("mftp:///absolute/parameters.json") == (
        "/absolute/parameters.json",
        None,
    )
    assert MavlinkFtpReader._path_from_uri("mftp://comp=42:@META/parameters.json") == (
        "@META/parameters.json",
        42,
    )

    for uri in (
        "https://example.com/parameters.json",
        "mftp://@META/../parameters.json",
    ):
        try:
            MavlinkFtpReader._path_from_uri(uri)
        except ParameterMetadataError:
            continue
        raise AssertionError(f"invalid URI was accepted: {uri}")

    try:
        ParameterMetadataManager._validate_crc(valid, 0)
    except ParameterMetadataError:
        pass
    else:
        raise AssertionError("invalid CRC was accepted")


def test_mavftp_download_uses_server_assigned_session() -> None:
    async def run() -> None:
        content = bytes(index % 251 for index in range(500))
        vehicle = FakeFtpVehicleManager(content)
        reader = MavlinkFtpReader(cast(Any, vehicle))
        assert await reader.download("mftp://comp=7:@META/parameters.json") == content
        assert vehicle.mavlink2rest.sessions[0] == 0
        assert all(session == 7 for session in vehicle.mavlink2rest.sessions[1:])
        assert all(component == 7 for component in vehicle.mavlink2rest.components)

    asyncio.run(run())


def test_failed_hotswap_retries_same_advertisement_and_keeps_stale_snapshot() -> None:
    async def run() -> None:
        vehicle = FakeVehicleManager()
        first_general, first_parameters = documents(["EK3_SRC1_TARGET"])
        files = {
            "mftp://@META/general.json": first_general,
            "mftp://@META/parameters.json": first_parameters,
        }
        reader = FailingFileReader(files)
        manager = ParameterMetadataManager(cast(Any, vehicle), cast(Any, reader))
        await manager.refresh()
        vehicle.mavlink2rest.advertisement = advertisement(1, first_general)
        await manager.refresh()
        original = manager.snapshot
        assert original is not None

        second_general, second_parameters = documents(["EK3_SRC1_TARGET", "EK3_SRC2_TARGET"])
        files["mftp://@META/general.json"] = second_general
        files["mftp://@META/parameters.json"] = second_parameters
        reader.failures_remaining = 2
        vehicle.mavlink2rest.advertisement = advertisement(2, second_general)
        await manager.refresh()
        assert manager.snapshot is original

        manager._advertisement.retry_at = 0
        await manager.refresh()
        assert manager.snapshot is original

        manager._advertisement.retry_at = 0
        await manager.refresh()
        assert manager.snapshot is not None
        assert len(manager.snapshot.document["parameters"]) == 2
        assert manager._advertisement.failed_attempts == 0

        accepted_snapshot = manager.snapshot
        third_general, third_parameters = documents(["EK3_SRC1_TARGET", "EK3_SRC2_TARGET", "EK3_SRC3_TARGET"])
        files["mftp://@META/general.json"] = third_general
        files["mftp://@META/parameters.json"] = third_parameters
        reader.failures_remaining = 4
        attempts_before = reader.attempt_count
        vehicle.mavlink2rest.advertisement = advertisement(3, third_general)
        for _ in range(4):
            manager._advertisement.retry_at = 0
            await manager.refresh()
        assert reader.attempt_count - attempts_before == 3
        assert manager.snapshot is accepted_snapshot

        reader.failures_remaining = 0
        vehicle.mavlink2rest.advertisement = advertisement(4, third_general)
        await manager.refresh()
        assert manager.snapshot is not None
        assert len(manager.snapshot.document["parameters"]) == 3
        assert manager._advertisement.failed_attempts == 0

    asyncio.run(run())


def test_xz_crc_is_checked_before_decompression_and_version_four_is_accepted() -> None:
    async def run() -> None:
        vehicle = FakeVehicleManager()
        general, parameters = documents(["EK3_SRC1_TARGET"], version=4)
        compressed_parameters = lzma.compress(parameters, format=lzma.FORMAT_XZ)
        general_document = json.loads(general)
        general_document["metadataTypes"][0]["uri"] = "https://metadata.example/parameters.json.xz"
        general_document["metadataTypes"][0]["fileCrc"] = metadata_crc(compressed_parameters)
        compressed_general = lzma.compress(
            json.dumps(general_document, separators=(",", ":")).encode(),
            format=lzma.FORMAT_XZ,
        )
        files = {
            "mftp://@META/general.json.xz": compressed_general,
            "https://metadata.example/parameters.json.xz": compressed_parameters,
        }
        reader = FakeFtpReader(files)
        manager = ParameterMetadataManager(cast(Any, vehicle), cast(Any, reader))
        await manager.refresh()
        uri = list(b"mftp://@META/general.json.xz\x00")
        vehicle.mavlink2rest.advertisement = {
            "status": {"time": {"counter": 1}},
            "message": {"file_crc": metadata_crc(compressed_general), "uri": uri},
        }
        await manager.refresh()
        assert manager.snapshot is not None
        assert manager.snapshot.document["version"] == 4
        assert manager.snapshot.file_crc == metadata_crc(compressed_parameters)

    asyncio.run(run())


class FakeHttpContent:
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def iter_chunked(self, size: int) -> Any:
        for offset in range(0, len(self._content), size):
            yield self._content[offset : offset + size]


class FakeHttpResponse:
    def __init__(self, content: bytes) -> None:
        self.url = SimpleNamespace(scheme="https")
        self.headers = {"Content-Length": str(len(content))}
        self.content = FakeHttpContent(content)

    async def __aenter__(self) -> "FakeHttpResponse":
        return self

    async def __aexit__(self, *args: Any) -> None:
        del args

    def raise_for_status(self) -> None:
        return None


class FakeHttpSession:
    def __init__(self, content: bytes) -> None:
        self._response = FakeHttpResponse(content)

    async def __aenter__(self) -> "FakeHttpSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        del args

    def get(self, uri: str, allow_redirects: bool) -> FakeHttpResponse:
        assert uri.startswith("https://")
        assert allow_redirects
        return self._response


def test_https_download_is_bounded_without_new_dependencies() -> None:
    async def run() -> None:
        content = b'{"version":4,"parameters":[]}'
        with patch(
            "parameter_metadata.aiohttp.ClientSession",
            return_value=FakeHttpSession(content),
        ):
            assert await MetadataFileReader._download_https("https://metadata.example/parameters.json") == content

        oversized = lzma.compress(b"x" * (MAX_METADATA_FILE_SIZE + 1))
        try:
            ParameterMetadataManager._decompress_if_needed("metadata.json.xz", oversized)
        except ParameterMetadataError:
            pass
        else:
            raise AssertionError("oversized decompressed metadata was accepted")

    asyncio.run(run())
