from typing import Any, Dict, List

from commonwealth.utils.commands import load_file, locate_file, run_command, save_file
from loguru import logger
from RPi import GPIO

from flight_controller_detector.linux.linux_boards import LinuxFlightController
from flight_controller_detector.linux.overlay_loader import load_overlays_in_runtime
from typedefs import Platform, Serial

GPIO.setmode(GPIO.BCM)


class Navigator(LinuxFlightController):
    name = "Navigator"
    manufacturer = "Blue Robotics"
    platform = Platform.Navigator
    gpio_config: dict[int, Dict[str, Any]] = {}
    all_dtparams: List[str] = []
    i2c_overlays: List[str] = []
    all_overlays: List[str] = []

    def is_pi5(self) -> bool:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            return "Raspberry Pi 5" in f.read()

    def detect(self) -> bool:
        return False

    def setup_board(self) -> None:
        self.build_led_overlay()
        load_overlays_in_runtime(self.all_dtparams, self.all_overlays, ["i2c_dev"])
        for gpio, config in self.gpio_config.items():
            self.setup_gpio(gpio, config["direction"], config["value"])

    def setup_gpio(self, pin: int, direction: str, value: bool) -> None:
        GPIO.setup(pin, direction)
        GPIO.output(pin, value)

    def setup_board_for_detection(self) -> None:
        load_overlays_in_runtime(self.all_dtparams, self.i2c_overlays, ["i2c_dev"])

    def get_serials(self) -> List[Serial]:
        return [
            Serial(port="C", endpoint="/dev/ttyAMA0"),
            Serial(port="B", endpoint="/dev/ttyAMA2"),
            Serial(port="E", endpoint="/dev/ttyAMA3"),
            Serial(port="F", endpoint="/dev/ttyAMA4"),
        ]

    def build_led_overlay(self) -> None:
        temp_overlay_file_at_host = "/tmp/spi0-led.dts"
        target_overlay_location_pi4 = "/boot/overlays/spi0-led.dtbo"
        target_overlay_location_pi5 = "/boot/firmware/overlays/spi0-led.dtbo"
        overlay_exists = locate_file([target_overlay_location_pi4, target_overlay_location_pi5])
        if overlay_exists:
            logger.info(f"spi0-led overlay found at {overlay_exists}")
            return
        dts = load_file(
            "/home/pi/services/ardupilot_manager/flight_controller_detector/linux/overlay_source/spi0-led.dts"
        )
        save_file(temp_overlay_file_at_host, dts, "")
        command = f"sudo dtc -@ -Hepapr -I dts -O dtb -o {target_overlay_location_pi4} {temp_overlay_file_at_host}"
        run_command(command, False)
        copy_command = (
            f"if [ -d /boot/firmware ]; then sudo cp {target_overlay_location_pi4} {target_overlay_location_pi5}; fi"
        )
        run_command(copy_command, False)


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
    devices = {
        "ADS1115": (0x48, 1),
        "AK09915": (0x0C, 1),
        "BME280": (0x76, 1),
        "PCA9685": (0x40, 3),
    }

    def detect(self) -> bool:
        if not self.is_pi5():
            return False
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
        # serial ports, checked individually
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
        11: {"direction": GPIO.OUT, "value": GPIO.HIGH},
        24: {"direction": GPIO.OUT, "value": GPIO.HIGH},
        25: {"direction": GPIO.OUT, "value": GPIO.HIGH},
        37: {"direction": GPIO.OUT, "value": GPIO.LOW},
    }

    def detect(self) -> bool:
        if self.is_pi5():
            return False
        return all(self.check_for_i2c_device(bus, address) for address, bus in self.devices.values())
