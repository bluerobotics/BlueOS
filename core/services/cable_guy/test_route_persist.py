import sys
from pathlib import Path

_CABLE_GUY_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _CABLE_GUY_DIR)
# Root pytest also finds other services' top-level modules (e.g. ardupilot_manager/typedefs.py).
_mod = sys.modules.get("typedefs")
if _mod is not None and not str(getattr(_mod, "__file__", "")).startswith(_CABLE_GUY_DIR):
    del sys.modules["typedefs"]

from typedefs import Route, managed_routes_only, persist_managed_route

MULTICAST = Route(destination="224.0.0.0/4", gateway=None, priority=None, managed=True)
LAN = Route(destination="192.168.0.0/24", gateway=None, priority=None, managed=False)
DEFAULT = Route(destination="0.0.0.0/0", gateway="192.168.0.1", priority=None, managed=False)
USER = Route(destination="10.0.0.0/8", gateway="192.168.2.1", priority=100, managed=False)


def test_migration_drops_unmanaged_and_keeps_multicast() -> None:
    assert managed_routes_only([LAN, DEFAULT, MULTICAST]) == [MULTICAST]


def test_apply_input_never_includes_dhcp_or_connected_routes() -> None:
    desired = managed_routes_only([DEFAULT, LAN, MULTICAST])
    assert DEFAULT not in desired
    assert LAN not in desired
    assert MULTICAST in desired


def test_add_merges_managed_and_strips_unmanaged() -> None:
    saved = persist_managed_route([MULTICAST, LAN, DEFAULT], "add", USER)
    assert MULTICAST in saved
    assert LAN not in saved
    assert DEFAULT not in saved
    owned = next(route for route in saved if route.destination == USER.destination)
    assert owned.managed is True
    assert owned.priority == 100


def test_add_persists_when_kernel_already_has_route() -> None:
    saved = persist_managed_route([MULTICAST], "add", MULTICAST)
    assert saved == [MULTICAST]
    assert saved[0].managed is True


def test_delete_removes_only_matching_managed_route() -> None:
    extra = Route(destination="10.1.0.0/16", gateway=None, priority=None, managed=True)
    saved = persist_managed_route([MULTICAST, extra, LAN], "del", extra)
    assert saved == [MULTICAST]


def test_route_identity_is_destination_and_gateway() -> None:
    unmanaged_copy = Route(destination="224.0.0.0/4", gateway=None, priority=None, managed=False)
    other_metric = Route(destination="224.0.0.0/4", gateway=None, priority=50, managed=True)
    assert unmanaged_copy == MULTICAST
    assert other_metric == MULTICAST
