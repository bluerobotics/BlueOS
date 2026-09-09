import pytest
from pi5_i2c import (
    Pi5I2CConfigurationError,
    Pi5I2CMode,
    get_pi5_i2c_mode,
    set_pi5_i2c_mode,
)

SENSOR_CONFIGURATION = """[all]
dtparam=i2c_arm=on

[pi5]
dtoverlay=i2c-gpio,i2c_gpio_sda=22,i2c_gpio_scl=23,bus=6,i2c_gpio_delay_us=0
"""


def test_get_pi5_i2c_mode():
    assert get_pi5_i2c_mode(SENSOR_CONFIGURATION) == Pi5I2CMode.EXTERNAL_SENSOR
    camera_configuration = SENSOR_CONFIGURATION.replace("bus=6", "bus=8")
    assert get_pi5_i2c_mode(camera_configuration) == Pi5I2CMode.MIPI_CAMERA


def test_set_pi5_i2c_mode_preserves_other_configuration():
    protected_configuration = SENSOR_CONFIGURATION.replace(
        "i2c_gpio_delay_us=0", "i2c_gpio_delay_us=0 # custom"
    )

    camera_configuration = set_pi5_i2c_mode(
        protected_configuration, Pi5I2CMode.MIPI_CAMERA
    )

    assert "bus=8" in camera_configuration
    assert "i2c_gpio_delay_us=0 # custom" in camera_configuration
    assert camera_configuration.replace("bus=8", "bus=6") == protected_configuration


def test_set_pi5_i2c_mode_only_changes_pi5_section():
    configuration = SENSOR_CONFIGURATION.replace(
        "[all]",
        "[all]\ndtoverlay=i2c-gpio,i2c_gpio_sda=22,i2c_gpio_scl=23,bus=4,i2c_gpio_delay_us=0",
    )

    camera_configuration = set_pi5_i2c_mode(configuration, Pi5I2CMode.MIPI_CAMERA)

    assert "bus=4" in camera_configuration
    assert camera_configuration.count("bus=8") == 1


def test_set_pi5_i2c_mode_preserves_crlf_and_accepts_spaced_section():
    configuration = SENSOR_CONFIGURATION.replace("[pi5]", "[ pi5 ]").replace(
        "\n", "\r\n"
    )

    camera_configuration = set_pi5_i2c_mode(configuration, Pi5I2CMode.MIPI_CAMERA)

    assert camera_configuration.count("\r\n") == configuration.count("\r\n")
    assert "bus=8" in camera_configuration


def test_set_pi5_i2c_mode_rejects_unknown_mode():
    with pytest.raises(Pi5I2CConfigurationError):
        set_pi5_i2c_mode(SENSOR_CONFIGURATION, "automatic")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "configuration",
    [
        "[pi5]\ndtoverlay=i2c1\n",
        SENSOR_CONFIGURATION.replace(",bus=6", ""),
        SENSOR_CONFIGURATION.replace("bus=6", "bus=7"),
        SENSOR_CONFIGURATION + SENSOR_CONFIGURATION.split("[pi5]\n", maxsplit=1)[1],
    ],
)
def test_get_pi5_i2c_mode_rejects_ambiguous_or_unsupported_configuration(
    configuration: str,
):
    with pytest.raises(Pi5I2CConfigurationError):
        get_pi5_i2c_mode(configuration)
