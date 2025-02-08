"""Service definitions for BlueOS.

This module contains the definitions of all BlueOS services, including their commands and memory limits.
It is used by both the startup script and the commander service to ensure consistency.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Service:
    """Represents a BlueOS service."""

    command: str
    memory_limit: int
    priority: bool = False  # True for high-priority services that should start first


# Define all services
SERVICES: Dict[str, Service] = {
    "autopilot": Service(
        command="nice --19 /home/pi/services/ardupilot_manager/main.py", memory_limit=0, priority=True
    ),
    "cable_guy": Service(command="/home/pi/services/cable_guy/main.py", memory_limit=0, priority=True),
    "video": Service(
        command="nice --19 mavlink-camera-manager --default-settings BlueROVUDP --mavlink tcpout:127.0.0.1:5777 "
        "--mavlink-system-id 1 --gst-feature-rank omxh264enc=0,v4l2h264enc=250,x264enc=260 "
        "--log-path /var/logs/blueos/services/mavlink-camera-manager --stun-server stun://stun.l.google.com:19302 --verbose",
        memory_limit=0,
        priority=True,
    ),
    "mavlink2rest": Service(
        command="mavlink2rest --connect=udpout:127.0.0.1:14001 --server [::]:6040 --system-id 1 --component-id 194",
        memory_limit=0,
        priority=True,
    ),
    "kraken": Service(command="nice -19 /home/pi/services/kraken/main.py", memory_limit=0),
    "wifi": Service(command="nice -19 /home/pi/services/wifi/main.py --socket wlan0", memory_limit=0),
    "zenohd": Service(
        command="ZENOH_BACKEND_FS_ROOT=/home/pi/tools/zenoh zenohd -c /home/pi/tools/zenoh/blueos-zenoh.json5",
        memory_limit=0,
    ),
    "beacon": Service(command="/home/pi/services/beacon/main.py", memory_limit=250),
    "bridget": Service(command="nice -19 sudo -u blueos /home/pi/services/bridget/main.py", memory_limit=0),
    "commander": Service(command="/home/pi/services/commander/main.py", memory_limit=250),
    "nmea_injector": Service(
        command="nice -19 /home/pi/services/nmea_injector/nmea_injector/main.py", memory_limit=250
    ),
    "helper": Service(command="/home/pi/services/helper/main.py", memory_limit=250),
    "iperf3": Service(command="iperf3 --server --port 5201", memory_limit=250),
    "linux2rest": Service(
        command="linux2rest --log-path /var/logs/blueos/services/linux2rest "
        "--log-settings netstat=30,platform=10,serial-ports=10,system-cpu=10,system-disk=30,"
        "system-info=10,system-memory=10,system-network=10,system-process=60,system-temperature=10,"
        "system-unix-time-seconds=10",
        memory_limit=250,
    ),
    "filebrowser": Service(
        command="nice -19 filebrowser --database /etc/filebrowser/filebrowser.db --baseurl /file-browser",
        memory_limit=250,
    ),
    "versionchooser": Service(command="/home/pi/services/versionchooser/main.py", memory_limit=250),
    "pardal": Service(command="nice -19 /home/pi/services/pardal/main.py", memory_limit=250),
    "ping": Service(command="nice -19 sudo -u blueos /home/pi/services/ping/main.py", memory_limit=0),
    "user_terminal": Service(command="cat /etc/motd", memory_limit=0),
    "ttyd": Service(
        command='nice -19 ttyd -p 8088 sh -c "/usr/bin/tmux attach -t user_terminal || /usr/bin/tmux new -s user_terminal"',
        memory_limit=250,
    ),
    "nginx": Service(command="nice -18 nginx -g 'daemon off;' -c /home/pi/tools/nginx/nginx.conf", memory_limit=250),
    "log_zipper": Service(
        command="nice -20 /home/pi/services/log_zipper/main.py '/shortcuts/system_logs/\\*\\*/\\*.log' --max-age-minutes 60",
        memory_limit=250,
    ),
    "bag_of_holding": Service(command="/home/pi/services/bag_of_holding/main.py", memory_limit=250),
}


def get_priority_services() -> List[str]:
    """Get the list of priority services that should start first."""
    return [name for name, service in SERVICES.items() if service.priority]


def get_regular_services() -> List[str]:
    """Get the list of regular (non-priority) services."""
    return [name for name, service in SERVICES.items() if not service.priority]


def get_service(name: str) -> Service:
    """Get a service by name. Raises KeyError if service doesn't exist."""
    return SERVICES[name]
