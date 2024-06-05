from typing import List

from commonwealth.utils.commands import locate_file, run_command, save_file
from loguru import logger
from smbus2 import SMBus

from enum import Enum
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from flight_controller_detector.linux.overlay_loader import (
    DtParam,
    load_overlays_in_runtime,
)
from typedefs import Platform, Serial
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

class Navigator(LinuxFlightController):
    name = "Navigator"
    manufacturer = "Blue Robotics"
    platform = Platform.Navigator
    gpio_config = {}

    def is_pi5(self) -> bool:
        is_pi5 = False
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            if "Raspberry Pi 5" in f.read():
                is_pi5 = True
        return is_pi5

    def detect(self):
        return False

    def setup_board(self) -> None:
        load_overlays_in_runtime(self.all_dtparams, self.all_overlays, ["i2c_dev"])
        for gpio, config in self.gpio_config.items():
            self.setup_gpio(gpio, config["direction"], config["value"])

    def setup_gpio(self, pin, direction, value) -> None:
        GPIO.setup(pin, direction)
        GPIO.output(pin, value)

    def setup_board_for_detection(self) -> None:
        load_overlays_in_runtime(self.all_dtparams, self.i2c_overlays, ["i2c_dev"])

    def get_serials(self) -> List[Serial]:
        release = "Bullseye"
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            os_release = f.read()
            if "bookworm" in os_release:
                release = "Bookworm"

        match release:
            case "Bullseye":
                # port mapping available at https://ardupilot.org/dev/docs/sitl-serial-mapping.html
                return [
                    Serial(port="C", endpoint="/dev/ttyS0"),
                    Serial(port="B", endpoint="/dev/ttyAMA1"),
                    Serial(port="E", endpoint="/dev/ttyAMA2"),
                    Serial(port="F", endpoint="/dev/ttyAMA3"),
                ]
            case "Bookworm":
                # these have been validated for pi5 but need validation on Pi4,
                return [
                    Serial(port="C", endpoint="/dev/ttyAMA0"),
                    Serial(port="B", endpoint="/dev/ttyAMA2"),
                    Serial(port="E", endpoint="/dev/ttyAMA3"),
                    Serial(port="F", endpoint="/dev/ttyAMA4"),
                ]
        raise RuntimeError("Unknown release, unable to map ports")

    def build_led_overlay(self):
        temp_overlay_file_at_host = "/tmp/spi0-led.dts"
        target_overlay_location_pi4 = "/boot/overlays/spi0-led.dtbo"
        target_overlay_location_pi5 = "/boot/firmware/overlays/spi0-led.dtbo"
        overlay_exists = locate_file([target_overlay_location_pi4, target_overlay_location_pi5])
        if overlay_exists:
            logger.info(f"spi0-led overlay found at {overlay_exists}")
            return False
        with open(
            "/home/pi/services/ardupilot_manager/flight_controller_detector/linux/overlay_source/spi0-led.dts",
            "r",
            encoding="utf-8",
        ) as f:
            dts = f.read()
            save_file(temp_overlay_file_at_host, dts, "")
        command = f"sudo dtc -@ -Hepapr -I dts -O dtb -o {target_overlay_location_pi4} {temp_overlay_file_at_host}"
        logger.info(run_command(command, False))
        copy_command = (
            f"if [ -d /boot/firmware ]; then sudo cp {target_overlay_location_pi4} {target_overlay_location_pi5}; fi"
        )
        logger.info(run_command(copy_command, False))
        # we should be able to load the just-built overlay, no need to restart
        return False


class NavigatorPi5(Navigator):
    all_dtparams = [
        "i2c_arm=on",
        "i2c_arm_baudrate=1000000",
    ]
    # i2c overlays are required to detect the board
    i2c_overlays = [
        # i2c1: ADS1115, AK09915, BME280
        "i2c1-pi5 baudrate=400000",
        # i2c3: PCA
        "i2c3-pi5 baudrate=400000",
    ]
    all_overlays = [
        # serial ports, checked individually
        "uart0-pi5",  # Navigator serial1
        "uart3-pi5",  # Navigator serial4
        "uart4-pi5",  # Navigator serial5
        "uart2-pi5",  # Navigator serial3
        # i2c-6: bar30 and friends
        "i2c-gpio i2c_gpio_sda=22 i2c_gpio_scl=23 bus=6 i2c_gpio_delay_us=0",
        # i2c1: ADS1115, AK09915, BME280
        "i2c3-pi5 baudrate=400000",
        # i2c3: PCA
        "i2c3-pi5 baudrate=400000",
        # SPI1: MMC5983
        "spi1-3cs",
        # SPI0: LED
        "spi0-led",
    ]

    def detect(self):
        logger.info("Detecting Navigator on Pi5")
        if not self.is_pi5():
            return False
        logger.info("setting up hardware for detection")
        self.setup_board_for_detection()
        return all(self.check_for_i2c_device(bus, address) for address, bus in self.devices.values())


class NavigatorPi4(Navigator):
    all_dtparams = [
        "i2c_vc=on",
        "i2c_arm_baudrate=1000000",
        "spi=on",
        "enable_uart=1",
    ]
    
    # i2c overlays are required to detect the board
    i2c_overlays = [
        # i2c1: ADS1115, AK09915, BME280
        "i2c1",
        # i2c3: PCA
        "i2c4 pins_6_7=true baudrate=1000000",
    ]
    all_overlays = [
        # serial ports, checked individually
        "uart1",
        "uart3",
        "uart4",
        "uart5",
        "i2c6 pins_22_23=true baudrate=400000",
        "spi0-led",
        "spi1-3cs",
        "dwc2 dr_mode=otg",
    ]
    devices = {
        "ADS1115": (0x48, 1),
        "AK09915": (0x0C, 1),
        "BME280": (0x76, 1),
        "PCA9685": (0x40, 4),
    }
    gpio_config = {
      11: {
        "direction": GPIO.OUT,
        "value": GPIO.HIGH
      },
      24: {
        "direction": GPIO.OUT,
        "value": GPIO.HIGH
      },
      25: {
        "direction": GPIO.OUT,
        "value": GPIO.HIGH
      },
      37: {
        "direction": GPIO.OUT,
        "value": GPIO.LOW
      },
    }

    def detect(self):
        logger.info("Detecting Navigator on Pi4")
        if self.is_pi5():
            return False
        logger.info("setting up hardware for detection")
        self.setup_board_for_detection()
        return all(self.check_for_i2c_device(bus, address) for address, bus in self.devices.values())
