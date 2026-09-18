from typing import Dict, List

import blueos_startup_update
import pytest
from commonwealth.utils.general import CpuType
from test_blueos_startup_update import (
    BOOKWORM,
    NAVIGATOR_BOARDS,
    NAVIGATOR_INSTALL_SCRIPTS,
    Distribution,
    apply_boot_config_patches,
    install_script_configuration,
    install_script_section,
    section_configuration,
    stock_files,
)


def apply_install_script_section(script_name: str, config_txt: str) -> str:
    """Run the insertion loop of the install script on a config.txt held in memory."""
    section_name = install_script_section(script_name)
    _, insertions = install_script_configuration(script_name)
    lines = config_txt.splitlines()
    if f"[{section_name}]" not in lines:
        lines.append(f"[{section_name}]")
    line_number = lines.index(f"[{section_name}]")
    for string in insertions:
        line_number += 1
        lines.insert(line_number, string)
    return "\n".join(lines) + "\n"


def assert_dtparam_lines_precede_overlays(section_lines: List[str]) -> None:
    seen_overlay = False
    for line in section_lines:
        if line == blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE:
            seen_overlay = False
            continue
        if line.startswith("dtoverlay="):
            seen_overlay = True
            continue
        if line.startswith("dtparam=") and seen_overlay:
            raise AssertionError(f"dtparam line {line!r} appears after a dtoverlay line in {section_lines}")


SHIPPED_REVERSED_PI5_SECTION = """[pi5]
dtoverlay=dwc2,dr_mode=peripheral
gpio=37=op,pd,dl
gpio=11,24,25=op,pu,dh
dtoverlay=spi1-3cs
dtoverlay=spi0-led
dtparam=spi=on
dtoverlay=i2c-gpio,i2c_gpio_sda=22,i2c_gpio_scl=23,bus=6,i2c_gpio_delay_us=0
dtoverlay=i2c3-pi5.baudrate=400000
dtoverlay=i2c3-pi5,baudrate=400000
dtoverlay=i2c1
dtparam=i2c_arm=on
dtoverlay=uart2-pi5
dtoverlay=uart4-pi5
dtoverlay=uart3-pi5
dtoverlay=uart0-pi5
enable_uart=1
"""

USER_SECTION_LINES = [
    "dtparam=i2c_arm=on",
    "dtoverlay=my-custom-hat",
    "dtparam=spi=off #custom",
    "# plain user comment",
]


def user_section_fixture(distribution: Distribution, cpu_type: CpuType) -> Dict[str, str]:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)
    files[distribution.config_file] += f"\n[{section_name}]\n" + "\n".join(USER_SECTION_LINES) + "\n"
    return files


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_install_script_writes_declared_order(distribution: Distribution, cpu_type: CpuType) -> None:
    script_name = NAVIGATOR_INSTALL_SCRIPTS[cpu_type]
    section_name = install_script_section(script_name)
    _, insertions = install_script_configuration(script_name)

    installed_config = apply_install_script_section(script_name, distribution.stock_config)

    assert section_configuration(installed_config, section_name)[: len(insertions)] == insertions


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_install_script_and_startup_patches_agree(distribution: Distribution, cpu_type: CpuType) -> None:
    script_name = NAVIGATOR_INSTALL_SCRIPTS[cpu_type]
    section_name = install_script_section(script_name)

    installed_config = apply_install_script_section(script_name, distribution.stock_config)
    files = stock_files(distribution)
    apply_boot_config_patches(cpu_type, distribution, files)

    assert section_configuration(files[distribution.config_file], section_name) == section_configuration(
        installed_config, section_name
    )


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_keeps_dtparam_before_overlays(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)

    apply_boot_config_patches(cpu_type, distribution, files)

    assert_dtparam_lines_precede_overlays(section_configuration(files[distribution.config_file], section_name))


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_ends_the_overlay_scope(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)
    assert any(line.startswith("dtoverlay=") for line in distribution.stock_config.splitlines())

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    first_dtparam = next(index for index, line in enumerate(section_lines) if line.startswith("dtparam="))
    assert section_lines.index(blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE) < first_dtparam


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_keeps_the_hat_overlay_loadable(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)
    files[distribution.config_file] = "# a config.txt with no dtparam and no dtoverlay\n"

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    assert blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE not in section_lines
    assert_dtparam_lines_precede_overlays(section_lines)


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_keeps_the_scope_end_of_the_user(distribution: Distribution, cpu_type: CpuType) -> None:
    user_dtparam = "dtparam=act_led_trigger=heartbeat"
    files = stock_files(distribution)
    files[distribution.config_file] += f"\n{blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE}\n{user_dtparam}\n"

    apply_boot_config_patches(cpu_type, distribution, files)

    patched_lines = files[distribution.config_file].splitlines()
    assert (
        patched_lines[patched_lines.index(user_dtparam) - 1] == blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE
    ), "the patch removed the empty dtoverlay= that the user wrote"


