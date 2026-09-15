"""Decoding of 802.11 vendor information elements.

Access points that cloak their SSID keep advertising WPS and P2P vendor elements, and those
carry the device name, manufacturer and model. Decoding them is the only way to tell apart the
several cloaked networks a user sees while scanning.

The elements come from whatever frame the supplicant kept for the BSS, usually a probe
response, so an access point may advertise more there than it does on its beacon.
"""

from typing import Dict, Iterator, Optional, Tuple

from pydantic import BaseModel

VENDOR_SPECIFIC_ELEMENT_ID = 0xDD

WPS_OUI = b"\x00\x50\xf2"
WPS_OUI_TYPE = 0x04
P2P_OUI = b"\x50\x6f\x9a"
P2P_OUI_TYPE = 0x09

WPS_DEVICE_NAME = 0x1011
WPS_MANUFACTURER = 0x1021
WPS_MODEL_NAME = 0x1023
WPS_MODEL_NUMBER = 0x1024
WPS_SETUP_STATE = 0x1044
WPS_PRIMARY_DEVICE_TYPE = 0x1054

WPS_SETUP_STATE_CONFIGURED = 0x02

P2P_CAPABILITY = 0x02
P2P_DEVICE_INFO = 0x0D
P2P_GROUP_OWNER_BIT = 0x01

# Device type categories are only meaningful under the Wi-Fi Alliance OUI, vendors are free to
# define their own numbering under their own OUI
WPS_DEVICE_TYPE_OUI = b"\x00\x50\xf2\x04"

DEVICE_TYPES: Dict[int, Tuple[str, Dict[int, str]]] = {
    1: (
        "Computer",
        {
            1: "PC",
            2: "Server",
            3: "Media Center",
            4: "Ultra-mobile PC",
            5: "Notebook",
            6: "Desktop",
            7: "Mobile Internet Device",
            8: "Netbook",
            9: "Tablet",
        },
    ),
    2: (
        "Input Device",
        {
            1: "Keyboard",
            2: "Mouse",
            3: "Joystick",
            4: "Trackball",
            5: "Gaming Controller",
            6: "Remote",
            7: "Touchscreen",
            8: "Biometric Reader",
            9: "Barcode Reader",
        },
    ),
    3: (
        "Printer",
        {1: "Printer", 2: "Scanner", 3: "Fax", 4: "Copier", 5: "All-in-one"},
    ),
    4: (
        "Camera",
        {1: "Digital Still Camera", 2: "Video Camera", 3: "Web Camera", 4: "Security Camera"},
    ),
    5: ("Storage", {1: "NAS"}),
    6: (
        "Network Infrastructure",
        {1: "Access Point", 2: "Router", 3: "Switch", 4: "Gateway", 5: "Bridge"},
    ),
    7: (
        "Display",
        {1: "Television", 2: "Electronic Picture Frame", 3: "Projector", 4: "Monitor"},
    ),
    8: (
        "Multimedia Device",
        {
            1: "Digital Audio Recorder",
            2: "Personal Video Recorder",
            3: "Media Center Extender",
            4: "Set-top Box",
            5: "Media Server",
            6: "Portable Video Player",
        },
    ),
    9: (
        "Gaming Device",
        {1: "Xbox", 2: "Xbox 360", 3: "Playstation", 4: "Game Console", 5: "Portable Gaming Device"},
    ),
    10: (
        "Telephone",
        {
            1: "Windows Mobile",
            2: "Phone",
            3: "Dual Mode Phone",
            4: "Smartphone",
            5: "Dual Mode Smartphone",
        },
    ),
    11: (
        "Audio Device",
        {
            1: "Audio Tuner",
            2: "Speakers",
            3: "Portable Music Player",
            4: "Headset",
            5: "Headphones",
            6: "Microphone",
            7: "Home Theater System",
        },
    ),
    12: ("Docking Device", {1: "Computer Docking Station", 2: "Media Kiosk"}),
}


class AccessPointIdentity(BaseModel):
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model_name: Optional[str] = None
    model_number: Optional[str] = None
    device_category: Optional[str] = None
    device_subcategory: Optional[str] = None
    wps_available: bool = False
    wps_configured: Optional[bool] = None
    is_p2p_group: bool = False


def _text(raw: bytes) -> Optional[str]:
    return raw.decode("utf-8", errors="replace").replace("\x00", "").strip() or None


