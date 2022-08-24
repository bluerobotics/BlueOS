from typing import Optional

from pydantic import BaseModel

from pingutils import PingDeviceDescriptor


class DriverStatus(BaseModel):
    udp_port: Optional[int]
    mavlink_driver_enabled: bool

    @staticmethod
    def unknown() -> "DriverStatus":
        return DriverStatus(udp_port=None, mavlink_driver_enabled=False)


# TODO: This is a ugly workaround to have SysFS working for us
# Issue: https://github.com/tiangolo/fastapi/issues/4189
class PingDeviceDescriptorModel(BaseModel):
    ping_type: str
    device_id: int
    device_model: int
    device_revision: int
    firmware_version_major: int
    firmware_version_minor: int
    firmware_version_patch: int
    port: str
    ethernet_discovery_info: Optional[str]  # ip:port string for pings found with ethernet discovery
    driver_status: DriverStatus

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
            ethernet_discovery_info=descriptor.ethernet_discovery_info,
            driver_status=descriptor.driver.driver_status if descriptor.driver is not None else DriverStatus.unknown(),
        )
