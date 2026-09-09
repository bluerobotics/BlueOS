import re
from enum import Enum


class Pi5I2CMode(str, Enum):
    EXTERNAL_SENSOR = "external_sensor"
    MIPI_CAMERA = "mipi_camera"


class Pi5I2CConfigurationError(ValueError):
    pass


def _navigator_i2c_overlay(config_content: str) -> tuple[int, int]:
    section = "all"
    matches: list[tuple[int, int]] = []

    for index, line in enumerate(config_content.splitlines()):
        section_match = re.match(r"^\s*\[([^]]+)]", line)
        if section_match:
            section = section_match.group(1).strip().lower()
            continue
        if section != "pi5":
            continue

        configuration = line.partition("#")[0].strip()
        if not configuration.startswith("dtoverlay=i2c-gpio,"):
            continue

        parameters = {
            key.strip(): value.strip()
            for parameter in configuration.split(",")[1:]
            if "=" in parameter
            for key, value in [parameter.split("=", maxsplit=1)]
        }
        if (
            parameters.get("i2c_gpio_sda") != "22"
            or parameters.get("i2c_gpio_scl") != "23"
        ):
            continue

        try:
            bus = int(parameters["bus"])
        except (KeyError, ValueError) as error:
            raise Pi5I2CConfigurationError(
                "Navigator I2C overlay has no valid bus number."
            ) from error
        matches.append((index, bus))

    if not matches:
        raise Pi5I2CConfigurationError(
            "Navigator I2C overlay was not found in the [pi5] section."
        )
    if len(matches) > 1:
        raise Pi5I2CConfigurationError(
            "Multiple Navigator I2C overlays were found in the [pi5] section."
        )
    return matches[0]


def get_pi5_i2c_mode(config_content: str) -> Pi5I2CMode:
    _, bus = _navigator_i2c_overlay(config_content)
    if bus == 6:
        return Pi5I2CMode.EXTERNAL_SENSOR
    if bus == 8:
        return Pi5I2CMode.MIPI_CAMERA
    raise Pi5I2CConfigurationError(f"Navigator I2C overlay uses unsupported bus {bus}.")


def set_pi5_i2c_mode(config_content: str, mode: Pi5I2CMode) -> str:
    line_index, _ = _navigator_i2c_overlay(config_content)
    if mode == Pi5I2CMode.EXTERNAL_SENSOR:
        bus = 6
    elif mode == Pi5I2CMode.MIPI_CAMERA:
        bus = 8
    else:
        raise Pi5I2CConfigurationError(f"Unsupported Raspberry Pi 5 I2C mode: {mode}.")
    lines = config_content.splitlines(keepends=True)
    configuration, comment_separator, comment = lines[line_index].partition("#")
    updated_configuration, replacements = re.subn(
        r"(?P<prefix>(?:^|,)\s*bus\s*=\s*)\d+",
        rf"\g<prefix>{bus}",
        configuration,
        count=1,
    )
    if replacements != 1:
        raise Pi5I2CConfigurationError(
            "Navigator I2C bus parameter could not be updated."
        )
    lines[line_index] = updated_configuration + comment_separator + comment
    return "".join(lines)
