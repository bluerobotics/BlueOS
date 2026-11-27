import json
from ipaddress import IPv4Address, IPv4Network

import pytest
from blueos.core import BlueOS
from features.network import ClientPc

# The backup dhcp server of cable-guy's default eth0 configuration
BLUEOS_DHCP_SERVER = IPv4Address("192.168.2.2")
BLUEOS_NETWORK = IPv4Network("192.168.2.0/24")


@pytest.mark.usefixtures("network_without_dhcp_server")
def test_blueos_serves_dhcp_when_the_network_has_none(client_pc: ClientPc, blueos: BlueOS) -> None:
    with client_pc.connected() as lease:
        assert lease.server == BLUEOS_DHCP_SERVER, lease
        assert lease.ip in BLUEOS_NETWORK, lease
        leases = blueos.cable_guy.dhcp_leases("eth0")
        assert str(lease.ip) in [entry["ip"] for entry in leases], leases
        # The PC reaches BlueOS at its fixed address
        version = json.loads(client_pc.get(f"http://{BLUEOS_DHCP_SERVER}/version-chooser/v1.0/version/current"))
        assert version == blueos.version()
