import asyncio
import functools
import re
import struct
import time
from pathlib import Path
from typing import Any, List, NamedTuple, Tuple

from commonwealth.utils.commands import run_command
from loguru import logger
from typedefs import Country, RfkillStatus

WORLD_CODE = "00"
COUNTRY_CODE_PATTERN = r"[A-Z0-9]{2}"
_6GHZ_BAND_START_KHZ = 5925000
_FAILED_READ_RETRY_S = 60
RFKILL_PATH = Path("/sys/class/rfkill")


class CountryDatabaseError(Exception):
    pass


class _Header(NamedTuple):
    magic: bytes
    version: int


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


_HEADER = struct.Struct(">4sI")
_COUNTRY = struct.Struct(">2sH")
_COLLECTION = struct.Struct(">BBB")
_RULE = struct.Struct(">BBHIII")
_DATABASE_MAGIC = b"RGDB"
_DATABASE_VERSION = 20


def _wlan_devices() -> List[Path]:
    devices = []
    for device in RFKILL_PATH.glob("rfkill*"):
        try:
            if (device / "type").read_text().strip() == "wlan":
                devices.append(device)
        except OSError:
            # Hotplugged away between the glob and the read
            continue
    return devices


def _read_flag(device: Path, attribute: str) -> bool:
    try:
        return (device / attribute).read_text().strip() == "1"
    except OSError:
        return False


def _rfkill_status() -> RfkillStatus:
    devices = _wlan_devices()
    return RfkillStatus(
        soft_blocked=any(_read_flag(device, "soft") for device in devices),
        hard_blocked=any(_read_flag(device, "hard") for device in devices),
    )


def _rfkill_unblock() -> None:
    for device in _wlan_devices():
        try:
            (device / "soft").write_text("0")
        except OSError as error:
            logger.warning(f"Could not unblock {device.name}: {error}")


async def rfkill_status() -> RfkillStatus:
    # The core container is privileged and binds /sys, so the kernel state is read directly instead of going
    # through a host command
    return await asyncio.to_thread(_rfkill_status)


async def rfkill_unblock() -> None:
    await asyncio.to_thread(_rfkill_unblock)