def _elements(blob: bytes) -> Iterator[Tuple[int, bytes]]:
    offset = 0
    while offset + 2 <= len(blob):
        element_id, length = blob[offset], blob[offset + 1]
        payload = blob[offset + 2 : offset + 2 + length]
        if len(payload) != length:
            return
        yield element_id, payload
        offset += 2 + length


def _wps_attributes(payload: bytes) -> Iterator[Tuple[int, bytes]]:
    offset = 0
    while offset + 4 <= len(payload):
        attribute = int.from_bytes(payload[offset : offset + 2], "big")
        length = int.from_bytes(payload[offset + 2 : offset + 4], "big")
        data = payload[offset + 4 : offset + 4 + length]
        if len(data) != length:
            return
        yield attribute, data
        offset += 4 + length


def _p2p_attributes(payload: bytes) -> Iterator[Tuple[int, bytes]]:
    offset = 0
    while offset + 3 <= len(payload):
        attribute = payload[offset]
        length = int.from_bytes(payload[offset + 1 : offset + 3], "little")
        data = payload[offset + 3 : offset + 3 + length]
        if len(data) != length:
            return
        yield attribute, data
        offset += 3 + length


def _device_type(raw: bytes) -> Tuple[Optional[str], Optional[str]]:
    if len(raw) < 8 or raw[2:6] != WPS_DEVICE_TYPE_OUI:
        return None, None
    device_type = DEVICE_TYPES.get(int.from_bytes(raw[0:2], "big"))
    if device_type is None:
        return None, None
    category, subcategories = device_type
    return category, subcategories.get(int.from_bytes(raw[6:8], "big"))


def _apply_wps(identity: AccessPointIdentity, payload: bytes) -> None:
    identity.wps_available = True
    for attribute, data in _wps_attributes(payload):
        if attribute == WPS_DEVICE_NAME:
            identity.device_name = _text(data)
        elif attribute == WPS_MANUFACTURER:
            identity.manufacturer = _text(data)
        elif attribute == WPS_MODEL_NAME:
            identity.model_name = _text(data)
        elif attribute == WPS_MODEL_NUMBER:
            identity.model_number = _text(data)
        elif attribute == WPS_SETUP_STATE and data:
            identity.wps_configured = data[0] == WPS_SETUP_STATE_CONFIGURED
        elif attribute == WPS_PRIMARY_DEVICE_TYPE:
            _set_device_type(identity, data)


def _apply_p2p(identity: AccessPointIdentity, payload: bytes) -> None:
    for attribute, data in _p2p_attributes(payload):
        if attribute == P2P_CAPABILITY and len(data) >= 2:
            identity.is_p2p_group = bool(data[1] & P2P_GROUP_OWNER_BIT)
        elif attribute == P2P_DEVICE_INFO:
            _apply_p2p_device_info(identity, data)


def _apply_p2p_device_info(identity: AccessPointIdentity, data: bytes) -> None:
    # Device address, config methods, primary device type and the secondary device type count
    if len(data) < 17:
        return
    if identity.device_category is None:
        _set_device_type(identity, data[8:16])
    for attribute, value in _wps_attributes(data[17 + data[16] * 8 :]):
        if attribute == WPS_DEVICE_NAME and identity.device_name is None:
            identity.device_name = _text(value)


def _set_device_type(identity: AccessPointIdentity, raw: bytes) -> None:
    category, subcategory = _device_type(raw)
    if category is None:
        return
    identity.device_category = category
    identity.device_subcategory = subcategory


def parse_information_elements(blob: bytes) -> AccessPointIdentity:
    # An element carries at most 255 bytes, so wpa_supplicant splits the bigger vendor payloads
    # over several elements sharing the same OUI and type, to be read back as a single one
    payloads: Dict[Tuple[bytes, int], bytes] = {}
    for element_id, payload in _elements(bytes(blob)):
        if element_id != VENDOR_SPECIFIC_ELEMENT_ID or len(payload) < 4:
            continue
        key = (payload[0:3], payload[3])
        payloads[key] = payloads.get(key, b"") + payload[4:]

    identity = AccessPointIdentity()
    wps_payload = payloads.get((WPS_OUI, WPS_OUI_TYPE))
    if wps_payload is not None:
        _apply_wps(identity, wps_payload)
    p2p_payload = payloads.get((P2P_OUI, P2P_OUI_TYPE))
    if p2p_payload is not None:
        _apply_p2p(identity, p2p_payload)
    return identity
