from pathlib import Path

import pytest
from commonwealth.settings.manager import PydanticManager
from nmea_injector.adapters import (
    AsyncioSockListener,
    MavlinkMessengerSink,
    PydanticSockSettingsStore,
)
from nmea_injector.commands import AddSock, SocketKind
from nmea_injector.exceptions import UnsupportedSocketKind
from nmea_injector.settings import NmeaInjectorSettingsSpecV1, SettingsV1
from nmea_injector.views import SockSummary, SocksView


def test_nmea_settings_spec_eq_by_kind_and_port() -> None:
    a = NmeaInjectorSettingsSpecV1(kind="UDP", port=27000, component_id=220)
    b = NmeaInjectorSettingsSpecV1(kind="UDP", port=27000, component_id=221)
    c = NmeaInjectorSettingsSpecV1(kind="TCP", port=27000, component_id=220)
    assert a == b
    assert a != c
    assert a != "nope"


def test_nmea_settings_migrate_clamps_newer_version() -> None:
    settings = SettingsV1()
    data = {"VERSION": settings.VERSION + 10, "specs": []}
    settings.migrate(data)
    assert data["VERSION"] == settings.VERSION


def test_nmea_settings_migrate_noop_when_current() -> None:
    settings = SettingsV1()
    data = {"VERSION": settings.VERSION, "specs": [{"kind": "UDP", "port": 1, "component_id": 220}]}
    before = dict(data)
    settings.migrate(data)
    assert data == before


@pytest.mark.asyncio
async def test_asyncio_listener_rejects_unknown_kind() -> None:
    listener = AsyncioSockListener(MavlinkMessengerSink())
    with pytest.raises(UnsupportedSocketKind, match="Expected one of"):
        await listener.listen("SCTP", 27000, 220)


def test_pydantic_sock_settings_store_roundtrip(tmp_path: Path) -> None:
    store = PydanticSockSettingsStore(PydanticManager("nmea-test", SettingsV1, tmp_path))
    assert store.load() == []

    view = SocksView(socks=(SockSummary(kind=SocketKind.UDP, port=27000, component_id=220),))
    store.save(view)
    assert store.load() == [AddSock(SocketKind.UDP, 27000, 220)]
