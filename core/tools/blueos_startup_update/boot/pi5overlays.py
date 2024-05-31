import re
from typing import List, Optional

from loguru import logger

from commonwealth.utils.commands import run_command


class Overlay:
    def __init__(self, name: str, args: List[str], index: Optional[int] = None):
        self.name = name
        self.args = args
        self.index = index

    def __repr__(self) -> str:
        joined_args = " ".join(self.args)
        return f"{self.name} {joined_args}"

    def wrongly_set_in(self, overlays: List["Overlay"]) -> bool:
        for loaded_overlay in overlays:
            if loaded_overlay.name == self.name and loaded_overlay.args != self.args:
                return True
        return False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Overlay):
            return False
        return self.name == other.name and self.args == other.args

    def reload(self) -> None:
        command_result = run_command(f"sudo dtoverlay -r {self.name} && sudo dtoverlay {self}", False)
        logger.info(command_result)

    def load(self) -> None:
        command_result = run_command(f"sudo dtoverlay {self}", False)
        logger.info(command_result)

    @staticmethod
    def from_string(overlay: str) -> "Overlay":
        match = re.match(r"^((?P<index>\d+):\s+)?(?P<name>(\S)+)(?:$|\s+(?P<args>.*))", overlay)
        if not match:
            logger.error(f"no match for {overlay}")
            raise ValueError(f"no match for {overlay}")
        overlay_name = match.group("name")
        overlay_args = match.group("args").split(" ") if match.group("args") else []
        index = int(match.group("index")) if match.group("index") else None
        return Overlay(overlay_name, overlay_args, index=index)


class DtParam:
    def __init__(self, arg: str, value: str):
        self.arg = arg
        self.value = value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DtParam):
            return False
        return self.arg == other.arg and self.value == other.value

    def wrongly_set_in(self, dt_params: List["DtParam"]) -> bool:
        for loaded_dt_param in dt_params:
            if loaded_dt_param.arg == self.arg and loaded_dt_param.value != self.value:
                return True
        return False

    def load(self) -> None:
        command_result = run_command(f"sudo dtoverlay {self}", False)
        logger.info(command_result)

    def reload(self) -> None:
        command_result = run_command(f"sudo dtoverlay -r {self} && sudo dtoverlay {self}", False)
        logger.info(command_result)

    def __repr__(self) -> str:
        return f"{self.arg}={self.value}"


# pylint: disable=too-many-branches
def load_pi5_overlays_in_runtime() -> bool:
    """
    this parses the output of dtoverlay -l and checks if the required overlays are loaded
    sample output:
        Overlays (in load order):
        0:  dtparam  i2c_arm=on
        1:  dtparam  i2c_arm_baudrate=1000000
        2:  uart0-pi5
        3:  uart3-pi5
        4:  uart4-pi5
        5:  uart2-pi5
        6:  i2c-gpio  i2c_gpio_sda=22 i2c_gpio_scl=23 bus=6 i2c_gpio_delay_us=0
        7:  i2c1-pi5  baudrate=400000
        8:  i2c3-pi5  baudrate=400000
        9:  spi1-3cs
        10:  spi0-led
    """

    dtparams_to_load_strings = [
        "i2c_arm=on",
        "i2c_arm_baudrate=1000000",
    ]
    dtparams_to_load = [DtParam(*dtparam.split("=")) for dtparam in dtparams_to_load_strings]

    overlays_to_load_strings = [
        # serial ports, checked individually
        "uart0-pi5",  # Navigator serial1
        "uart3-pi5",  # Navigator serial4
        "uart4-pi5",  # Navigator serial5
        "uart2-pi5",  # Navigator serial3
        # i2c-6: bar30 and friends
        "i2c-gpio i2c_gpio_sda=22 i2c_gpio_scl=23 bus=6 i2c_gpio_delay_us=0",
        # i2c1: ADS1115, AK09915, BME280
        "i2c1-pi5 baudrate=400000",
        # i2c3: PCA
        "i2c3-pi5 baudrate=400000",
        # SPI1: MMC5983
        "spi1-3cs",
        # SPI0: LED
        "spi0-led",
    ]
    overlays_to_load = [Overlay.from_string(overlay) for overlay in overlays_to_load_strings]

    loaded_dt_params: List[DtParam] = []
    loaded_overlays: List[Overlay] = []

    dtoverlay_output = run_command("dtoverlay -l", check=False).stdout
    for line in dtoverlay_output.splitlines():
        match = re.match(r"^(?P<index>\d+):\s+(?P<name>(\S)+)(?:$|\s+(?P<args>.*))", line)
        if not match:
            continue
        overlay_name = match.group("name")
        overlay_args = match.group("args")
        if "dtparam" in overlay_name:
            # this is always a key=value pair
            loaded_dt_params.append(DtParam(*overlay_args.split("=", maxsplit=1)))
        else:
            loaded_overlays.append(Overlay(overlay_name, overlay_args.split(" ") if overlay_args else []))

    logger.info("Loaded dt params: ")
    for dt_param in loaded_dt_params:
        logger.info(dt_param)

    for dtparam in dtparams_to_load:
        if dtparam in loaded_dt_params:
            logger.info(f"dtparam {dtparam} is already loaded")
        elif dtparam.wrongly_set_in(loaded_dt_params):
            logger.info(f"Reloading dtparam {dtparam}")
            command_result = run_command(f"sudo dtoverlay -r {dtparam.arg} && sudo dtoverlay {dtparam}", False)
            logger.info(command_result)

    command_result = run_command("sudo modprobe i2c-dev", False)
    # validate if i2c-dev is loaded using lsmod
    if "i2c_dev" not in run_command("lsmod", False).stdout:
        logger.error("Failed to load i2c-dev")
        return False
    logger.info(command_result)

    for overlay in overlays_to_load:
        if overlay in loaded_overlays:
            logger.info(f"Overlay {overlay} is already loaded")
        elif overlay.wrongly_set_in(loaded_overlays):
            logger.info(f"Overlay {overlay} has wrong parameters, reloading.")
            overlay.reload()
        else:
            logger.info(f"Loading overlay {overlay}")
            overlay.load()

    return False
