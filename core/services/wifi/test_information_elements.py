import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wifi_handlers.information_elements import parse_information_elements


def _element(element_id: int, payload: bytes) -> bytes:
    return bytes([element_id, len(payload)]) + payload


def _wps_attribute(attribute: int, data: bytes) -> bytes:
    return attribute.to_bytes(2, "big") + len(data).to_bytes(2, "big") + data


def _p2p_attribute(attribute: int, data: bytes) -> bytes:
    return bytes([attribute]) + len(data).to_bytes(2, "little") + data


def _vendor_element(oui: bytes, oui_type: int, payload: bytes) -> bytes:
    return _element(0xDD, oui + bytes([oui_type]) + payload)


def _wps_element(payload: bytes) -> bytes:
    return _vendor_element(b"\x00\x50\xf2", 0x04, payload)


def _p2p_element(payload: bytes) -> bytes:
    return _vendor_element(b"\x50\x6f\x9a", 0x09, payload)


TELEVISION_DEVICE_TYPE = (7).to_bytes(2, "big") + b"\x00\x50\xf2\x04" + (1).to_bytes(2, "big")

ROKU_WPS = _wps_element(
    _wps_attribute(0x1044, b"\x02")
    + _wps_attribute(0x1011, '43" AOC Roku TV'.encode("utf-8"))
    + _wps_attribute(0x1021, b"Roku")
    + _wps_attribute(0x1023, b"Roku Streaming Player")
    + _wps_attribute(0x1024, b"C000X")
    + _wps_attribute(0x1042, b"X0123456789")
    + _wps_attribute(0x1054, TELEVISION_DEVICE_TYPE)
)


def test_parses_a_roku_like_beacon() -> None:
    identity = parse_information_elements(_element(0x00, b"") + ROKU_WPS)

    assert identity.device_name == '43" AOC Roku TV'
    assert identity.manufacturer == "Roku"
    assert identity.model_name == "Roku Streaming Player"
    assert identity.model_number == "C000X"
    assert identity.device_category == "Display"
    assert identity.device_subcategory == "Television"
    assert identity.wps_available is True
    assert identity.wps_configured is True
    assert identity.is_p2p_group is False


def test_reports_a_p2p_group_owner() -> None:
    identity = parse_information_elements(ROKU_WPS + _p2p_element(_p2p_attribute(0x02, b"\x25\x2d")))

    assert identity.is_p2p_group is True


def test_ignores_a_p2p_client() -> None:
    identity = parse_information_elements(_p2p_element(_p2p_attribute(0x02, b"\x25\x2c")))

    assert identity.is_p2p_group is False


def test_falls_back_to_the_p2p_device_info() -> None:
    device_info = (
        b"\xaa\xbb\xcc\xdd\xee\xff"
        + b"\x00\x88"
        + TELEVISION_DEVICE_TYPE
        + b"\x00"
        + _wps_attribute(0x1011, b"Roku Express")
    )
    identity = parse_information_elements(_p2p_element(_p2p_attribute(0x0D, device_info)))

    assert identity.device_name == "Roku Express"
    assert identity.device_category == "Display"
    assert identity.device_subcategory == "Television"
    assert identity.wps_available is False


def test_keeps_the_wps_name_over_the_p2p_one() -> None:
    device_info = (
        b"\xaa\xbb\xcc\xdd\xee\xff\x00\x88" + TELEVISION_DEVICE_TYPE + b"\x00" + _wps_attribute(0x1011, b"P2P")
    )
    identity = parse_information_elements(ROKU_WPS + _p2p_element(_p2p_attribute(0x0D, device_info)))

    assert identity.device_name == '43" AOC Roku TV'


def test_skips_unknown_vendor_elements() -> None:
    identity = parse_information_elements(_vendor_element(b"\x00\x11\x22", 0x01, b"anything") + ROKU_WPS)

    assert identity.device_name == '43" AOC Roku TV'


def test_ignores_device_types_from_other_ouis() -> None:
    vendor_device_type = (7).to_bytes(2, "big") + b"\x00\x11\x22\x33" + (1).to_bytes(2, "big")
    identity = parse_information_elements(_wps_element(_wps_attribute(0x1054, vendor_device_type)))

    assert identity.device_category is None
    assert identity.device_subcategory is None
    assert identity.wps_available is True


def test_reports_an_unnamed_subcategory() -> None:
    device_type = (7).to_bytes(2, "big") + b"\x00\x50\xf2\x04" + (99).to_bytes(2, "big")
    identity = parse_information_elements(_wps_element(_wps_attribute(0x1054, device_type)))

    assert identity.device_category == "Display"
    assert identity.device_subcategory is None


def test_reports_an_unconfigured_access_point() -> None:
    identity = parse_information_elements(_wps_element(_wps_attribute(0x1044, b"\x01")))

    assert identity.wps_available is True
    assert identity.wps_configured is False


def test_sanitizes_the_decoded_strings() -> None:
    identity = parse_information_elements(_wps_element(_wps_attribute(0x1011, b" Roku\x00\xff TV\x00")))

    assert identity.device_name == "Roku\ufffd TV"


def test_discards_empty_strings() -> None:
    identity = parse_information_elements(_wps_element(_wps_attribute(0x1011, b"\x00\x00")))

    assert identity.device_name is None


def test_survives_malformed_input() -> None:
    malformed = [
        b"",
        b"\xdd",
        b"\xdd\xff\x00\x50\xf2\x04",
        _element(0xDD, b"\x00\x50"),
        _wps_element(b"\x10\x11\x00"),
        _wps_element(b"\x10\x11\xff\xff" + b"short"),
        _p2p_element(b"\x0d\xff"),
        _p2p_element(_p2p_attribute(0x0D, b"\xaa\xbb")),
        _p2p_element(_p2p_attribute(0x02, b"\x25")),
        bytes(range(256)),
    ]

    for blob in malformed:
        assert parse_information_elements(blob) is not None