def test_startup_patches_repair_a_reversed_board_section() -> None:
    _, insertions = install_script_configuration(NAVIGATOR_INSTALL_SCRIPTS[CpuType.PI5])
    files = stock_files(BOOKWORM)
    files[BOOKWORM.config_file] = BOOKWORM.stock_config + SHIPPED_REVERSED_PI5_SECTION

    applied = apply_boot_config_patches(CpuType.PI5, BOOKWORM, files)

    restarting = [name for name, wants_restart in applied.items() if wants_restart]
    assert restarting, "repairing a reversed section has to ask for a restart"
    assert section_configuration(files[BOOKWORM.config_file], "pi5")[: len(insertions)] == insertions
    assert_dtparam_lines_precede_overlays(section_configuration(files[BOOKWORM.config_file], "pi5"))


def test_startup_patches_converge_after_repairing_a_reversed_board_section() -> None:
    files = stock_files(BOOKWORM)
    files[BOOKWORM.config_file] = BOOKWORM.stock_config + SHIPPED_REVERSED_PI5_SECTION
    apply_boot_config_patches(CpuType.PI5, BOOKWORM, files)
    patched = dict(files)

    applied = apply_boot_config_patches(CpuType.PI5, BOOKWORM, files)

    restarting = [name for name, wants_restart in applied.items() if wants_restart]
    assert not restarting, f"{restarting} did not converge after repairing the reversed section"
    assert files == patched


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_rewrite_keeps_each_user_line_once(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = user_section_fixture(distribution, cpu_type)

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    for user_line in USER_SECTION_LINES:
        assert section_lines.count(user_line) == 1, f"{user_line!r} appeared {section_lines.count(user_line)} times"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_rewrite_converges_with_user_lines(distribution: Distribution, cpu_type: CpuType) -> None:
    files = user_section_fixture(distribution, cpu_type)

    apply_boot_config_patches(cpu_type, distribution, files)
    patched = dict(files)

    for run in (2, 3):
        applied = apply_boot_config_patches(cpu_type, distribution, files)
        restarting = [name for name, wants_restart in applied.items() if wants_restart]
        assert not restarting, f"run {run} requested restart for {restarting}"
        assert files == patched, f"run {run} changed the boot files"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_rewrite_drops_a_protected_line(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    protected_spi = "dtparam=spi=off #custom"
    files = stock_files(distribution)
    files[distribution.config_file] += f"\n[{section_name}]\n{protected_spi}\n"

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    assert section_lines.count(protected_spi) == 1
    assert section_lines.count("dtparam=spi=on") == 0


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_rewrite_keeps_a_protected_line_and_a_plain_one(
    distribution: Distribution, cpu_type: CpuType
) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    protected = "dtoverlay=i2c1 # custom"
    user_line = "hdmi_force_hotplug=1"
    files = stock_files(distribution)
    files[distribution.config_file] += f"\n[{section_name}]\n{protected}\n{user_line}\n"

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    assert section_lines.count(protected) == 1
    assert section_lines.count(user_line) == 1
