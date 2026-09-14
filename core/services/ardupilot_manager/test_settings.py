import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from commonwealth.settings.manager import PydanticManager

_SERVICE_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _SERVICE_DIR)
for _name in ("settings", "config", "typedefs", "exceptions"):
    _mod = sys.modules.get(_name)
    if _mod is not None and not str(getattr(_mod, "__file__", "")).startswith(_SERVICE_DIR):
        del sys.modules[_name]

from autopilot_manager import AutoPilotManager
from config import SERVICE_NAME
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from settings import SettingsV1, migrate_from_old_settings
from typedefs import FlightController, Platform, Serial, SITLFrame

VALID_SERIAL_ENDPOINT = "udp:192.168.2.1:14550"


def _endpoint(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "GCS Client Link",
        "owner": SERVICE_NAME,
        "connection_type": EndpointType.UDPClient.value,
        "place": "192.168.2.1",
        "argument": 14550,
        "persistent": True,
        "protected": False,
        "enabled": True,
        "overwrite_settings": False,
    }
    data.update(overrides)
    return data


def _old_settings_payload() -> dict[str, Any]:
    return {
        "version": 0,
        "content": {
            "serials": [{"port": "B", "endpoint": VALID_SERIAL_ENDPOINT}],
            "start_on_boot": False,
            "preferred_router": "MAVLinkRouter",
            "sitl_frame": SITLFrame.VECTORED.value,
            "preferred_board": {
                "name": "Navigator",
                "manufacturer": "Blue Robotics",
                "platform": Platform.Navigator.value,
                "path": None,
                "flags": [],
            },
            "endpoints": [_endpoint()],
            "manual_board_master_endpoint": _endpoint(
                name="Manual Board Master Endpoint",
                connection_type=EndpointType.UDPServer.value,
                place="0.0.0.0",
                argument=14551,
            ),
        },
    }


