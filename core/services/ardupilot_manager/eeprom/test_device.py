import struct
from pathlib import Path

import pytest
from eeprom.device import EEPROM

EEPROM_SIZE = 4096
HAT_SIZE = 96


def create_eeprom(path: Path, hat_size: int | None = None) -> EEPROM:
    data = bytearray(b"\xff" * EEPROM_SIZE)
    if hat_size is not None:
        data[: EEPROM.HAT_HEADER.size] = EEPROM.HAT_HEADER.pack(EEPROM.HAT_ID_MAGIC, 1, 0, 2, hat_size)
    path.write_bytes(data)
    return EEPROM(str(path))


def test_blank_eeprom_has_no_hat_id(tmp_path: Path) -> None:
    eeprom = create_eeprom(tmp_path / "eeprom")
    assert not eeprom.has_hat_id()
    assert eeprom.hat_id_partition_size() == 0


def test_hat_id_partition_size_is_read_from_header(tmp_path: Path) -> None:
    eeprom = create_eeprom(tmp_path / "eeprom", HAT_SIZE)
    assert eeprom.has_hat_id()
    assert eeprom.hat_id_partition_size() == HAT_SIZE


@pytest.mark.parametrize("hat_size", [0, EEPROM.HAT_HEADER.size - 1, EEPROM_SIZE + 1])
def test_invalid_hat_size_protects_the_whole_eeprom(tmp_path: Path, hat_size: int) -> None:
    eeprom = create_eeprom(tmp_path / "eeprom", hat_size)
    assert eeprom.hat_id_partition_size() == EEPROM_SIZE


def test_read_and_write(tmp_path: Path) -> None:
    eeprom = create_eeprom(tmp_path / "eeprom")
    eeprom.write(100, b"abc")
    assert eeprom.read(99, 5) == b"\xffabc\xff"
    assert eeprom.size() == EEPROM_SIZE


def test_write_after_hat_id_partition(tmp_path: Path) -> None:
    eeprom = create_eeprom(tmp_path / "eeprom", HAT_SIZE)
    eeprom.write(HAT_SIZE, b"abc")
    assert eeprom.read(HAT_SIZE, 3) == b"abc"


def test_write_cannot_touch_hat_id_partition(tmp_path: Path) -> None:
    eeprom = create_eeprom(tmp_path / "eeprom", HAT_SIZE)
    original = eeprom.read(0, EEPROM_SIZE)
    with pytest.raises(ValueError):
        eeprom.write(HAT_SIZE - 1, b"abc")
    assert eeprom.read(0, EEPROM_SIZE) == original


def test_write_cannot_exceed_eeprom_size(tmp_path: Path) -> None:
    eeprom = create_eeprom(tmp_path / "eeprom")
    with pytest.raises(ValueError):
        eeprom.write(EEPROM_SIZE - 2, b"abc")


def test_read_works_on_read_only_file(tmp_path: Path) -> None:
    eeprom = create_eeprom(tmp_path / "eeprom", HAT_SIZE)
    (tmp_path / "eeprom").chmod(0o444)
    assert eeprom.read(0, 4) == struct.pack("4s", EEPROM.HAT_ID_MAGIC)
