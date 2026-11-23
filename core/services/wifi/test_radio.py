import asyncio
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import radio
from loguru import logger

pytestmark = pytest.mark.asyncio


def _add_device(root: Path, name: str, kind: str, soft: str, hard: str) -> Path:
    device = root / name
    device.mkdir()
    for attribute, value in {"type": kind, "soft": soft, "hard": hard}.items():
        (device / attribute).write_text(f"{value}\n")
    return device


async def test_rfkill_status_only_reads_wifi_devices(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _add_device(tmp_path, "rfkill0", "bluetooth", "0", "1")
    _add_device(tmp_path, "rfkill1", "wlan", "1", "0")
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path)

    status = await radio.rfkill_status()

    assert status.soft_blocked is True
    assert status.hard_blocked is False


async def test_rfkill_status_skips_a_device_that_vanishes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _add_device(tmp_path, "rfkill0", "wlan", "1", "0")
    (tmp_path / "rfkill1").mkdir()
    gone = _add_device(tmp_path, "rfkill2", "wlan", "0", "0")
    (gone / "soft").unlink()
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path)

    status = await radio.rfkill_status()

    assert status.soft_blocked is True
    assert status.hard_blocked is False


async def test_rfkill_status_without_radio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path / "missing")

    status = await radio.rfkill_status()

    assert (status.soft_blocked, status.hard_blocked) == (False, False)


async def test_rfkill_unblock_clears_only_the_wifi_soft_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bluetooth = _add_device(tmp_path, "rfkill0", "bluetooth", "1", "0")
    wifi = _add_device(tmp_path, "rfkill1", "wlan", "1", "0")
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path)

    await radio.rfkill_unblock()

    assert (wifi / "soft").read_text() == "0"
    assert (bluetooth / "soft").read_text().strip() == "1"


class _FakeProcess:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout.encode(), b"failed"


def _fake_iw(monkeypatch: pytest.MonkeyPatch, stdout: str, returncode: int = 0) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    async def fake_exec(*args: str, **_kwargs: Any) -> _FakeProcess:
        calls.append(args)
        return _FakeProcess(stdout, returncode)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return calls


