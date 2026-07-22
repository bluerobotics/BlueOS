from pathlib import Path
from typing import List

import requests
from bridges.bridges import Bridge
from bridges.serialhelper import Baudrate
from commands import AddBridge
from commonwealth.settings.manager import PydanticManager
from loguru import logger
from ports import LiveBridge
from serial.tools.list_ports_linux import SysFS
from settings import BridgeSettingsSpecV2, SettingsV2
from views import BridgesView


class Linux2RestSerialCatalog:
    def list_ports(self) -> List[str]:
        try:
            response = requests.get("http://localhost:6030/serial", timeout=1)
            data = response.json()
            return [port["name"] for port in data["ports"] if port["name"] is not None]
        except requests.RequestException as e:
            logger.error(f"Error fetching data: {e}")
            return []


class BridgesLibRuntime:
    # pylint: disable-next=too-many-arguments
    def open(
        self,
        serial_path: str,
        baud: int,
        ip: str,
        udp_target_port: int,
        udp_listen_port: int,
    ) -> LiveBridge:
        return Bridge(
            SysFS(serial_path),
            Baudrate(baud),
            ip,
            udp_target_port,
            udp_listen_port,
            automatic_disconnect=False,
        )


class PydanticBridgeSettingsStore:
    def __init__(self, path: Path) -> None:
        self._manager = PydanticManager("bridget", SettingsV2, path)

    def load(self) -> List[AddBridge]:
        return [
            AddBridge(
                serial_path=spec.serial_path,
                baud=int(spec.baudrate),
                ip=spec.ip,
                udp_target_port=spec.udp_target_port,
                udp_listen_port=spec.udp_listen_port,
            )
            for spec in self._manager.settings.specsv2
        ]

    def save(self, view: BridgesView) -> None:
        self._manager.settings.specsv2 = [
            BridgeSettingsSpecV2(
                serial_path=bridge.serial_path,
                baudrate=bridge.baud,
                ip=bridge.ip,
                udp_target_port=bridge.udp_target_port,
                udp_listen_port=bridge.udp_listen_port,
            )
            for bridge in view.bridges
        ]
        self._manager.save()