def _write_old_settings(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _settings_with_tmp_paths(tmp_path: Path, **overrides: Any) -> SettingsV1:
    values: dict[str, Any] = {
        "firmware_folder": tmp_path / "firmware",
        "log_path": tmp_path / "logs",
        "user_firmware_folder": tmp_path / "user_firmware",
    }
    values.update(overrides)
    return SettingsV1(**values)


def test_migrate_from_old_settings_copies_supported_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("settings.appdirs.user_config_dir", lambda _name: str(tmp_path))
    _write_old_settings(tmp_path / "settings.json", _old_settings_payload())

    target = _settings_with_tmp_paths(tmp_path)
    migrate_from_old_settings(target)

    assert target.start_on_boot is False
    assert target.preferred_router == "MAVLinkRouter"
    assert target.sitl_frame == SITLFrame.VECTORED
    assert target.preferred_board is not None
    assert target.preferred_board.name == "Navigator"
    assert target.preferred_board.platform == Platform.Navigator
    assert target.serials == [Serial(port="B", endpoint=VALID_SERIAL_ENDPOINT)]
    assert target.endpoints == {
        Endpoint.model_validate(_endpoint()),
    }
    assert target.manual_board_master_endpoint == Endpoint.model_validate(
        _endpoint(
            name="Manual Board Master Endpoint",
            connection_type=EndpointType.UDPServer.value,
            place="0.0.0.0",
            argument=14551,
        )
    )


def _assert_unmigrated_defaults(target: SettingsV1) -> None:
    assert not target.serials
    assert target.sitl_frame == SITLFrame.UNDEFINED
    assert target.start_on_boot is True
    assert target.preferred_router is None
    assert target.preferred_board is None
    assert target.endpoints == set()
    assert target.manual_board_master_endpoint is None


def test_migrate_from_old_settings_skips_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("settings.appdirs.user_config_dir", lambda _name: str(tmp_path))
    target = _settings_with_tmp_paths(tmp_path)
    migrate_from_old_settings(target)
    _assert_unmigrated_defaults(target)


def test_migrate_from_old_settings_ignores_invalid_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("settings.appdirs.user_config_dir", lambda _name: str(tmp_path))
    payload = _old_settings_payload()
    payload["content"]["serials"] = [
        {"port": "B", "endpoint": VALID_SERIAL_ENDPOINT},
        {"port": "A", "endpoint": VALID_SERIAL_ENDPOINT},
        {"not": "a serial"},
    ]
    payload["content"]["sitl_frame"] = "not-a-frame"
    payload["content"]["preferred_board"] = {"name": "broken"}
    payload["content"]["endpoints"] = [_endpoint(), "not an endpoint", {"name": "x"}]
    payload["content"]["manual_board_master_endpoint"] = {"name": "x"}
    _write_old_settings(tmp_path / "settings.json", payload)

    target = _settings_with_tmp_paths(tmp_path, sitl_frame=SITLFrame.UNDEFINED, preferred_board=None)
    migrate_from_old_settings(target)

    assert target.serials == [Serial(port="B", endpoint=VALID_SERIAL_ENDPOINT)]
    assert target.sitl_frame == SITLFrame.UNDEFINED
    assert target.preferred_board is None
    assert target.endpoints == {Endpoint.model_validate(_endpoint())}
    assert target.manual_board_master_endpoint is None


def test_migrate_from_old_settings_handles_corrupt_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("settings.appdirs.user_config_dir", lambda _name: str(tmp_path))
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")
    target = _settings_with_tmp_paths(tmp_path)
    migrate_from_old_settings(target)
    _assert_unmigrated_defaults(target)


def test_migrate_from_old_settings_requires_content_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("settings.appdirs.user_config_dir", lambda _name: str(tmp_path))
    _write_old_settings(tmp_path / "settings.json", {"version": 0, "content": []})
    target = _settings_with_tmp_paths(tmp_path)
    migrate_from_old_settings(target)
    _assert_unmigrated_defaults(target)


def test_keep_valid_serials_drops_invalid_entries() -> None:
    settings = SettingsV1(
        serials=[
            {"port": "B", "endpoint": VALID_SERIAL_ENDPOINT},
            {"port": "A", "endpoint": VALID_SERIAL_ENDPOINT},
            {"port": "C"},
        ]
    )
    assert settings.serials == [Serial(port="B", endpoint=VALID_SERIAL_ENDPOINT)]


def test_keep_valid_serials_accepts_empty_values() -> None:
    assert not SettingsV1(serials=None).serials
    assert not SettingsV1(serials=[]).serials
    assert not SettingsV1(serials="nope").serials


def test_migrate_is_noop_for_current_version() -> None:
    settings = SettingsV1()
    data = {"VERSION": SettingsV1.STATIC_VERSION, "start_on_boot": False}
    settings.migrate(data)
    assert data["VERSION"] == SettingsV1.STATIC_VERSION
    assert data["start_on_boot"] is False


def test_create_app_folders_creates_directories_and_replaces_files(tmp_path: Path) -> None:
    firmware = tmp_path / "firmware"
    logs = tmp_path / "logs"
    user_firmware = tmp_path / "user_firmware"
    firmware.write_text("not a directory", encoding="utf-8")

    settings = _settings_with_tmp_paths(
        tmp_path, firmware_folder=firmware, log_path=logs, user_firmware_folder=user_firmware
    )
    settings.create_app_folders()

    assert firmware.is_dir()
    assert logs.is_dir()
    assert user_firmware.is_dir()


def test_pydantic_manager_migrates_old_settings_on_first_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_config = tmp_path / "legacy"
    new_config = tmp_path / "pydantic"
    monkeypatch.setattr("settings.appdirs.user_config_dir", lambda _name: str(old_config))
    _write_old_settings(old_config / "settings.json", _old_settings_payload())

    manager: PydanticManager[SettingsV1] = PydanticManager(SERVICE_NAME, SettingsV1, new_config)
    settings = manager.settings

    assert settings.start_on_boot is False
    assert settings.preferred_router == "MAVLinkRouter"
    assert settings.sitl_frame == SITLFrame.VECTORED
    assert settings.serials == [Serial(port="B", endpoint=VALID_SERIAL_ENDPOINT)]
    assert (new_config / SERVICE_NAME / "settings-1.json").is_file()


def test_pydantic_manager_roundtrip_preserves_typed_fields(tmp_path: Path) -> None:
    manager: PydanticManager[SettingsV1] = PydanticManager(SERVICE_NAME, SettingsV1, tmp_path)
    endpoint = Endpoint.model_validate(_endpoint())
    board = FlightController(name="Navigator", platform=Platform.Navigator)
    manager.settings.start_on_boot = False
    manager.settings.preferred_router = "MAVP2P"
    manager.settings.sitl_frame = SITLFrame.VECTORED
    manager.settings.serials = [Serial(port="C", endpoint=VALID_SERIAL_ENDPOINT)]
    manager.settings.preferred_board = board
    manager.settings.endpoints = {endpoint}
    manager.settings.manual_board_master_endpoint = endpoint
    manager.save()

    reloaded: PydanticManager[SettingsV1] = PydanticManager(SERVICE_NAME, SettingsV1, tmp_path)
    assert reloaded.settings.start_on_boot is False
    assert reloaded.settings.preferred_router == "MAVP2P"
    assert reloaded.settings.sitl_frame == SITLFrame.VECTORED
    assert reloaded.settings.serials == [Serial(port="C", endpoint=VALID_SERIAL_ENDPOINT)]
    assert reloaded.settings.preferred_board == board
    assert reloaded.settings.endpoints == {endpoint}
    assert reloaded.settings.manual_board_master_endpoint == endpoint


class _FakeSettingsManager:
    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.save_calls = 0

    def save(self) -> None:
        self.save_calls += 1


def _manager_with_settings(settings: Any) -> AutoPilotManager:
    manager = AutoPilotManager.__new__(AutoPilotManager)
    manager._settings_manager = cast(PydanticManager[SettingsV1], _FakeSettingsManager(settings))
    return manager


def test_get_serials_prefers_saved_then_linux_board_defaults() -> None:
    settings = SettingsV1(serials=[Serial(port="B", endpoint=VALID_SERIAL_ENDPOINT)])
    manager = _manager_with_settings(settings)
    manager._current_board = None
    assert manager.get_serials() == [Serial(port="B", endpoint=VALID_SERIAL_ENDPOINT)]

    settings.serials = []
    manager._current_board = FlightController(name="Pixhawk1", platform=Platform.Pixhawk1)
    assert not manager.get_serials()

    linux_board = MagicMock(spec=LinuxFlightController)
    linux_board.get_serials.return_value = [Serial(port="C", endpoint=VALID_SERIAL_ENDPOINT)]
    manager._current_board = linux_board
    assert manager.get_serials() == [Serial(port="C", endpoint=VALID_SERIAL_ENDPOINT)]


def test_configuration_endpoints_roundtrip_and_skip_invalid() -> None:
    endpoint = Endpoint.model_validate(_endpoint())
    settings = SettingsV1(endpoints={endpoint})
    manager = _manager_with_settings(settings)
    assert manager._get_configuration_endpoints() == {endpoint}

    manager._save_endpoints_to_configuration({endpoint})
    fake_manager = cast(_FakeSettingsManager, manager._settings_manager)
    assert fake_manager.save_calls == 1
    assert settings.endpoints == {endpoint}

    manager = _manager_with_settings(SimpleNamespace(endpoints=[_endpoint(), "not an endpoint"]))
    assert manager._get_configuration_endpoints() == {endpoint}