def _completed(stdout: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.CompletedProcess(args="", returncode=0, stdout=stdout, stderr="")


def _database(*, magic: bytes = b"RGDB", version: int = 20, truncated: bool = False) -> bytes:
    header = magic + version.to_bytes(4, "big")
    countries = b"00" + (5).to_bytes(2, "big") + b"BR" + (5).to_bytes(2, "big") + bytes(4)
    collection = bytes([3, 2, 1, 0]) + (7).to_bytes(2, "big") + (11).to_bytes(2, "big")
    rule_20_dbm = bytes([14, 0]) + (2000).to_bytes(2, "big") + bytes(12)
    rule_30_dbm = bytes([14, 0]) + (3000).to_bytes(2, "big") + bytes(12)
    data = header + countries + collection + rule_20_dbm + rule_30_dbm
    return data[:20] if truncated else data


def _fake_host(
    monkeypatch: pytest.MonkeyPatch, database: bytes, names: str | None = "# comment\nBR\tBrazil\n"
) -> list[str]:
    reads: list[str] = []

    def fake_run_command(command: str, **_kwargs: Any) -> "subprocess.CompletedProcess[str]":
        reads.append(command)
        if "iso3166" in command:
            if names is None:
                return subprocess.CompletedProcess(args="", returncode=1, stdout="", stderr="missing")
            return _completed(names)
        return _completed(database.hex(" "))

    monkeypatch.setattr(radio, "run_command", fake_run_command)
    return reads


@pytest.fixture(autouse=True)
def clear_supported_countries() -> None:
    radio._reset_cache_for_tests()


async def test_current_country_defaults_to_world(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_iw(monkeypatch, "global\ncountry BR: DFS-UNSET\n")
    assert await radio.current_country() == "BR"

    _fake_iw(monkeypatch, "")
    assert await radio.current_country() == "00"


async def test_current_country_ignores_self_managed_phys_without_a_global_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_iw(monkeypatch, "phy#0 (self-managed)\ncountry US: DFS-FCC\n")
    assert await radio.current_country() == "00"


@pytest.mark.parametrize("failure", ["exec", "exit"])
async def test_a_broken_iw_is_logged_and_reads_as_the_world_domain(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    if failure == "exec":

        async def missing_iw(*_args: str, **_kwargs: Any) -> None:
            raise FileNotFoundError("iw")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", missing_iw)
    else:
        _fake_iw(monkeypatch, "global\ncountry BR: DFS-UNSET\n", returncode=1)
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="WARNING")
    try:
        assert await radio.current_country() == "00"
    finally:
        logger.remove(sink)

    assert any("iw" in message for message in messages)


async def test_current_country_is_the_global_one_on_multi_phy_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_iw(monkeypatch, "global\ncountry 00: DFS-UNSET\n\nphy#0 (self-managed)\ncountry US: DFS-FCC\n")
    assert await radio.current_country() == "00"


async def test_set_country_runs_iw_inside_the_container(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_iw(monkeypatch, "")
    await radio.set_country("BR")
    assert calls == [("iw", "reg", "set", "BR")]

    _fake_iw(monkeypatch, "", returncode=1)
    with pytest.raises(RuntimeError):
        await radio.set_country("BR")


async def test_set_country_without_iw_is_a_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def missing_iw(*_args: str, **_kwargs: Any) -> None:
        raise FileNotFoundError("iw")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", missing_iw)

    with pytest.raises(RuntimeError):
        await radio.set_country("BR")


async def test_set_country_rejects_anything_but_a_country_code() -> None:
    with pytest.raises(ValueError):
        await radio.set_country("US;id")


async def test_supported_countries_come_from_the_regulatory_database(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_host(monkeypatch, _database())

    countries_found = await radio.supported_countries()

    assert [(country.code, country.name, country.max_power_dbm) for country in countries_found] == [
        ("00", "World", 30),
        ("BR", "Brazil", 30),
    ]


@pytest.fixture(name="clock")
def fixture_clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [1000.0]
    monkeypatch.setattr(radio, "time", SimpleNamespace(monotonic=lambda: now[0]))
    return now


@pytest.mark.parametrize("database", [_database(truncated=True), _database(magic=b"XXXX"), _database(version=19), b""])
async def test_a_corrupt_database_gives_no_countries_and_is_retried_after_a_while(
    monkeypatch: pytest.MonkeyPatch, database: bytes, clock: list[float]
) -> None:
    reads = _fake_host(monkeypatch, database)

    assert await radio.supported_countries() == []
    assert await radio.supported_countries() == []
    assert len(reads) == 1

    clock[0] += radio._FAILED_READ_RETRY_S
    assert await radio.supported_countries() == []
    assert len(reads) == 2


async def test_unreadable_country_names_fall_back_to_codes_and_are_retried_after_a_while(
    monkeypatch: pytest.MonkeyPatch, clock: list[float]
) -> None:
    reads = _fake_host(monkeypatch, _database(), names=None)

    first = await radio.supported_countries()
    await radio.supported_countries()
    assert len(reads) == 2

    clock[0] += radio._FAILED_READ_RETRY_S
    await radio.supported_countries()

    assert [country.name for country in first] == ["World", "BR"]
    assert len(reads) == 4


async def test_the_country_names_are_not_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[dict[str, Any]] = []

    def fake_run_command(command: str, **kwargs: Any) -> "subprocess.CompletedProcess[str]":
        logged.append(kwargs)
        return _completed("BR\tBrazil\n" if "iso3166" in command else _database().hex(" "))

    monkeypatch.setattr(radio, "run_command", fake_run_command)

    await radio.supported_countries()

    assert logged and all(kwargs["log_output"] is False for kwargs in logged)


async def test_concurrent_first_calls_read_the_database_once(monkeypatch: pytest.MonkeyPatch) -> None:
    reads = _fake_host(monkeypatch, _database())

    first, second = await asyncio.gather(radio.supported_countries(), radio.supported_countries())

    assert [country.code for country in first] == [country.code for country in second] == ["00", "BR"]
    assert len(reads) == 2


async def test_selecting_a_country_outside_the_database_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_host(monkeypatch, _database())

    await radio.check_supported("BR")
    with pytest.raises(ValueError):
        await radio.check_supported("ZZ")


async def test_selecting_a_country_without_a_database_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_host(monkeypatch, b"")

    with pytest.raises(radio.CountryDatabaseError):
        await radio.check_supported("BR")
