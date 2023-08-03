import asyncio
import socket
from typing import List, Set

import psutil
from loguru import logger


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


async def find_ping360_ethernet() -> List[str]:
    """
    Return a list of Ping360 IPs found in the connected ethernet interfaces
    """
    found = []
    loop = asyncio.get_running_loop()
    for ip in list_ips():
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
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
            raw_ip = decoded_message.split("IP Address:- ")[1].strip()
            found.append(remove_zeros(raw_ip))
        except socket.timeout:
            logger.debug(f"timed out waiting for ping360 at ip {ip}")
        except Exception as e:
            logger.error(f"Error while probing for ping360 at ip {ip}: {e}")
    return found
