from dataclasses import dataclass
from typing import Union

from pingutils import PingDeviceDescriptor


# TODO: This is a ugly workaround to have SysFS working for us
# Issue: https://github.com/tiangolo/fastapi/issues/4189
# pylint: disable=too-many-instance-attributes
@dataclass
class PingDeviceDescriptorModel:
    ping_type: str
    device_id: int
    device_model: int
    device_revision: int
    firmware_version_major: int
    firmware_version_minor: int
    firmware_version_patch: int
    port: str
    ethernet_discovery_info: str  # ip:port string for pings found with ethernet discovery
    driver_status: dict[str, Union[int, float, str, bool]]

    @staticmethod
    def from_descriptor(descriptor: PingDeviceDescriptor) -> "PingDeviceDescriptorModel":
        return PingDeviceDescriptorModel(
            ping_type=str(descriptor.ping_type),
            device_id=descriptor.device_id,
            device_model=descriptor.device_model,
            device_revision=descriptor.device_revision,
            firmware_version_major=descriptor.firmware_version_major,
            firmware_version_minor=descriptor.firmware_version_minor,
            firmware_version_patch=descriptor.firmware_version_patch,
            port=descriptor.port.device if descriptor.port is not None else "",
            ethernet_discovery_info=descriptor.ethernet_discovery_info
            if descriptor.ethernet_discovery_info is not None
            else "",
            driver_status=descriptor.driver.driver_status if descriptor.driver is not None else {},
        )
