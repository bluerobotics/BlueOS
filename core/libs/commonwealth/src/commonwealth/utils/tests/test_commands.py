import subprocess
from unittest.mock import mock_open, patch

import pytest

from .. import commands


def _result(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_load_file_returns_contents_when_cat_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "run_command", lambda *_args, **_kwargs: _result(0, stdout="dtoverlay=spi0-led\n"))
    assert commands.load_file("/boot/config.txt") == "dtoverlay=spi0-led\n"


def test_load_file_returns_empty_string_for_empty_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "run_command", lambda *_args, **_kwargs: _result(0, stdout=""))
    assert commands.load_file("/boot/config.txt") == ""


def test_load_file_raises_when_cat_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        commands, "run_command", lambda *_args, **_kwargs: _result(1, stdout="", stderr="cat: No such file")
    )
    with pytest.raises(commands.HostFileError, match="Failed to read /boot/config.txt"):
        commands.load_file("/boot/config.txt")


def test_locate_file_returns_first_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        commands, "run_command", lambda *_args, **_kwargs: _result(0, stdout="/boot/firmware/config.txt\n")
    )
    assert commands.locate_file(["/boot/firmware/config.txt", "/boot/config.txt"]) == "/boot/firmware/config.txt"


def test_locate_file_returns_none_when_find_prints_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "run_command", lambda *_args, **_kwargs: _result(1, stdout="", stderr="No such file"))
    assert commands.locate_file(["/missing/a", "/missing/b"]) is None


def test_locate_file_returns_match_when_find_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        commands,
        "run_command",
        lambda *_args, **_kwargs: _result(1, stdout="/boot/config.txt\n", stderr="No such file"),
    )
    assert commands.locate_file(["/boot/firmware/config.txt", "/boot/config.txt"]) == "/boot/config.txt"


def test_save_file_raises_when_upload_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "run_command", lambda *_args, **_kwargs: _result(0))
    monkeypatch.setattr(commands, "upload_file", lambda *_args, **_kwargs: _result(1, stderr="Permission denied"))
    with pytest.raises(commands.HostFileError, match="Failed to save /boot/config.txt"):
        commands.save_file("/boot/config.txt", "[pi4]\n", "before_test")


def test_save_file_succeeds_when_upload_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "run_command", lambda *_args, **_kwargs: _result(0))
    monkeypatch.setattr(commands, "upload_file", lambda *_args, **_kwargs: _result(0))
    commands.save_file("/boot/config.txt", "[pi4]\n", "before_test")


def test_upload_file_returns_mv_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "upload_file_with_ssh_key", lambda *_args, **_kwargs: _result(0))
    monkeypatch.setattr(commands, "run_command", lambda *_args, **_kwargs: _result(1, stderr="Read-only file system"))
    with patch("builtins.open", mock_open()):
        result = commands.upload_file("[pi4]\n", "/boot/config.txt", False)
    assert result.returncode == 1
    assert "Read-only file system" in result.stderr
