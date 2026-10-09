import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import radio

pytestmark = pytest.mark.asyncio


def _completed(stdout: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.CompletedProcess(args="", returncode=0, stdout=stdout, stderr="")


def _fake_host(monkeypatch: pytest.MonkeyPatch, outputs: dict[str, str]) -> None:
    def fake_run_command(command: str, *_args: Any) -> "subprocess.CompletedProcess[str]":
        return _completed(outputs[command])

    monkeypatch.setattr(radio, "run_command", fake_run_command)


@pytest.mark.parametrize("key", ["", "rfkilldevices"])
async def test_rfkill_status_reads_both_json_layouts(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    output = f'{{"{key}": [{{"type": "wlan", "soft": "blocked", "hard": "unblocked"}}]}}'
    _fake_host(monkeypatch, {"sudo rfkill --json --output TYPE,SOFT,HARD list wifi": output})

    status = await radio.rfkill_status()

    assert status.soft_blocked is True
    assert status.hard_blocked is False


async def test_current_country_defaults_to_world(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_host(monkeypatch, {"sudo iw reg get": "global\ncountry BR: DFS-UNSET\n"})
    assert await radio.current_country() == "BR"

    _fake_host(monkeypatch, {"sudo iw reg get": ""})
    assert await radio.current_country() == "00"


@pytest.fixture(autouse=True)
def clear_supported_countries() -> None:
    radio._supported_countries.clear()


async def test_supported_countries_come_from_the_regulatory_database(monkeypatch: pytest.MonkeyPatch) -> None:
    header = b"RGDB" + (20).to_bytes(4, "big")
    countries = b"00" + (5).to_bytes(2, "big") + b"BR" + (5).to_bytes(2, "big") + bytes(4)
    collection = bytes([3, 2, 1, 0]) + (7).to_bytes(2, "big") + (11).to_bytes(2, "big")
    rule_20_dbm = bytes([14, 0]) + (2000).to_bytes(2, "big") + bytes(12)
    rule_30_dbm = bytes([14, 0]) + (3000).to_bytes(2, "big") + bytes(12)
    data = header + countries + collection + rule_20_dbm + rule_30_dbm
    _fake_host(
        monkeypatch,
        {
            "od -An -v -tx1 /lib/firmware/regulatory.db": data.hex(" "),
            "cat /usr/share/zoneinfo/iso3166.tab": "# comment\nBR\tBrazil\n",
        },
    )

    countries_found = await radio.supported_countries()

    assert [(country.code, country.name, country.max_power_dbm) for country in countries_found] == [
        ("00", "World", 30),
        ("BR", "Brazil", 30),
    ]


async def test_set_country_rejects_anything_but_a_country_code() -> None:
    with pytest.raises(ValueError):
        await radio.set_country("US;id")


async def test_concurrent_first_calls_read_the_database_once(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"RGDB" + (20).to_bytes(4, "big") + b"00" + (4).to_bytes(2, "big") + bytes(4)
    data += bytes([3, 1, 1, 0]) + (6).to_bytes(2, "big") + bytes(2)
    data += bytes([14, 0]) + (2000).to_bytes(2, "big") + bytes(12)
    _fake_host(
        monkeypatch,
        {"od -An -v -tx1 /lib/firmware/regulatory.db": data.hex(" "), "cat /usr/share/zoneinfo/iso3166.tab": ""},
    )

    reads: list[str] = []
    fake_run_command = radio.run_command  # type: ignore[attr-defined]

    def counting_run_command(command: str, *args: Any) -> "subprocess.CompletedProcess[str]":
        reads.append(command)
        completed: "subprocess.CompletedProcess[str]" = fake_run_command(command, *args)
        return completed

    monkeypatch.setattr(radio, "run_command", counting_run_command)

    first, second = await asyncio.gather(radio.supported_countries(), radio.supported_countries())

    assert [country.code for country in first] == [country.code for country in second] == ["00"]
    assert len(reads) == 2
