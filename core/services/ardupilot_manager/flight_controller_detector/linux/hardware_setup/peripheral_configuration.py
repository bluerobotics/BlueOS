import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional

all_dtparams = [
    "i2c_vc=on",
    "i2c_arm_baudrate=1000000",
    "spi=on",
    "enable_uart=1",
]


other_overlays = [
    "dwc2 dr_mode=otg",
]
devices = {
    "ADS1115": (0x48, 1),
    "AK09915": (0x0C, 1),
    "BME280": (0x76, 1),
    "PCA9685": (0x40, 4),
}


class SetupError(Exception):
    pass


@dataclass
class I2cDevice:
    device: str
    overlay: str
    pins: dict[int, str]


@dataclass
class SpiDevice:
    device: str
    overlay: str
    pins: dict[int, str]


@dataclass
class SerialDevice:
    device: str
    overlay: str
    pins: dict[int, str]


@dataclass
class GpioSetup:
    number: int
    function: str
    pull: str
    value: str


i2c_module = "i2c-dev"
i2c_dtparams = [
    "i2c_vc=on",
    "i2c_arm_baudrate=1000000",
]

i2c_devices: List[I2cDevice] = [
    I2cDevice(device="i2c-6", overlay="i2c6 pins_22_23=true baudrate=400000", pins={22: "SDA6", 23: "SCL6"}),
    I2cDevice(device="i2c-1", overlay="i2c1", pins={2: "SDA1", 3: "SCL1"}),
    I2cDevice(device="i2c-4", overlay="i2c4 pins_6_7=true baudrate=400000", pins={6: "SDA4", 7: "SCL4"}),
]

spi_devices: List[SpiDevice] = [
    SpiDevice(device="spidev1.0", overlay="spi1-3cs", pins={19: "SPI1_MISO", 20: "SPI1_MOSI", 21: "SPI1_SCLK"}),
    SpiDevice(
        device="spidev0.0",
        overlay="spi0-led",
        pins={
            10: "SPI0_MOSI",
        },
    ),
]

gpios = [
    GpioSetup(number=11, function="OUT", pull="UP", value="HIGH"),
    GpioSetup(number=24, function="OUT", pull="UP", value="HIGH"),
    GpioSetup(number=25, function="OUT", pull="UP", value="HIGH"),
    GpioSetup(number=37, function="OUT", pull="DOWN", value="LOW"),
]


def enable_i2c_module() -> None:
    modules = subprocess.check_output("lsmod")
    if "i2c_dev" in str(modules):
        return
    print(f"loading module {i2c_module}...")
    output = subprocess.check_output(shlex.split(f"modprobe {i2c_module}"))
    print(output)


def enable_spi_module() -> None:
    modules = subprocess.check_output("lsmod")
    if "spi_dev" in str(modules):
        return
    print(f"loading module {i2c_module}...")
    output = subprocess.check_output(shlex.split(f"modprobe {i2c_module}"))
    print(output)


@dataclass
class GpioState:
    number: int
    level: int
    fsel: int
    alt: Optional[int]
    func: str
    pull: str


def get_gpios_state() -> dict[int, GpioState]:
    output = subprocess.check_output(["raspi-gpio", "get"]).decode("utf-8")
    pattern = r"GPIO (?P<gpio>\d+): level=(?P<level>\d) fsel=(?P<fsel>\d)(?: alt=(?P<alt>\d))? func=(?P<func>[\w\d_]+) pull=(?P<pull>\w+)"

    # Using findall to extract all matches
    matches = re.finditer(pattern, output)
    gpio_states = {}
    # Print each match
    for match in matches:
        gpio_states[int(match.group("gpio"))] = GpioState(
            number=int(match.group("gpio")),
            level=int(match.group("level")),
            fsel=int(match.group("fsel")),
            alt=int(match.group("alt")) if match.group("alt") else None,
            func=match.group("func"),
            pull=match.group("pull"),
        )
    return gpio_states


def load_overlay(overlay: str) -> None:
    output = subprocess.check_output(shlex.split(f"dtoverlay {overlay}")).decode("utf-8")
    print(output)


enable_i2c_module()
enable_spi_module()

states = get_gpios_state()
all_devices: List[I2cDevice | SpiDevice] = [*i2c_devices, *spi_devices]
for device in all_devices:
    needs_reload = False
    for gpio, function in device.pins.items():
        if states[gpio].func != function:
            print(f"GPIO {gpio} is not configured as {function}, instad it is {states[gpio].func}")
            print(f"{device.overlay} needs to be loaded")
            needs_reload = True
    if needs_reload:
        load_overlay(device.overlay)
        time.sleep(2)
        new_state = get_gpios_state()
        for gpio, function in device.pins.items():
            if states[gpio].func != function:
                print(f"GPIO {gpio} is STILL not configured as {function}, instad it is {states[gpio].func}")
                raise SetupError("Failed to configure device")
