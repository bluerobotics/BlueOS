import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

import blueos_startup_update
import pytest
from commonwealth.utils.general import CpuType
from test_blueos_startup_update import (
    BOOKWORM,
    MULTI_BOARD_INSTALL_SCRIPT,
    NAVIGATOR_BOARDS,
    NAVIGATOR_INSTALL_SCRIPTS,
    REPOSITORY_PATH,
    TRIXIE,
    Distribution,
    apply_boot_config_patches,
    install_script_configuration,
    install_script_section,
    multi_board_sections,
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
    config = "\n".join(lines) + "\n"
    if "close_overlay_scope()" in (REPOSITORY_PATH / script_name).read_text(encoding="utf-8"):
        config = close_overlay_scope(script_name, section_name, config)
    return config


def close_overlay_scope(script_name: str, section_name: str, config_txt: str) -> str:
    """Run the close_overlay_scope function of an install script, in bash, on a config.txt."""
    content = (REPOSITORY_PATH / script_name).read_text(encoding="utf-8")
    function = re.search(r"^close_overlay_scope\(\) \{\n.*?^\}\n", content, re.DOTALL | re.MULTILINE)
    assert function, f"{script_name} does not close the overlay scope of its section"
    with tempfile.TemporaryDirectory() as directory:
        config_file = Path(directory) / "config.txt"
        config_file.write_text(config_txt, encoding="utf-8")
        script = f'CONFIG_FILE="$1"\n{function.group(0)}\nclose_overlay_scope "$2"'
        subprocess.run(["bash", "-c", script, "bash", config_file, section_name], check=True)
        return config_file.read_text(encoding="utf-8")


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

    patched_lines = files[distribution.config_file].splitlines()
    first_directive = next(line for line in patched_lines if line.startswith(("dtparam=", "dtoverlay=")))
    assert (
        first_directive != blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE
    ), "config.txt opens with the empty dtoverlay=, so the firmware skips the HAT overlay"
    assert_dtparam_lines_precede_overlays(section_configuration(files[distribution.config_file], section_name))


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_closes_a_hat_overlay_scope(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)
    # the firmware loads the HAT overlay before it reads config.txt, and that overlay stays
    # in scope while no line of config.txt opens another one. The firmware trims the line,
    # so this line counts as a directive.
    files[distribution.config_file] = "  dtparam=audio=on\n"

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    assert (
        section_lines[0] == blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE
    ), "a HAT overlay is in scope here, so the board dtparam lines would be read against the HAT"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_skips_a_line_the_firmware_does_not_read(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)
    # a space around the equal sign hides the line from the firmware, so the board section
    # holds the first directive of the file
    files[distribution.config_file] = "dtparam = audio=on\n"

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    assert (
        section_lines[0] != blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE
    ), "config.txt opens with the empty dtoverlay=, so the firmware skips the HAT overlay"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_closes_its_own_overlay_scope(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    assert not blueos_startup_update.boot_config_overlay_is_open(
        section_lines
    ), "a line written below the board section would go to the last overlay of the board"


@pytest.mark.parametrize(
    "line, overlay_is_open",
    [
        ("dtoverlay=uart1", True),
        ("dtoverlay=", False),
        # the firmware trims the line before it reads the directive
        ("   dtoverlay=   ", False),
        ("\tdtoverlay=uart1", True),
        # the firmware keeps a comment that follows a directive, so the name is "uart1 # a
        # comment". No overlay carries that name, so the line opens nothing. We still answer
        # open, because one empty dtoverlay= too many costs nothing and one too few does.
        ("dtoverlay=uart1 # a comment", True),
        ("dtoverlay= # a comment", True),
        # the firmware reads nothing in these three lines, so the overlay above stays open
        ("dtoverlay = uart1", True),
        ("DTOVERLAY=", True),
        ("#dtoverlay=", True),
    ],
)
def test_overlay_is_open_reads_a_line_like_the_firmware(line: str, overlay_is_open: bool) -> None:
    assert blueos_startup_update.boot_config_overlay_is_open(["dtoverlay=uart0", line]) == overlay_is_open


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_keeps_the_scope_end_of_the_user(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    user_overlay = "dtoverlay=my-hat"
    user_dtparam = "dtparam=act_led_trigger=heartbeat"
    scope_end = blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE
    files = stock_files(distribution)
    files[distribution.config_file] += f"\n[{section_name}]\n{user_overlay}\n{scope_end}\n{user_dtparam}\n"

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    above_dtparam = section_lines[: section_lines.index(user_dtparam)]
    assert user_overlay in above_dtparam
    assert not blueos_startup_update.boot_config_overlay_is_open(
        above_dtparam
    ), "the patch removed the empty dtoverlay= of the user, so the dtparam goes to the overlay of the user"

    patched = dict(files)
    applied = apply_boot_config_patches(cpu_type, distribution, files)
    assert not any(applied.values()), "the second run asked for a restart, so it changed something"
    assert files == patched, "the second run rewrote a boot file"


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
    above_protected = section_lines[: section_lines.index(protected_spi)]
    assert not blueos_startup_update.boot_config_overlay_is_open(
        above_protected
    ), "the protected dtparam goes to the overlay above it instead of to the board"


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


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_closes_the_scope_of_an_overlay_the_user_keeps(
    distribution: Distribution, cpu_type: CpuType
) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)
    files[distribution.config_file] += f"\n[{section_name}]\ndtoverlay=my-hat\n[all]\ndtparam=audio=on\n"

    apply_boot_config_patches(cpu_type, distribution, files)
    patched = dict(files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    assert "dtoverlay=my-hat" in section_lines
    assert not blueos_startup_update.boot_config_overlay_is_open(
        section_lines
    ), "the dtparam lines written below the section would go to dtoverlay=my-hat"
    applied = apply_boot_config_patches(cpu_type, distribution, files)
    assert not any(applied.values()) and files == patched, "closing the overlay did not converge"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_board_section_puts_a_protected_line_in_the_slot_of_the_board_line(
    distribution: Distribution, cpu_type: CpuType
) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    protected_spi = "dtparam=spi=off #custom"
    files = stock_files(distribution)
    files[distribution.config_file] += f"\n[{section_name}]\ndtoverlay=my-hat\n{protected_spi}\n"

    apply_boot_config_patches(cpu_type, distribution, files)

    section_lines = section_configuration(files[distribution.config_file], section_name)
    assert section_lines.index(protected_spi) < section_lines.index("dtoverlay=my-hat")
    assert not blueos_startup_update.boot_config_overlay_is_open(section_lines[: section_lines.index(protected_spi)])


def test_install_script_closes_the_scope_of_an_overlay_already_in_the_section() -> None:
    script_name = NAVIGATOR_INSTALL_SCRIPTS[CpuType.PI5]
    config = "arm_64bit=1\n[pi5]\ndtparam=spi=on\ndtoverlay=nospi10\n\n[all]\ndtparam=audio=on\n"

    closed = close_overlay_scope(script_name, "pi5", config)

    assert closed == config.replace("dtoverlay=nospi10\n", "dtoverlay=nospi10\ndtoverlay=\n")
    assert close_overlay_scope(script_name, "pi5", closed) == closed
    assert close_overlay_scope(script_name, "pi5", config.replace("dtoverlay=nospi10\n", "")) == config.replace(
        "dtoverlay=nospi10\n", ""
    )


@pytest.mark.parametrize("cpu_type", [CpuType.PI4, CpuType.PI5])
def test_multi_board_script_writes_what_the_startup_patches_manage(cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    managed = blueos_startup_update.navigator_managed_entries(cpu_type)
    # The USB gadget mode is left to update_dwc2, and the scope is closed when a board overlay is last
    expected = [line for line, _ in managed if not line.startswith("dtoverlay=dwc2")]
    expected.append(blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE)

    assert multi_board_sections()[section_name] == expected


def test_multi_board_script_closes_every_section_it_writes() -> None:
    sections = multi_board_sections()
    assert sorted(sections) == ["pi3", "pi4", "pi5"]
    for name, lines in sections.items():
        assert lines[0] == blueos_startup_update.BOOT_CONFIG_END_OVERLAY_SCOPE, name
        assert not blueos_startup_update.boot_config_overlay_is_open(lines), f"[{name}] ends with an open overlay"


@pytest.mark.parametrize("cpu_type", [CpuType.PI4, CpuType.PI5])
def test_multi_board_script_and_startup_patches_converge(cpu_type: CpuType) -> None:
    content = (REPOSITORY_PATH / MULTI_BOARD_INSTALL_SCRIPT).read_text(encoding="utf-8")
    start = content.index("write_board_section() {")
    end = content.index("for SECTION in pi3 pi4 pi5; do")
    end = content.index("\ndone\n", end) + len("\ndone\n")
    function = content[start:end]
    # closes the overlay the stock Trixie section holds, which is what the real script runs against
    close_function = re.search(r"^close_overlay_scope\(\) \{\n.*?^\}\n", content, re.DOTALL | re.MULTILINE)
    assert close_function
    function = close_function.group(0) + function.replace(close_function.group(0), "")
    with tempfile.TemporaryDirectory() as directory:
        config_file = Path(directory) / "config.txt"
        config_file.write_text(TRIXIE.stock_config, encoding="utf-8")
        subprocess.run(["bash", "-c", f'CONFIG_FILE="$1"\n{function}', "bash", config_file], check=True)
        files = stock_files(TRIXIE)
        files[TRIXIE.config_file] = config_file.read_text(encoding="utf-8")

    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    written = section_configuration(files[TRIXIE.config_file], section_name)
    apply_boot_config_patches(cpu_type, TRIXIE, files)
    patched = section_configuration(files[TRIXIE.config_file], section_name)
    assert [line for line in patched if not line.startswith("dtoverlay=dwc2")] == written
    applied = apply_boot_config_patches(cpu_type, TRIXIE, files)
    assert not any(applied.values())
