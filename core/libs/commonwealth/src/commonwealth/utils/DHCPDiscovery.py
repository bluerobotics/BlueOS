#! /usr/bin/env python3
import asyncio
import re
import sys
from typing import List

from loguru import logger


class DHCPDiscoveryError(Exception):
    """Base exception for DHCP discovery errors"""


async def discover_dhcp_servers(iface: str, timeout: int = 15) -> List[str]:
    """
    Discover DHCP servers on the network using nmap's DHCP discovery script

    Args:
        interface: Network interface to use
        timeout: Time to wait for responses in seconds

    Returns:
        List of DHCP server IP addresses found

    Raises:
        DHCPDiscoveryError: If discovery fails
    """
    try:
        # Run nmap with DHCP discovery script
        cmd = [
            "sudo",  # Need root privileges
            "nmap",
            "--script",
            "broadcast-dhcp-discover",
            "-e",
            iface,  # Specify interface
            "--script-timeout",
            f"{timeout}s",
        ]

        # Run nmap asynchronously
        logger.info(f"Running nmap command: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        output = stdout.decode()
        error = stderr.decode()

        if process.returncode != 0:
            logger.info(f"nmap output: {output}")
            logger.info(f"nmap error: {error}")
            raise DHCPDiscoveryError(f"nmap failed: {error}")

        # Parse nmap output for DHCP servers
        servers = []

        # Look for Server Identifier or DHCP Server lines
        server_pattern = r"Server(?:\s+Identifier|\s*:)\s*(\d+\.\d+\.\d+\.\d+)"
        for match in re.finditer(server_pattern, output):
            server_ip = match.group(1)
            if server_ip not in servers:
                servers.append(server_ip)

        return servers

    except FileNotFoundError as e:
        raise DHCPDiscoveryError("nmap is not installed. Please install nmap package.") from e
    except Exception as e:
        raise DHCPDiscoveryError(f"Failed to discover DHCP servers: {str(e)}") from e


async def main() -> None:
    """Main function for command line usage"""
    interface_to_scan = sys.argv[1]

    try:
        servers = await discover_dhcp_servers(interface_to_scan)
        if servers:
            print(f"Found {len(servers)} DHCP server(s):")
            for server in servers:
                print(f"  {server}")
        else:
            print("No DHCP servers found.")
    except DHCPDiscoveryError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: sudo {sys.argv[0]} <interface>")
        sys.exit(1)
    asyncio.run(main())
