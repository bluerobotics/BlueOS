import asyncio
import json
import re
import struct
from typing import Any, List

from commonwealth.utils.commands import run_command
from loguru import logger
from typedefs import Country, RfkillStatus

WORLD_CODE = "00"


async def rfkill_status() -> RfkillStatus:
    output = await asyncio.to_thread(run_command, "sudo rfkill --json --output TYPE,SOFT,HARD list wifi", False, False)
    # util-linux names the top level list "" before 2.37 and "rfkilldevices" after
    devices: List[Any] = next(iter(json.loads(output.stdout or "{}").values()), [])
    return RfkillStatus(
        soft_blocked=any(device["soft"] == "blocked" for device in devices),
        hard_blocked=any(device["hard"] == "blocked" for device in devices),
    )


async def rfkill_unblock(check: bool = True) -> None:
    await asyncio.to_thread(run_command, "sudo rfkill unblock wifi", check)


async def current_country() -> str:
    output = await asyncio.to_thread(run_command, "sudo iw reg get", False, False)
    match = re.search(r"^country ([A-Z0-9]{2}):", output.stdout, re.MULTILINE)
    return match.group(1) if match else WORLD_CODE


def check_country(code: str) -> None:
    if not re.fullmatch(r"[A-Z0-9]{2}", code):
        raise ValueError(f"Invalid regulatory country: {code!r}")


async def set_country(code: str) -> None:
    check_country(code)
    await asyncio.to_thread(run_command, f"sudo iw reg set {code}")


_supported_countries: List[Country] = []
_supported_countries_lock = asyncio.Lock()


async def supported_countries() -> List[Country]:
    # The database is read-only, so it is only parsed once, unless it could not be read
    async with _supported_countries_lock:
        if not _supported_countries:
            _supported_countries[:] = await _read_supported_countries()
        return list(_supported_countries)


async def _read_supported_countries() -> List[Country]:
    # regulatory.db is the database the kernel validates the country against: an 8 byte header, then
    # 4 byte entries (alpha2, collection offset / 4) ended by an all-zero entry. A collection is
    # (length, rule count, dfs region, padding) followed by one 16 bit rule offset / 4 per rule, and a rule is
    # (length, flags, max EIRP in mBm, start in kHz, ...).
    database = await asyncio.to_thread(run_command, "od -An -v -tx1 /lib/firmware/regulatory.db", False, False)
    data = bytes.fromhex(database.stdout)
    if not data:
        logger.warning("Could not read the regulatory database, no country can be selected.")
        return []
    countries = {}
    for offset in range(8, len(data), 4):
        alpha2, collection_offset = struct.unpack(">2sH", data[offset : offset + 4])
        if alpha2 == b"\x00\x00":
            break
        collection = collection_offset * 4
        rules_start = collection + (data[collection] + 1) // 2 * 2
        rule_offsets = struct.unpack(
            f">{data[collection + 1]}H", data[rules_start : rules_start + 2 * data[collection + 1]]
        )
        # Only the 2.4 and 5 GHz rules: the radio has no 6 GHz and 60 GHz rules can have much higher power
        rules = [data[rule * 4 : rule * 4 + 8] for rule in rule_offsets]
        powers = [struct.unpack(">H", rule[2:4])[0] for rule in rules if struct.unpack(">I", rule[4:8])[0] < 5925000]
        countries[alpha2.decode()] = max(powers, default=0) // 100

    table = await asyncio.to_thread(run_command, "cat /usr/share/zoneinfo/iso3166.tab", False, False)
    names = dict(line.split("\t", 1) for line in table.stdout.splitlines() if line and not line.startswith("#"))
    found = [
        Country(code=code, name="World" if code == WORLD_CODE else names.get(code, code), max_power_dbm=power)
        for code, power in countries.items()
    ]
    return sorted(found, key=lambda country: (country.code != WORLD_CODE, country.name))
