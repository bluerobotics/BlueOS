from types import SimpleNamespace

from settings import BridgeSettingsSpecV1, BridgeSettingsSpecV2, SettingsV1, SettingsV2
from views import BridgeSummary


def test_bridge_settings_spec_eq_by_serial_path() -> None:
    a = BridgeSettingsSpecV2(
        serial_path="/dev/ttyUSB0",
        baudrate=115200,
        ip="0.0.0.0",
        udp_target_port=0,
        udp_listen_port=14550,
    )
    b = BridgeSettingsSpecV2(
        serial_path="/dev/ttyUSB0",
        baudrate=57600,
        ip="10.0.0.1",
        udp_target_port=1,
        udp_listen_port=2,
    )
    c = BridgeSettingsSpecV2(
        serial_path="/dev/ttyUSB1",
        baudrate=115200,
        ip="0.0.0.0",
        udp_target_port=0,
        udp_listen_port=14550,
    )
    assert a == b
    assert a != c
    assert a != "nope"


def test_bridge_settings_spec_v1_eq() -> None:
    a = BridgeSettingsSpecV1(serial_path="/dev/ttyUSB0", baudrate=115200, ip="0.0.0.0", udp_port=1)
    b = BridgeSettingsSpecV1(serial_path="/dev/ttyUSB0", baudrate=9600, ip="1.1.1.1", udp_port=2)
    assert a == b
    assert a != BridgeSettingsSpecV1(serial_path="/dev/ttyX", baudrate=115200, ip="0.0.0.0", udp_port=1)


def test_bridge_settings_from_summary_like_spec() -> None:
    summary = BridgeSummary(
        serial_path="/dev/ttyUSB0",
        baud=115200,
        ip="192.168.2.1",
        udp_target_port=10,
        udp_listen_port=20,
    )
    # from_spec accepts any object with the same attributes (legacy BridgeIdentity shape).
    v2 = BridgeSettingsSpecV2.from_spec(summary)  # type: ignore[arg-type]
    assert v2.serial_path == summary.serial_path
    assert v2.baudrate == summary.baud
    assert v2.udp_target_port == 10
    assert v2.udp_listen_port == 20

    v1 = BridgeSettingsSpecV1.from_spec(
        SimpleNamespace(serial_path="/dev/ttyUSB0", baud=9600, ip="0.0.0.0", udp_port=14550)
    )
    assert v1.udp_port == 14550
    assert v1.baudrate == 9600


def test_settings_v2_migrates_v1_server_and_client_specs() -> None:
    v1, v2 = SettingsV1(), SettingsV2()
    data = {
        "VERSION": v1.VERSION,
        "specs": [
            {"serial_path": "/dev/ttyUSB0", "baudrate": 115200, "ip": "0.0.0.0", "udp_port": 14550},
            {"serial_path": "/dev/ttyUSB1", "baudrate": 57600, "ip": "192.168.2.1", "udp_port": 14551},
        ],
    }
    v2.migrate(data)

    assert data["VERSION"] == v2.VERSION
    assert data["specsv2"] == [
        {
            "serial_path": "/dev/ttyUSB0",
            "baudrate": 115200,
            "ip": "0.0.0.0",
            "udp_target_port": 0,
            "udp_listen_port": 14550,
        },
        {
            "serial_path": "/dev/ttyUSB1",
            "baudrate": 57600,
            "ip": "192.168.2.1",
            "udp_target_port": 14551,
            "udp_listen_port": 0,
        },
    ]


def test_settings_v2_migrate_noop_when_current() -> None:
    v2 = SettingsV2()
    data = {"VERSION": v2.VERSION, "specs": [], "specsv2": []}
    v2.migrate(data)
    assert data == {"VERSION": v2.VERSION, "specs": [], "specsv2": []}
