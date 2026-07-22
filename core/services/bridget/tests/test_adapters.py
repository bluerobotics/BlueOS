from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from adapters import (
    BridgesLibRuntime,
    Linux2RestSerialCatalog,
    PydanticBridgeSettingsStore,
)
from bridges.serialhelper import Baudrate
from commands import AddBridge
from views import BridgeSummary, BridgesView


def test_serial_catalog_lists_named_ports() -> None:
    response = MagicMock()
    response.json.return_value = {"ports": [{"name": "/dev/ttyUSB0"}, {"name": None}, {"name": "/dev/ttyACM0"}]}
    with patch("adapters.requests.get", return_value=response) as get:
        assert Linux2RestSerialCatalog().list_ports() == ["/dev/ttyUSB0", "/dev/ttyACM0"]
    get.assert_called_once_with("http://localhost:6030/serial", timeout=1)


def test_serial_catalog_request_error_returns_empty() -> None:
    with patch("adapters.requests.get", side_effect=requests.RequestException("down")):
        assert Linux2RestSerialCatalog().list_ports() == []


def test_bridges_lib_runtime_opens_bridge() -> None:
    bridge = MagicMock()
    with patch("adapters.SysFS") as sysfs, patch("adapters.Bridge", return_value=bridge) as bridge_ctor:
        opened = BridgesLibRuntime().open("/dev/ttyUSB0", 115200, "192.168.2.1", 14550, 14551)

    assert opened is bridge
    sysfs.assert_called_once_with("/dev/ttyUSB0")
    bridge_ctor.assert_called_once()
    args, kwargs = bridge_ctor.call_args
    assert args[1] == Baudrate(115200)
    assert args[2:] == ("192.168.2.1", 14550, 14551)
    assert kwargs["automatic_disconnect"] is False


def test_pydantic_bridge_settings_store_roundtrip(tmp_path: Path) -> None:
    store = PydanticBridgeSettingsStore(tmp_path)
    assert store.load() == []

    view = BridgesView(
        bridges=(
            BridgeSummary(
                serial_path="/dev/ttyUSB0",
                baud=115200,
                ip="192.168.2.1",
                udp_target_port=14550,
                udp_listen_port=14551,
            ),
        )
    )
    store.save(view)
    assert store.load() == [
        AddBridge("/dev/ttyUSB0", 115200, "192.168.2.1", 14550, 14551),
    ]
