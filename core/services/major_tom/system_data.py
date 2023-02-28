import re
import subprocess
from typing import Any, Dict, List

import psutil


class SystemDataGatherer:
    def get_disk_usage(self) -> Dict[str, Any]:
        results = {}
        for partition in psutil.disk_partitions():
            results[partition.mountpoint] = {"device": partition.device, "usage": None}
            try:
                results[partition.mountpoint]["usage"] = psutil.disk_usage(partition.mountpoint)
            except Exception as error:
                print(f"unable to read disk usage: {error}")
        return results

    def get_memory_usage(self) -> Any:
        return psutil.virtual_memory()

    def get_usb_devices(self) -> List[Dict[str, Any]]:
        device_re = re.compile(
            r"Bus\s+(?P<bus>\d+)\s+Device\s+(?P<device>\d+).+ID\s(?P<id>\w+:\w+)\s(?P<name>.+)$", re.I
        )
        lsusb = subprocess.check_output("lsusb", encoding="utf-8")
        devices = []
        for line in lsusb.split("\n"):
            if line:
                info = device_re.match(line)
                if info:
                    device_info = info.groupdict()
                    device_info["device"] = f"/dev/bus/usb/{device_info.pop('bus')}/{device_info.pop('device')}"
                    devices.append(device_info)
        return devices

    def get_temps(self) -> Any:
        return psutil.sensors_temperatures()

    def get_cpu_info(self) -> Dict[str, Any]:
        serial_number = None
        model = None
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    # extract part after the ':'
                    model = "".join(line.strip().split(":")[1:])

                if line.startswith("Serial"):
                    # Extract the serial number using a regular expression
                    serial_number = re.findall(r"\w{16}", line)[0]
        return {"serial": serial_number, "model": model}

    def get_system_data(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        data["disk"] = self.get_disk_usage()
        data["memory"] = self.get_memory_usage()
        data["usb"] = self.get_usb_devices()
        data["thermal"] = self.get_temps()
        data["cpu"] = self.get_cpu_info()
        return data
