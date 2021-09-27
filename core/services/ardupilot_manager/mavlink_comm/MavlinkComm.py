import json
import os
import time
from typing import Any, Dict, Optional

import requests

from exceptions import (
    FetchUpdatedMessageFail,
    MavlinkMessageReceiveFail,
    MavlinkMessageSendFail,
)


class MavlinkMessenger:
    def __init__(self) -> None:
        self.system_id = int(os.environ.get("MAV_SYSTEM_ID", 1))
        self.component_id = int(os.environ.get("MAV_COMPONENT_ID_ONBOARD_COMPUTER4", 194))
        self.sequence = 0
        self.m2r_address = "localhost:8088"
        self.m2r_rest_url = f"http://{self.m2r_address}/mavlink"

    def set_system_id(self, system_id: int) -> None:
        self.system_id = system_id

    def set_component_id(self, component_id: int) -> None:
        self.component_id = component_id

    def set_sequence(self, sequence: int) -> None:
        self.sequence = sequence

    def set_m2r_address(self, address: str) -> None:
        if len(address.split(":")) != 2:
            raise ValueError("Invalid address. Valid address should follow the format 'localhost:8088'.")
        self.m2r_address = address
        self.m2r_rest_url = f"http://{self.m2r_address}/mavlink"

    def get_mavlink_message(
        self, message_name: Optional[str] = None, vehicle: Optional[int] = 1, component: Optional[int] = 1
    ) -> Any:
        request_url = f"{self.m2r_rest_url}/vehicles/{vehicle}/components/{component}/messages"
        if message_name:
            request_url += f"/{message_name.upper()}"

        response = requests.get(request_url, timeout=1)
        if not response.status_code == 200:
            raise MavlinkMessageReceiveFail

        return response.json()

    def get_updated_mavlink_message(
        self,
        message_name: str,
        vehicle: int = 1,
        component: int = 1,
        timeout: float = 10.0,
    ) -> Any:
        first_message = self.get_mavlink_message(message_name, vehicle, component)
        first_message_counter = first_message["status"]["time"]["counter"]
        t0 = time.time()
        while True:
            new_message = self.get_mavlink_message(message_name, vehicle, component)
            new_message_counter = new_message["status"]["time"]["counter"]
            if new_message_counter > first_message_counter:
                break
            if (time.time() - t0) > timeout:
                raise FetchUpdatedMessageFail(f"Did not receive an updated {message_name} before timeout.")
            time.sleep(timeout / 10.0)

        return new_message

    def send_mavlink_message(self, message: Dict[str, Any]) -> None:
        mavlink2rest_package = {
            "header": {"system_id": self.system_id, "component_id": self.component_id, "sequence": self.sequence},
            "message": message,
        }

        response = requests.post(self.m2r_rest_url, data=json.dumps(mavlink2rest_package), timeout=5.0)
        if not response.status_code == 200:
            raise MavlinkMessageSendFail
