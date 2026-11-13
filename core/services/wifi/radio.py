import asyncio
import re
import struct
from pathlib import Path
from typing import List, NamedTuple

from commonwealth.utils.commands import run_command
from loguru import logger
from typedefs import Country, RfkillStatus

WORLD_CODE = "00"
RFKILL_PATH = Path("/sys/class/rfkill")


class _Country(NamedTuple):
    alpha2: bytes
    collection_pointer: int


class _Collection(NamedTuple):
    length: int
    rule_count: int
    dfs_region: int


class _Rule(NamedTuple):
    length: int
    flags: int
    max_eirp_mbm: int
    start_khz: int
    end_khz: int
    max_bandwidth_khz: int


_HEADER_SIZE = 8
_COUNTRY = struct.Struct(">2sH")
_COLLECTION = struct.Struct(">BBB")
_RULE = struct.Struct(">BBHIII")


async def rfkill_status() -> RfkillStatus:
    # The frontend polls this, so it reads sysfs instead of running a command on the host
    devices = [device for device in RFKILL_PATH.glob("rfkill*") if (device / "type").read_text().strip() == "wlan"]
    return RfkillStatus(
        soft_blocked=any((device / "soft").read_text().strip() == "1" for device in devices),
        hard_blocked=any((device / "hard").read_text().strip() == "1" for device in devices),
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
    # regulatory.db is the database the kernel validates the country against. Its layout is the fwdb_* structs
    # of the kernel's net/wireless/reg.c: a header, then countries ended by an all-zero one, with every pointer
    # in units of 4 bytes.
    database = await asyncio.to_thread(run_command, "od -An -v -tx1 /lib/firmware/regulatory.db", False, False)
    data = bytes.fromhex(database.stdout)
    if not data:
        logger.warning("Could not read the regulatory database, no country can be selected.")
        return []
    countries = {}
    for offset in range(_HEADER_SIZE, len(data), _COUNTRY.size):
        country = _Country._make(_COUNTRY.unpack_from(data, offset))
        if country.alpha2 == b"\x00\x00":
            break
        collection_offset = country.collection_pointer * 4
        collection = _Collection._make(_COLLECTION.unpack_from(data, collection_offset))
        # The rule pointers follow the collection, aligned to 2 bytes
        rules_offset = collection_offset + (collection.length + 1) // 2 * 2
        rule_pointers = struct.unpack_from(f">{collection.rule_count}H", data, rules_offset)
        rules = [_Rule._make(_RULE.unpack_from(data, pointer * 4)) for pointer in rule_pointers]
        # Keep only 2.4 and 5 GHz rules: the radio can't use 6 and 60 GHz, which would skew the maximum power upward
        powers = [rule.max_eirp_mbm for rule in rules if rule.start_khz < 5925000]
        countries[country.alpha2.decode()] = max(powers, default=0) // 100

    table = await asyncio.to_thread(run_command, "cat /usr/share/zoneinfo/iso3166.tab", False, False)
    names = dict(line.split("\t", 1) for line in table.stdout.splitlines() if line and not line.startswith("#"))
    found = [
        Country(code=code, name="World" if code == WORLD_CODE else names.get(code, code), max_power_dbm=power)
        for code, power in countries.items()
    ]
    return sorted(found, key=lambda country: (country.code != WORLD_CODE, country.name))