async def current_country() -> str:
    # The regulatory domain is global to the kernel, so it can be read from inside the container
    try:
        process = await asyncio.create_subprocess_exec(
            "iw", "reg", "get", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
    except OSError as error:
        logger.warning(f"Could not run iw to read the regulatory country, assuming the world domain: {error}")
        return WORLD_CODE
    stdout, _ = await process.communicate()
    if process.returncode != 0:
        logger.warning(f"iw reg get failed with {process.returncode}, assuming the world domain")
        return WORLD_CODE
    # Hosts with self-managed radios print per-phy blocks after the global one
    global_block = re.split(r"^phy#", stdout.decode(), maxsplit=1, flags=re.MULTILINE)[0]
    match = re.search(rf"^country ({COUNTRY_CODE_PATTERN}):", global_block, re.MULTILINE)
    return match.group(1) if match else WORLD_CODE


def check_country_format(code: str) -> None:
    # A cheap shape check, so a malformed string never reaches the wpa_supplicant control socket
    if not re.fullmatch(COUNTRY_CODE_PATTERN, code):
        raise ValueError(f"Invalid regulatory country: {code!r}")


async def set_country(code: str) -> None:
    check_country_format(code)
    try:
        process = await asyncio.create_subprocess_exec(
            "iw", "reg", "set", code, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
    except OSError as error:
        raise RuntimeError(f"Could not run iw to set the regulatory country {code}: {error}") from error
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"Could not set the regulatory country {code}: {stderr.decode().strip()}")


_supported_countries: List[Country] = []
# A host without a usable regulatory database would otherwise run its commands again on every dialog open
_failed_read: dict[str, Any] = {"countries": [], "retry_at": 0.0}


def _reset_cache_for_tests() -> None:
    _supported_countries.clear()
    _failed_read["retry_at"] = 0.0
    _supported_countries_lock.cache_clear()


@functools.cache
def _supported_countries_lock() -> asyncio.Lock:
    # Created on first use, so it binds to the running loop and not to whichever one exists at import
    return asyncio.Lock()


async def supported_countries() -> List[Country]:
    # The database is read-only, so it is only parsed once, unless it could not be fully read
    async with _supported_countries_lock():
        if _supported_countries:
            return list(_supported_countries)
        if time.monotonic() < _failed_read["retry_at"]:
            return list(_failed_read["countries"])
        countries, complete = await _read_supported_countries()
        if complete:
            _supported_countries[:] = countries
        else:
            _failed_read.update(countries=countries, retry_at=time.monotonic() + _FAILED_READ_RETRY_S)
        return countries


async def check_supported(code: str) -> None:
    countries = await supported_countries()
    if not countries:
        raise CountryDatabaseError("Could not read the countries.")
    if code not in {country.code for country in countries}:
        raise ValueError(f"Country '{code}' is not supported.")


def _parse_regulatory_db(data: bytes) -> dict[str, int]:
    header = _Header._make(_HEADER.unpack_from(data, 0))
    if header.magic != _DATABASE_MAGIC or header.version != _DATABASE_VERSION:
        raise ValueError(f"Unsupported regulatory database {header.magic!r} version {header.version}")
    countries = {}
    for offset in range(_HEADER.size, len(data), _COUNTRY.size):
        country = _Country._make(_COUNTRY.unpack_from(data, offset))
        if country.alpha2 == b"\x00\x00":
            break
        collection_offset = country.collection_pointer * 4
        collection = _Collection._make(_COLLECTION.unpack_from(data, collection_offset))
        # The rule pointers follow the collection, aligned to 2 bytes, as ALIGN(coll->len, 2) in the kernel's
        # net/wireless/reg.c
        rules_offset = collection_offset + (collection.length + 1) // 2 * 2
        rule_pointers = struct.unpack_from(f">{collection.rule_count}H", data, rules_offset)
        rules = [_Rule._make(_RULE.unpack_from(data, pointer * 4)) for pointer in rule_pointers]
        # Keep only 2.4 and 5 GHz rules: 6 and 60 GHz would skew max_power upward on radios that cannot use them
        powers = [rule.max_eirp_mbm for rule in rules if rule.start_khz < _6GHZ_BAND_START_KHZ]
        countries[country.alpha2.decode()] = max(powers, default=0) // 100
    return countries


async def _read_supported_countries() -> Tuple[List[Country], bool]:
    # regulatory.db is the database the kernel validates the country against. Its layout is the fwdb_* structs
    # of the kernel's net/wireless/reg.c: a header, then countries ended by an all-zero one, with every pointer
    # in units of 4 bytes. /lib/firmware is not bind-mounted into the core container (see bootstrap/startup.json.default),
    # so the binary file is read from the host, dumped as hex.
    database = await asyncio.to_thread(
        run_command, "od -An -v -tx1 /lib/firmware/regulatory.db", check=False, log_output=False
    )
    try:
        countries = _parse_regulatory_db(bytes.fromhex(database.stdout))
    except (struct.error, ValueError) as error:
        logger.warning(f"Could not read the regulatory database, no country can be selected: {error}")
        return [], False

    table = await asyncio.to_thread(run_command, "cat /usr/share/zoneinfo/iso3166.tab", check=False, log_output=False)
    complete = table.returncode == 0
    if not complete:
        logger.warning(f"Could not read the country names, falling back to the codes: {table.stderr}")
    names = dict(
        line.split("\t", 1) for line in table.stdout.splitlines() if complete and line and not line.startswith("#")
    )
    found = [
        Country(code=code, name="World" if code == WORLD_CODE else names.get(code, code), max_power_dbm=power)
        for code, power in countries.items()
    ]
    return sorted(found, key=lambda country: (country.code != WORLD_CODE, country.name)), complete
