import asyncio
import socket
from typing import List, Set

import psutil
from loguru import logger

from pingutils import PingDeviceDescriptor, PingType


def list_ips() -> Set[str]:
    """
    Returns a list of IPs found on ethernet interfaces that are currently up.
    """
    stats = psutil.net_if_stats()

    available_networks = []
    ips: List[str] = []
    for interface in stats:
        if getattr(stats[interface], "isup"):
            available_networks.append(interface)

    network_interface_addresses = psutil.net_if_addrs()
    for interface in available_networks:
        ips.extend(
            phys.address
            for phys in network_interface_addresses[interface]
            if phys.family == socket.AF_INET and phys.address != "127.0.0.1"
        )
    return set(ips)  # make sure there are not duplicated entries


def remove_zeros(ip: str) -> str:
    """
    Removes leading zeros from sections of an IP address.
      e.g. transforms 192.168.015.016 into 192.168.15.16

    Leading zero IPs are returned by the Ping360 firmware.
    """
    new_ip = ".".join(str(int(section)) for section in ip.split("."))
    return new_ip


async def find_ping360_ethernet() -> List[PingDeviceDescriptor]:
    """
    Return a list of Ping360 devices found in the connected ethernet interfaces
    """
    found = []
    loop = asyncio.get_running_loop()
    for ip in list_ips():
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Set a timeout so the socket does not block
        # indefinitely when trying to receive data.
        server.settimeout(0.2)
        try:
            server.bind((ip, 30303))
        except OSError:
            continue
        message = b"Discovery"

        server.sendto(message, ("255.255.255.255", 30303))
        await asyncio.sleep(1)
        try:
            data = await loop.sock_recv(server, 2048)
            decoded_message = data.decode("utf8")
            logger.info(f"Data received: {decoded_message}")
            device_type, _, _, ip_address, *extras = decoded_message.split("\n")
            formatted_ip = remove_zeros(ip_address.replace("IP Address:-", "").strip())
            port = "12345"
            for line in extras:
                if line.startswith("Port:-"):
                    port = line[6:].strip()

            found.append(
                PingDeviceDescriptor(
                    ping_type=PingType.PING360 if "PING360" in device_type else PingType.UNKNOWN,
                    device_id=0,
                    device_model=0,
                    device_revision=0,
                    firmware_version_major=0,
                    firmware_version_minor=0,
                    firmware_version_patch=0,
                    ethernet_discovery_info=f"{formatted_ip}:{port}",
                    port=None,
                    driver=None,
                )
            )
        except socket.timeout:
            logger.debug(f"timed out waiting for ping360 at ip {ip}")
        except Exception as e:
            logger.error(f"Error while probing for ping360 at ip {ip}: {e}")
    return found
