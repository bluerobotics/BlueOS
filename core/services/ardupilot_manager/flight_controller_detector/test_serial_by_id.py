from pathlib import Path

import pytest
from flight_controller_detector.serial_by_id import SerialById


@pytest.fixture(name="by_id")
def fixture_by_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "by-id"
    directory.mkdir()
    monkeypatch.setattr(SerialById, "BY_ID_DIR", directory)
    return directory


def link_to(by_id: Path, node: Path, name: str = "usb-ArduPilot_Pixhawk1_123-if00") -> Path:
    link = by_id / name
    link.unlink(missing_ok=True)
    link.symlink_to(node)
    return link


def test_link_is_the_one_pointing_to_the_device(by_id: Path, tmp_path: Path) -> None:
    ours, other = tmp_path / "ttyACM0", tmp_path / "ttyACM1"
    ours.touch()
    other.touch()
    link_to(by_id, other, "usb-Other-if00")
    link = link_to(by_id, ours)

    assert SerialById(str(ours)).link == str(link)


@pytest.mark.usefixtures("by_id")
def test_link_is_none_without_a_link_and_so_is_the_current_path(tmp_path: Path) -> None:
    serial = SerialById(str(tmp_path / "ttyACM0"))

    assert serial.link is None
    assert serial.current_path() is None


def test_link_is_looked_up_once(by_id: Path, tmp_path: Path) -> None:
    first, second = tmp_path / "ttyACM0", tmp_path / "ttyACM1"
    first.touch()
    second.touch()
    link = link_to(by_id, first)
    serial = SerialById(str(first))

    link.unlink()
    assert serial.link == str(link)
    assert SerialById(str(second)).link is None


def test_current_path_follows_the_link(by_id: Path, tmp_path: Path) -> None:
    old, new = tmp_path / "ttyACM0", tmp_path / "ttyACM1"
    old.touch()
    new.touch()
    link = link_to(by_id, old)
    serial = SerialById(str(old))
    assert serial.current_path() == str(old)

    old.unlink()
    link_to(by_id, new)
    assert serial.current_path() == str(new)

    link.unlink()
    assert serial.current_path() is None


def test_current_path_is_none_when_the_node_is_gone(by_id: Path, tmp_path: Path) -> None:
    node = tmp_path / "ttyACM0"
    node.touch()
    link_to(by_id, node)
    serial = SerialById(str(node))

    node.unlink()
    assert serial.current_path() is None
