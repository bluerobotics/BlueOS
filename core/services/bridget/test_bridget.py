import json
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from fastapi import HTTPException
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
_saved = sys.modules.pop("settings", None)

import bridget
import settings
from bridget import BridgeFrontendSpec, Bridget

if _saved is not None:
    sys.modules["settings"] = _saved
else:
    sys.modules.pop("settings", None)

SERVER = BridgeFrontendSpec(
    serial_path="/dev/ttyUSB0", baud=115200, ip="0.0.0.0", udp_target_port=0, udp_listen_port=15000
)
CLIENT = BridgeFrontendSpec(
    serial_path="/dev/ttyUSB1", baud=57600, ip="192.168.2.1", udp_target_port=14550, udp_listen_port=0
)
V1_SETTINGS = {
    "VERSION": 1,
    "specs": [
        {"serial_path": "/dev/ttyUSB0", "baudrate": 115200, "ip": "0.0.0.0", "udp_port": 15000},
        {"serial_path": "/dev/ttyUSB1", "baudrate": 57600, "ip": "192.168.2.1", "udp_port": 14550},
    ],
}


@pytest.fixture(name="bridge_cls")
def fixture_bridge_cls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(settings, "OLD_SETTINGS_DIR", tmp_path / "old")
    bridge_cls = MagicMock()
    monkeypatch.setattr(bridget, "Bridge", bridge_cls)
    return bridge_cls


@pytest.mark.parametrize(
    "spec, expected",
    [(SERVER, "/dev/ttyUSB0:115200//0.0.0.0:15000"), (CLIENT, "/dev/ttyUSB1:57600//192.168.2.1:14550:0")],
)
def test_spec_str_and_hash(spec: BridgeFrontendSpec, expected: str) -> None:
    assert str(spec) == expected
    assert hash(spec) == hash(spec.model_copy())


@pytest.mark.parametrize("field, value", [("udp_listen_port", 65536), ("udp_target_port", -1), ("baud", 1234)])
def test_spec_rejects_invalid(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        BridgeFrontendSpec(**{**SERVER.model_dump(), field: value})


@pytest.mark.usefixtures("bridge_cls")
def test_first_boot_migrates_old_v1_userdata(tmp_path: Path) -> None:
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    (old_dir / "settings-2.json").write_text("corrupted", encoding="utf-8")
    (old_dir / "settings-1.json").write_text(json.dumps(V1_SETTINGS), encoding="utf-8")
    assert Bridget().get_bridges() == [SERVER, CLIENT]
    shutil.rmtree(old_dir)
    assert Bridget().get_bridges() == [SERVER, CLIENT]


def test_add_bridge_persists_and_restores(bridge_cls: MagicMock) -> None:
    Bridget().add_bridge(CLIENT)
    serial, *args = bridge_cls.call_args.args
    assert serial.device == "/dev/ttyUSB1"
    assert args == [57600, "192.168.2.1", 14550, 0]
    assert bridge_cls.call_args.kwargs == {"automatic_disconnect": False}
    restarted = Bridget()
    assert restarted.get_bridges() == [CLIENT]


def test_one_bridge_per_serial_port(bridge_cls: MagicMock) -> None:
    manager = Bridget()
    manager.add_bridge(SERVER)
    with pytest.raises(RuntimeError):
        manager.add_bridge(SERVER.model_copy(update={"udp_listen_port": 16000}))
    assert manager.get_bridges() == [SERVER]
    assert bridge_cls.call_count == 1


def test_failed_restore_is_kept_until_replaced(bridge_cls: MagicMock) -> None:
    Bridget().add_bridge(SERVER)
    bridge_cls.side_effect = RuntimeError("serial port is gone")
    offline = Bridget()
    assert offline.get_bridges() == []
    bridge_cls.side_effect = None
    assert Bridget().get_bridges() == [SERVER]
    replacement = SERVER.model_copy(update={"udp_listen_port": 16000})
    offline.add_bridge(replacement)
    assert Bridget().get_bridges() == [replacement]


def test_remove_bridge(bridge_cls: MagicMock) -> None:
    manager = Bridget()
    manager.add_bridge(SERVER)
    manager.add_bridge(CLIENT)
    manager.remove_bridge(SERVER)
    assert manager.get_bridges() == [CLIENT]
    bridge_cls.return_value.stop.assert_called_once()
    with pytest.raises(RuntimeError):
        manager.remove_bridge(SERVER)
    assert Bridget().get_bridges() == [CLIENT]


def test_stop_keeps_bridges_persisted(bridge_cls: MagicMock) -> None:
    manager = Bridget()
    manager.add_bridge(SERVER)
    manager.add_bridge(CLIENT)
    manager.stop()
    assert bridge_cls.return_value.stop.call_count == 2
    assert manager.get_bridges() == []
    assert Bridget().get_bridges() == [SERVER, CLIENT]


@pytest.mark.usefixtures("bridge_cls")
def test_available_serial_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    get = MagicMock()
    get.return_value.json.return_value = {"ports": [{"name": "/dev/ttyUSB0"}, {"name": None}]}
    monkeypatch.setattr(requests, "get", get)
    manager = Bridget()
    assert manager.available_serial_ports() == ["/dev/ttyUSB0"]
    get.side_effect = requests.ConnectionError("linux2rest is down")
    with pytest.raises(HTTPException) as error:
        manager.available_serial_ports()
    assert error.value.status_code == 502
