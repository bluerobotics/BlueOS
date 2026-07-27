import socket
from types import SimpleNamespace
from unittest.mock import patch

import ping360_ethernet_prober
import psutil


def test_list_ips_ignores_interfaces_missing_from_address_snapshot() -> None:
    stats = {
        "eth0": SimpleNamespace(isup=True),
        "lo": SimpleNamespace(isup=True),
        "wlan0": SimpleNamespace(isup=False),
        "noipv4": SimpleNamespace(isup=True),
        "uap0": SimpleNamespace(isup=True),
    }
    addresses = {
        "eth0": [SimpleNamespace(family=socket.AF_INET, address="192.168.2.2")],
        "lo": [SimpleNamespace(family=socket.AF_INET, address="127.0.0.1")],
        "wlan0": [SimpleNamespace(family=socket.AF_INET, address="192.168.10.2")],
        "noipv4": [SimpleNamespace(family=socket.AF_INET6, address="::1")],
    }

    with (
        patch.object(psutil, "net_if_stats", return_value=stats),
        patch.object(psutil, "net_if_addrs", return_value=addresses),
    ):
        assert ping360_ethernet_prober.list_ips() == {"192.168.2.2"}


def test_list_ips_returns_empty_set_for_empty_snapshots() -> None:
    with (
        patch.object(psutil, "net_if_stats", return_value={}),
        patch.object(psutil, "net_if_addrs", return_value={}),
    ):
        assert ping360_ethernet_prober.list_ips() == set()
