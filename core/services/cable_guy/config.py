# This file is used to define general configurations for the app

from ipaddress import ip_network
from typedefs import AddressMode, InterfaceAddress, NetworkInterface, Route

SERVICE_NAME = "cable-guy"

# If no valid configuration is found, this will be used as the default
DEFAULT_NETWORK_INTERFACES = [
    NetworkInterface(
        name="eth0",
        addresses=[
            InterfaceAddress(ip="192.168.2.2", mode=AddressMode.BackupServer),
            InterfaceAddress(ip="0.0.0.0", mode=AddressMode.Client),
        ],
        routes=[
            Route(
                destination=str(ip_network("224.0.0.0/4")),
                gateway=None,
                priority=None,
                managed=True,
            )
        ],
    ),
    NetworkInterface(name="usb0", addresses=[InterfaceAddress(ip="192.168.3.1", mode=AddressMode.Server)], routes=[]),
]
