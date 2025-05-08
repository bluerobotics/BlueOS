import logging
from enum import IntEnum
from pathlib import Path

from serial.tools.list_ports_linux import SysFS


class Baudrate(IntEnum):
    b1200 = 1200
    b1800 = 1800
    b2400 = 2400
    b4800 = 4800
    b9600 = 9600
    b19200 = 19200
    b38400 = 38400
    b57600 = 57600
    b115200 = 115200
    b230400 = 230400
    b460800 = 460800
    b500000 = 500000
    b576000 = 576000
    b921600 = 921600
    b1000000 = 1000000
    b1152000 = 1152000
    b1500000 = 1500000
    b2000000 = 2000000
    b2500000 = 2500000
    b3000000 = 3000000
    b3500000 = 3500000
    b4000000 = 4000000


def set_low_latency(port: SysFS) -> None:
    """
    sets the latency_timer for the serial adapter
    """

    device_name = Path(port.device.strip()).name
    latency_file = f"/sys/bus/usb-serial/devices/{device_name}/latency_timer"
    logging.info(f"Latency file: {latency_file}")

    try:
        with open(latency_file, "w", encoding="utf-8") as p:
            p.write("1")
            p.flush()
    except IOError:
        logging.warning(f"Unable to set latency for device {device_name}, your device may work slower than expected.")
