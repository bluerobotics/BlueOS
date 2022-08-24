from typing import Any, Callable, Coroutine, Optional

from brping import PingDevice
from brping.definitions import COMMON_DEVICE_INFORMATION, PING1D_FIRMWARE_VERSION
from loguru import logger
from serial.tools.list_ports_linux import SysFS

from pingutils import PingDeviceDescriptor, PingType


class PingProber:
    """PingProber is responsible for identifying Ping-enabled devices on serial ports."""

    async def probe(self, port: SysFS) -> Optional[PingDeviceDescriptor]:
        """Attempts to communicate via Ping Protocol at port "port".
        Calls on_ping_found callback when a ping device is found."""
        logger.info(f"Probing {port}")
        detected_device = self.detect_device(port)
        if detected_device:
            await self.ping_found_callback(detected_device)
        return detected_device

    def on_ping_found(self, callback: Callable[[PingDeviceDescriptor], Coroutine[Any, Any, None]]) -> None:
        self.ping_found_callback = callback

    @staticmethod
    def legacy_detect_ping1d(port: SysFS) -> Optional[PingDeviceDescriptor]:
        """
        Detects Ping1D devices without DEVICE_INFORMATION implemented
        """
        ping = PingDevice()
        ping.connect_serial(port.device, 115200)
        firmware_version = ping.request(PING1D_FIRMWARE_VERSION)
        if firmware_version is None:
            return None
        descriptor = PingDeviceDescriptor(
            ping_type=PingType.PING1D,
            device_id=firmware_version.src_device_id,
            device_model=firmware_version.device_model,
            device_revision=0,  # not available in this message
            firmware_version_major=firmware_version.firmware_version_major,
            firmware_version_minor=firmware_version.firmware_version_minor,
            firmware_version_patch=0,
            ethernet_discovery_info=None,
            driver=None,
            port=port,
        )
        logger.info("Identified ping device:")
        logger.info(descriptor)
        return descriptor

    def detect_device(self, port: SysFS) -> Optional[PingDeviceDescriptor]:
        """
        Attempts to detect the Ping device attached to serial port 'dev'
        Returns the new path with encoded name if detected, or None if the
        device was not detected
        """

        try:
            ping = PingDevice()
            ping.connect_serial(port.device, 115200)

        except Exception as exception:
            if exception.args[0] and "Errno 16" in exception.args[0]:
                logger.info(f"Device {port.hwid} is busy. Re-trying...")
                return None

            logger.info(
                f"An exception has occurred while attempting to"
                f"talk Ping to device {port.hwid}: {exception}"
                f"If this is not a Ping device, this is expected."
            )
            return None

        if not ping.initialize():
            return None

        device_info = ping.request(COMMON_DEVICE_INFORMATION)
        if not device_info:
            return self.legacy_detect_ping1d(port)

        if device_info.device_type not in [PingType.PING1D, PingType.PING360]:
            logger.warning(
                f"PingProber was able to talk Ping to {port.hwid},"
                f"but the device id {device_info.device_type} is not known"
            )
            return None

        descriptor = PingDeviceDescriptor(
            ping_type=PingType(device_info.device_type),
            device_id=device_info.src_device_id,
            device_model=0,  #  not available in this message
            device_revision=device_info.device_revision,
            firmware_version_major=device_info.firmware_version_major,
            firmware_version_minor=device_info.firmware_version_minor,
            firmware_version_patch=0,
            port=port,
            ethernet_discovery_info=None,
            driver=None,
        )
        logger.info("Identified ping device:")
        logger.info(descriptor)
        return descriptor
