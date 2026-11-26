import re
from typing import Optional

from serial.tools.list_ports_linux import SysFS

GENERIC_SERIAL_PLATFORM = "GenericSerial"

AUTOPILOT_USB_VIDS = {
    0x0483,  # STMicroelectronics, ChibiOS default
    0x1209,  # pid.codes, used by ArduPilot
    0x1FC9,  # NXP
    0x26AC,  # 3D Robotics / PX4
    0x2DAE,  # CubePilot / Hex
    0x3162,  # Holybro
    0x3163,  # CUAV
    0x3185,  # ARK
}

# Identifiers BlueOS used before boards were identified by their ArduPilot board id
LEGACY_PRODUCTS = ["Pixhawk1", "FMU v2.x", "FMU v3.x", "Pixhawk4", "FMU v5.x", "FMU v6X.x", "FMU v6C.x", "CubeOrange"]
LEGACY_MANUFACTURERS = ["ArduPilot", "Arduino", "3D Robotics", "Hex/ProfiCNC", "Holybro", "CubePilot"]

# PX4 firmware and bootloaders report the FMU version instead of the ArduPilot platform name
PX4_PRODUCT_PLATFORMS = {
    "FMU v2.x": "Pixhawk1",
    "FMU v3.x": "Pixhawk1",
    "FMU v5.x": "Pixhawk4",
    "FMU v6X.x": "Pixhawk6X",
    "FMU v6C.x": "Pixhawk6C",
}

# ArduPilot hwdefs whose USB product (USB_STRING_PRODUCT) is not their board name, which is the manifest platform
PRODUCT_PLATFORMS = {
    "CubeOrange+": "CubeOrangePlus",
    "CubeRed": "CubeRedPrimary",
}

# Linux boards use the CUAV CAN Babel as a SLCAN adapter
DENIED_PRODUCTS = ["CAN Babel"]

# "-BL", " BL" and signed bootloaders' "-Secure-BL-v10"
BOOTLOADER_SUFFIX = re.compile(r"[- ](Secure-)?BL(-v\d+)?$")


def is_usb_port(port: SysFS) -> bool:
    return port.vid is not None and port.usb_device_path is not None


def is_plausible_autopilot(port: SysFS) -> bool:
    if not is_usb_port(port):
        return False
    product = port.product or ""
    manufacturer = port.manufacturer or ""
    if any(denied in product for denied in DENIED_PRODUCTS):
        return False
    if port.vid in AUTOPILOT_USB_VIDS:
        return True
    return any(identifier in product for identifier in LEGACY_PRODUCTS) or any(
        identifier in manufacturer for identifier in LEGACY_MANUFACTURERS
    )


def serial_platform_name(product: Optional[str]) -> str:
    """ArduPilot ChibiOS boards use the hwdef board name, which is the manifest platform, as USB product."""
    if not product:
        return GENERIC_SERIAL_PLATFORM
    for identifier, platform in PX4_PRODUCT_PLATFORMS.items():
        if identifier in product:
            return platform
    name = BOOTLOADER_SUFFIX.sub("", product.strip())
    return PRODUCT_PLATFORMS.get(name, name) or GENERIC_SERIAL_PLATFORM
