import pytest
from firmware.FirmwareManagement import FirmwareManager
from typedefs import Platform, PlatformType


@pytest.mark.parametrize(
    "platform, firmware_name",
    [
        (Platform(name="Navigator", platform_type=PlatformType.Linux), "ardupilot_navigator"),
        (Platform(name="Navigator64", platform_type=PlatformType.Linux), "ardupilot_navigator64"),
        (Platform(name="Argonot", platform_type=PlatformType.Linux), "ardupilot_argonot"),
        (Platform(name="SITL_x86_64_linux_gnu", platform_type=PlatformType.SITL), "ardupilot_sitl_x86_64_linux_gnu"),
        (
            Platform(name="SITL_arm_linux_gnueabihf", platform_type=PlatformType.SITL),
            "ardupilot_sitl_arm_linux_gnueabihf",
        ),
        (Platform(name="Pixhawk1", platform_type=PlatformType.Serial), "ardupilot_pixhawk1"),
        (Platform(name="CubeOrange-bdshot", platform_type=PlatformType.Serial), "ardupilot_cubeorange-bdshot"),
        (Platform(name="PX4 FMU v6U.x", platform_type=PlatformType.Serial), "ardupilot_px4_fmu_v6u_x"),
        (Platform(name="../../etc/passwd", platform_type=PlatformType.Serial), "ardupilot_______etc_passwd"),
    ],
)
def test_firmware_name_is_a_safe_file_name(platform: Platform, firmware_name: str) -> None:
    assert FirmwareManager.firmware_name(platform) == firmware_name
