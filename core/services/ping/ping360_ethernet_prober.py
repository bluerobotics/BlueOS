#!/usr/bin/env python3
"""
Scan with ./findPing360.py [current IP of the interface to scan]
"""

import argparse
import asyncio
import socket
import time

import psutil


def list_ips():
    stats = psutil.net_if_stats()

    available_networks = []
    ips = []
    for interface in stats.keys():
        if interface in stats and getattr(stats[interface], "isup"):
            available_networks.append(interface)

    for interface in available_networks:
        phys_list = list(filter(lambda address: address.family == socket.AF_INET, psutil.net_if_addrs()[interface]))
        ips.extend([phys.address for phys in phys_list])
    return ips


def remove_zeros(ip):
    new_ip = ".".join([str(int(i)) for i in ip.split(".")])
    return new_ip


async def find_ping360_ethernet():
    found = []
    for ip in list_ips():
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Set a timeout so the socket does not block
        # indefinitely when trying to receive data.
        server.settimeout(0.2)
        server.bind((ip, 30303))
        message = b"Discovery"

        server.sendto(message, ("255.255.255.255", 30303))
        # print("Discovery message sent...")
        await asyncio.sleep(1)
        try:
            data, client = server.recvfrom(1048)
            raw_ip = data.decode("utf8").split("IP Address:- ")[1].strip()
            found.append(remove_zeros(raw_ip))
        except socket.timeout as e:
            print(e)
    return found
