import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple
from unittest.mock import patch

import pytest

REPOSITORY_PATH = Path(__file__).parents[3]
assert (REPOSITORY_PATH / "install" / "boards").is_dir(), f"the repository root is not at {REPOSITORY_PATH}"

# blueos_startup_update.py is a standalone script installed into /usr/bin, not a package,
# so it has to be loaded by path, and commonwealth has to be reachable for its imports
sys.path.append(str(REPOSITORY_PATH / "core" / "libs" / "commonwealth"))
MODULE_PATH = Path(__file__).parent / "blueos_startup_update.py"
blueos_startup_update = ModuleType("blueos_startup_update")
blueos_startup_update.__file__ = str(MODULE_PATH)
# Loading through importlib caches bytecode next to the script, keyed on its size and its mtime in
# whole seconds, so an edit that changes neither is silently ignored on the next run
exec(  # pylint: disable=exec-used
    compile(MODULE_PATH.read_text(encoding="utf-8"), str(MODULE_PATH), "exec"), blueos_startup_update.__dict__
)

from commonwealth.utils.general import CpuType


class Distribution(NamedTuple):
    name: str
    config_file: str
    cmdline_file: str
    stock_config: str
    stock_cmdline: str
    # Boards this release runs on, whether or not a Navigator can be used with them
    cpu_types: Tuple[CpuType, ...]


# Boards a Navigator can be used with, and the install script that sets them up while building the
# image. The install scripts are the reference for what each board needs, and the startup patches
# have to reach the same result on devices installed before a given overlay was added. The hat sits
# on a different pinout on each board, so the two sets of overlays are not interchangeable.
NAVIGATOR_INSTALL_SCRIPTS = {
    CpuType.PI4: "install/boards/bcm_27xx.sh",
    CpuType.PI5: "install/boards/bcm_2712.sh",
}

ALL_INSTALL_SCRIPTS = sorted(
    str(script.relative_to(REPOSITORY_PATH)) for script in (REPOSITORY_PATH / "install" / "boards").glob("*.sh")
)

# The scripts that write to the boot partition, and so have to work out where it is. Picked by what
# they name rather than by their name, so a new board script is enrolled on its own and a script
# that drops its boot partition probe stays enrolled.
BOOT_FILE_INSTALL_SCRIPTS = [
    script for script in ALL_INSTALL_SCRIPTS if "config.txt" in (REPOSITORY_PATH / script).read_text(encoding="utf-8")
]
assert set(NAVIGATOR_INSTALL_SCRIPTS.values()) <= set(BOOT_FILE_INSTALL_SCRIPTS), "an install script went missing"

WORKFLOW_PATH = REPOSITORY_PATH / ".github" / "workflows" / "test-and-deploy.yml"

# Stock config.txt of the Bullseye image BlueOS builds from, taken from
# RPi-Distro/pi-gen stage1/00-boot-files/files/config.txt on the bullseye branch.
# The board section already exists here, sits in the middle of the file, and is followed by a
# second [all] section, so patching it has to stay inside its own bounds.
BULLSEYE_STOCK_CONFIG_TXT = """# For more options and information see
# http://rpf.io/configtxt
# Some settings may impact device functionality. See link above for details

# uncomment if you get no picture on HDMI for a default "safe" mode
#hdmi_safe=1

# uncomment to force a HDMI mode rather than DVI. This can make audio work in
# DMT (computer monitor) modes
#hdmi_drive=2

# uncomment for composite PAL
#sdtv_mode=2

#uncomment to overclock the arm. 700 MHz is the default.
#arm_freq=800

# Uncomment some or all of these to enable the optional hardware interfaces
#dtparam=i2c_arm=on
#dtparam=i2s=on
#dtparam=spi=on

# Uncomment this to enable infrared communication.
#dtoverlay=gpio-ir,gpio_pin=17
#dtoverlay=gpio-ir-tx,gpio_pin=18

# Additional overlays and parameters are documented /boot/overlays/README

# Enable audio (loads snd_bcm2835)
dtparam=audio=on

# Automatically load overlays for detected cameras
camera_auto_detect=1

# Automatically load overlays for detected DSI displays
display_auto_detect=1

# Enable DRM VC4 V3D driver
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Disable compensation for displays with overscan
disable_overscan=1

[cm4]
# Enable host mode on the 2711 built-in XHCI USB controller.
# This line should be removed if the legacy DWC2 controller is required
# (e.g. for USB device mode) or if USB support is not required.
otg_mode=1

[all]

[pi4]
# Run as fast as firmware / board allows
arm_boost=1

[all]
"""

# Stock config.txt of a Bookworm device, read back from a Raspberry Pi 4 before BlueOS touched it.
# There is no board section to patch here, so one has to be created.
BOOKWORM_STOCK_CONFIG_TXT = """# For more options and information see
# http://rptl.io/configtxt
# Some settings may impact device functionality. See link above for details

# Uncomment some or all of these to enable the optional hardware interfaces
#dtparam=i2c_arm=on
#dtparam=i2s=on
#dtparam=spi=on

# Enable audio (loads snd_bcm2835)
dtparam=audio=on

# Additional overlays and parameters are documented
# /boot/firmware/overlays/README

# Automatically load overlays for detected cameras
camera_auto_detect=1

# Automatically load overlays for detected DSI displays
display_auto_detect=1

# Automatically load initramfs files, if found
auto_initramfs=1

# Enable DRM VC4 V3D driver
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Don't have the firmware create an initial video= setting in cmdline.txt.
# Use the kernel's default instead.
disable_fw_kms_setup=1

# Disable compensation for displays with overscan
disable_overscan=1

# Run as fast as firmware / board allows
arm_boost=1

[cm4]
# Enable host mode on the 2711 built-in XHCI USB controller.
# This line should be removed if the legacy DWC2 controller is required
# (e.g. for USB device mode) or if USB support is not required.
otg_mode=1

[cm5]
dtoverlay=dwc2,dr_mode=host

[all]
"""

STOCK_CMDLINE_TXT = (
    "console=serial0,115200 console=tty1 root=PARTUUID=41964984-02 rootfstype=ext4 fsck.repair=yes rootwait\n"
)

# Bullseye keeps the boot partition at /boot, Bookworm moved it to /boot/firmware and left plain
# text stubs behind at /boot. A Pi5 is newer than Bullseye, so it only ever runs Bookworm.
BULLSEYE = Distribution(
    name="bullseye",
    config_file="/boot/config.txt",
    cmdline_file="/boot/cmdline.txt",
    stock_config=BULLSEYE_STOCK_CONFIG_TXT,
    stock_cmdline=STOCK_CMDLINE_TXT,
    cpu_types=(CpuType.PI3, CpuType.PI4),
)

BOOKWORM = Distribution(
    name="bookworm",
    config_file="/boot/firmware/config.txt",
    cmdline_file="/boot/firmware/cmdline.txt",
    stock_config=BOOKWORM_STOCK_CONFIG_TXT,
    stock_cmdline=STOCK_CMDLINE_TXT,
    cpu_types=(CpuType.PI3, CpuType.PI4, CpuType.PI5),
)

# Every distribution and Navigator capable board combination that can reach a user
NAVIGATOR_BOARDS = [
    pytest.param(distribution, cpu_type, id=f"{distribution.name}-{cpu_type.name}")
    for distribution in (BULLSEYE, BOOKWORM)
    for cpu_type in distribution.cpu_types
    if cpu_type in NAVIGATOR_INSTALL_SCRIPTS
]

DISTRIBUTIONS = [pytest.param(distribution, id=distribution.name) for distribution in (BULLSEYE, BOOKWORM)]

# What Bookworm leaves at /boot once it has moved the boot partition to /boot/firmware. Writing to
# it configures nothing, and the write still succeeds, which is how the original bug shipped.
BOOT_STUBS = {
    "config.txt": "DO NOT EDIT THIS FILE\n\nThe file you are looking for has moved to /boot/firmware/config.txt\n",
    "cmdline.txt": "DO NOT EDIT THIS FILE\n\nThe file you are looking for has moved to /boot/firmware/cmdline.txt\n",
}

MOUNTED_BOOT_PARTITION = {"config.txt": BOOKWORM_STOCK_CONFIG_TXT, "cmdline.txt": STOCK_CMDLINE_TXT}

# Boot partition layouts an install script has to tell apart, as directories of a fake root, and the
# one it has to settle on. None means it has to refuse to guess rather than configure a stub.
BOOT_LAYOUTS = [
    pytest.param({"boot/firmware": MOUNTED_BOOT_PARTITION, "boot": BOOT_STUBS}, "boot/firmware", id="bookworm"),
    pytest.param({"boot": MOUNTED_BOOT_PARTITION}, "boot", id="bullseye"),
    pytest.param({"boot": BOOT_STUBS}, None, id="bookworm-boot-partition-unmounted"),
    pytest.param({}, None, id="no-boot-partition"),
]


def bash_words(word_list: str) -> List[str]:
    """Expand a bash word list with bash, so quoting style and line continuations do not matter."""
    result = subprocess.run(
        ["bash", "-c", f'for STRING in {word_list}; do printf "%s\\n" "$STRING"; done'],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def install_script_section(script_name: str) -> str:
    """Board section an install script tags its configuration with."""
    content = (REPOSITORY_PATH / script_name).read_text(encoding="utf-8")

    section_match = re.search(r"""grep -q\w* ['"]\\\[(\w+)\\\]['"]""", content)
    assert section_match, f"{script_name} does not tag its configuration with a board section"

    return section_match.group(1)


def install_script_configuration(script_name: str) -> Tuple[List[str], List[str]]:
    """Configuration an install script deletes from, then inserts into, config.txt."""
    content = (REPOSITORY_PATH / script_name).read_text(encoding="utf-8")

    # Selecting the loops by what they do rather than by where they are keeps reformatting, requoting
    # and reordering the scripts out of the test results
    loops = [
        (bash_words(words), body)
        for words, body in re.findall(r"for STRING in\b(.*?);?\s*do\s*\\?\n(.*?)\ndone", content, re.DOTALL)
        if "$CONFIG_FILE" in body
    ]
    deleting = [words for words, body in loops if re.search(r"sed -i .?/\$STRING/d", body)]
    inserting = [words for words, body in loops if not re.search(r"sed -i .?/\$STRING/d", body)]
    assert len(deleting) == 1, f"{script_name}: expected one loop deleting from $CONFIG_FILE, got {len(deleting)}"
    assert len(inserting) == 1, f"{script_name}: expected one loop writing to $CONFIG_FILE, got {len(inserting)}"

    return deleting[0], inserting[0]


def boot_path_probe(content: str) -> Optional[str]:
    """The `if ... fi` block that derives BOOT_PATH, whatever shape the test it uses has."""
    return next(
        (
            match.group(0)
            for match in re.finditer(r"^if .*\n(?:.*\n)*?^fi$", content, re.MULTILINE)
            if "BOOT_PATH=" in match.group(0)
        ),
        None,
    )


def apply_boot_config_patches(
    cpu_type: CpuType,
    distribution: Distribution,
    files: Dict[str, str],
    patches: Tuple[Callable[[], bool], ...] = (),
) -> Dict[str, bool]:
    """Run startup patches against in-memory boot files, returning which of them want a restart."""

    def fake_load_file(file_name: str) -> str:
        return files[file_name]

    def fake_save_file(file_name: str, file_content: str, _backup_identifier: str, ensure_newline: bool = True) -> None:
        files[file_name] = file_content if not ensure_newline or file_content.endswith("\n") else f"{file_content}\n"

    # dwc2 owns its own overlay inside the same board section, and cgroups shares cmdline.txt and
    # the line merging with it, so all three are needed to get what the install scripts describe
    patches = patches or (
        blueos_startup_update.update_navigator_overlays,
        blueos_startup_update.update_dwc2,
        blueos_startup_update.update_cgroups,
    )

    blueos_startup_update.config_file = distribution.config_file
    blueos_startup_update.cmdline_file = distribution.cmdline_file
    with patch.object(blueos_startup_update, "load_file", fake_load_file), patch.object(
        blueos_startup_update, "save_file", fake_save_file
    ), patch.object(blueos_startup_update, "get_cpu_type", lambda: cpu_type):
        # Every patch has to run, the startup script does not stop at the first one that applies
        return {patch_function.__name__: patch_function() for patch_function in patches}


def stock_files(distribution: Distribution) -> Dict[str, str]:
    return {
        distribution.config_file: distribution.stock_config,
        distribution.cmdline_file: distribution.stock_cmdline,
    }


def section_names(config_txt: str) -> List[str]:
    """Section headers in file order, keeping repetitions."""
    return [line for line in config_txt.splitlines() if line.startswith("[")]


def root_configuration(config_txt: str) -> List[str]:
    """Lines before the first section header, which apply to every board."""
    lines = config_txt.splitlines()
    end = next((i for i, line in enumerate(lines) if line.startswith("[")), len(lines))
    return [line for line in lines[:end] if line]


def section_configuration(config_txt: str, section_name: str) -> List[str]:
    """Lines of a section, which ends at the first blank line or the next section header."""
    lines = config_txt.splitlines()
    if f"[{section_name}]" not in lines:
        return []
    start = lines.index(f"[{section_name}]")
    end = next(
        (start + 1 + i for i, line in enumerate(lines[start + 1 :]) if not line or line.startswith("[")),
        len(lines),
    )
    return lines[start + 1 : end]


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_startup_patches_match_install_script(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    _, insertions = install_script_configuration(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    # What the distribution already put in the board section is not ours to remove
    distribution_configuration = section_configuration(distribution.stock_config, section_name)
    files = stock_files(distribution)

    applied = apply_boot_config_patches(cpu_type, distribution, files)

    assert any(applied.values()), "a fresh install has to ask for a restart"
    patched_config = files[distribution.config_file]
    headers = patched_config.count(f"[{section_name}]")
    assert headers == 1, f"expected exactly one [{section_name}] in config.txt, found {headers}"
    assert sorted(section_configuration(patched_config, section_name)) == sorted(
        insertions + distribution_configuration
    )

    # An overlay of another board would drive the wrong pins of the Navigator
    for other_cpu_type, other_script in NAVIGATOR_INSTALL_SCRIPTS.items():
        if other_cpu_type == cpu_type:
            continue
        _, other_insertions = install_script_configuration(other_script)
        for line in set(other_insertions) - set(insertions):
            assert line not in patched_config.splitlines(), f"{line!r} belongs to {other_cpu_type.name}"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_startup_patches_keep_distribution_configuration(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    deletions, _ = install_script_configuration(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    files = stock_files(distribution)

    apply_boot_config_patches(cpu_type, distribution, files)

    # The install scripts delete these with `sed /STRING/d`, so anything containing one of them is
    # configuration BlueOS owns. Every other line the distribution shipped has to survive, including
    # the commented hardware hints and the sections of boards we are not running on.
    patched_lines = files[distribution.config_file].splitlines()
    for line in distribution.stock_config.splitlines():
        if not line or any(deletion in line for deletion in deletions):
            continue
        assert line in patched_lines, f"{distribution.name} lost {line!r}"

    assert section_names(files[distribution.config_file]) == section_names(distribution.stock_config) + (
        [] if f"[{section_name}]" in section_names(distribution.stock_config) else [f"[{section_name}]"]
    ), "patching moved, dropped or duplicated a section"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_startup_patches_converge_on_first_run(distribution: Distribution, cpu_type: CpuType) -> None:
    files = stock_files(distribution)
    apply_boot_config_patches(cpu_type, distribution, files)
    patched = dict(files)

    applied = apply_boot_config_patches(cpu_type, distribution, files)

    restarting = [name for name, wants_restart in applied.items() if wants_restart]
    assert not restarting, f"{restarting} did not converge, a reboot loop would follow"
    for file_name, content in patched.items():
        assert files[file_name] == content, f"{file_name} kept changing after the first run"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_startup_patches_replace_conflicting_configuration(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    _, insertions = install_script_configuration(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    distribution_configuration = section_configuration(distribution.stock_config, section_name)
    conflicting = "enable_uart=0\ndtparam=spi=off\ndtoverlay=spi1-1cs\ndtoverlay=dwc2,dr_mode=host\n"
    # The same configuration outside the board section applies to boards it was never meant for,
    # so it has to be removed even though the value itself is the one we want
    misplaced = insertions[:2]
    protected = "dtoverlay=i2c1 # custom\n"
    files = stock_files(distribution)
    files[distribution.config_file] += conflicting + "\n".join(misplaced) + "\n" + protected

    apply_boot_config_patches(cpu_type, distribution, files)

    patched_lines = files[distribution.config_file].splitlines()
    assert sorted(section_configuration(files[distribution.config_file], section_name)) == sorted(
        insertions + distribution_configuration
    )
    for conflicting_line in conflicting.splitlines():
        assert conflicting_line not in patched_lines
    for misplaced_line in misplaced:
        assert patched_lines.count(misplaced_line) == 1, f"{misplaced_line!r} was left outside [{section_name}]"
    assert protected.strip() in patched_lines, "a line the user protected was removed"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_every_patch_asks_for_the_restart_its_own_writes_need(distribution: Distribution, cpu_type: CpuType) -> None:
    files = stock_files(distribution)

    applied = apply_boot_config_patches(cpu_type, distribution, files)

    # Reading the patches through any() hides the one that rewrote a boot file and reported no
    # change, which is the field symptom: overlays written, no reboot asked for, no Navigator
    silent = sorted(name for name, wants_restart in applied.items() if not wants_restart)
    assert not silent, f"{silent} rewrote the boot files of a fresh install without asking for a restart"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
@pytest.mark.parametrize("modules_first", [True, False], ids=["modules-load-first", "modules-load-mid-line"])
def test_startup_patches_load_usb_ethernet_modules(
    distribution: Distribution, cpu_type: CpuType, modules_first: bool
) -> None:
    files = stock_files(distribution)
    # A device that already loads modules keeps them, the dwc2 ones are merged into the same
    # parameter. Index 0 of cmdline.txt is its own code path, a falsy index used to append instead.
    files[distribution.cmdline_file] = (
        f"modules-load=i2c-dev {distribution.stock_cmdline}"
        if modules_first
        else distribution.stock_cmdline.replace("rootwait", "rootwait modules-load=i2c-dev")
    )

    apply_boot_config_patches(cpu_type, distribution, files)

    parameters = files[distribution.cmdline_file].split()
    modules = [parameter for parameter in parameters if parameter.startswith("modules-load=")]
    assert len(modules) == 1, f"cmdline.txt ended up with {len(modules)} modules-load parameters, only the first loads"
    assert sorted(modules[0].removeprefix("modules-load=").split(",")) == ["dwc2", "g_ether", "i2c-dev"]
    for parameter in distribution.stock_cmdline.split():
        assert parameter in parameters, f"cmdline.txt lost {parameter!r}"

    apply_boot_config_patches(cpu_type, distribution, files)

    assert files[distribution.cmdline_file].split() == parameters, "cmdline.txt kept changing, a reboot loop follows"


@pytest.mark.parametrize("distribution, cpu_type", NAVIGATOR_BOARDS)
def test_startup_patches_merge_stray_board_sections(distribution: Distribution, cpu_type: CpuType) -> None:
    section_name = install_script_section(NAVIGATOR_INSTALL_SCRIPTS[cpu_type])
    # A release that appended a board section on every boot left devices with a run of empty
    # headers, of which only the first is ever configured, and the user kept configuring the others
    user_configuration = ["hdmi_force_hotplug=1", "force_turbo=1", "usb_max_current_enable=1"]
    files = stock_files(distribution)
    files[distribution.config_file] += f"\n[{section_name}]\n" * 27 + "".join(
        f"\n[{section_name}]\n{line}\n" for line in user_configuration
    )

    applied = apply_boot_config_patches(cpu_type, distribution, files)

    patched_config = files[distribution.config_file]
    headers = patched_config.count(f"[{section_name}]")
    assert headers == 1, f"a device in the field kept {headers} [{section_name}] headers, only the first is configured"
    for line in user_configuration:
        found = patched_config.splitlines().count(line)
        assert found == 1, f"merging the stray headers left {found} copies of the user configuration {line!r}"
        assert line in section_configuration(
            patched_config, section_name
        ), f"{line!r} was left outside [{section_name}], the user configuration stopped applying"
    assert any(applied.values()), "the boot files were repaired without asking for the restart that applies them"

    applied = apply_boot_config_patches(cpu_type, distribution, files)

    restarting = [name for name, wants_restart in applied.items() if wants_restart]
    assert not restarting, f"{restarting} did not converge on a repaired device, a reboot loop would follow"


def test_merging_board_sections_leaves_a_single_section_alone() -> None:
    config_content = ["[all]", "arm_boost=1", "", "[pi4]", "enable_uart=1", "", "[cm4]", "otg_mode=1"]
    untouched = config_content.copy()

    blueos_startup_update.boot_config_merge_duplicated_sections(config_content, "pi4")

    assert config_content == untouched, "a config.txt with one board section was rewritten, forcing a needless restart"


def test_appended_board_section_index_points_at_its_header() -> None:
    config_content = ["arm_boost=1"]

    (start, end) = blueos_startup_update.boot_config_get_or_append_section(config_content, "pi4")

    # An index past the header left the section empty and appended another one on the next boot,
    # so the overlays only ever landed one reboot late
    assert start < len(config_content) and config_content[start] == "[pi4]", (
        f"the appended section starts at index {start} of {len(config_content)} lines, which is not its header, "
        "so the overlays would land outside the section"
    )
    assert start < end <= len(config_content), f"the section bounds ({start}, {end}) cannot hold any configuration"
    assert blueos_startup_update.boot_config_get_or_append_section(config_content, "pi4") == (
        start,
        end,
    ), "looking the section up again did not find the one just appended"
    assert config_content.count("[pi4]") == 1, f"config.txt collected {config_content.count('[pi4]')} board sections"


def test_removing_a_section_that_is_not_there_changes_nothing() -> None:
    config_content = ["[all]", "arm_boost=1"]
    untouched = config_content.copy()

    blueos_startup_update.boot_config_remove_section(config_content, "pi4")

    assert config_content == untouched, "removing an absent section rewrote config.txt and asked for a restart"


def test_pi5_keeps_both_spellings_of_the_navigator_i2c_overlay() -> None:
    _, insertions = install_script_configuration(NAVIGATOR_INSTALL_SCRIPTS[CpuType.PI5])
    spellings = [line for line in insertions if line.startswith("dtoverlay=i2c3-pi5")]
    assert len(spellings) == 2, f"bcm_2712.sh no longer writes both i2c3 spellings: {spellings}"

    # The two spellings reach different firmware revisions, and used as a pattern the dotted one
    # matches the comma one, so a device already carrying either must still be given the other
    for existing in spellings:
        files = stock_files(BOOKWORM)
        files[BOOKWORM.config_file] += f"\n[pi5]\n{existing}\n"

        apply_boot_config_patches(CpuType.PI5, BOOKWORM, files)

        section = section_configuration(files[BOOKWORM.config_file], "pi5")
        for spelling in spellings:
            assert section.count(spelling) == 1, (
                f"a Pi5 already carrying {existing!r} ended up with {section.count(spelling)} copies of "
                f"{spelling!r}, the Navigator I2C bus would not come up"
            )


@pytest.mark.parametrize("distribution", DISTRIBUTIONS)
def test_navigator_configuration_is_never_applied_to_a_pi3(distribution: Distribution) -> None:
    """A Navigator cannot be used on a Pi3, the hat expects a pinout the board does not have."""
    files = stock_files(distribution)

    # Reaching these at all takes a bad board detection, which has happened before, so neither may
    # write anything of its own accord
    patches = (blueos_startup_update.update_navigator_overlays, blueos_startup_update.update_dwc2)
    applied = apply_boot_config_patches(CpuType.PI3, distribution, files, patches=patches)

    assert not any(applied.values()), "a Pi3 was told to restart for configuration it cannot use"
    assert files == stock_files(distribution), "boot files were patched for a board without a Navigator"


@pytest.mark.parametrize("distribution", DISTRIBUTIONS)
def test_pi3_cleanup_keeps_distribution_sections(distribution: Distribution) -> None:
    """A Pi3 got Navigator sections it cannot use, and only those may be cleaned up."""
    files = stock_files(distribution)

    apply_boot_config_patches(CpuType.PI3, distribution, files, patches=(blueos_startup_update.clean_config_pi3,))

    patched_lines = files[distribution.config_file].splitlines()
    # A filter the firmware does not recognise evaluates to true rather than false, so a section of
    # a board newer than the running firmware is not merely useless on a Pi3, its contents are
    # applied. Only the filters a Pi3 answers to may survive the cleanup.
    pi3_filters = {"all", "pi3", "pi3+", "cm3", "cm3+"}
    remaining = {name.strip("[]") for name in section_names(files[distribution.config_file])}
    assert remaining <= pi3_filters, f"a Pi3 would apply the contents of {sorted(remaining - pi3_filters)}"
    assert section_names(files[distribution.config_file]).count("[all]") == section_names(
        distribution.stock_config
    ).count("[all]")
    # Configuration outside a board section applies to a Pi3 as much as to any other board
    for line in root_configuration(distribution.stock_config):
        assert line in patched_lines, f"{distribution.name} lost {line!r}"

    applied = apply_boot_config_patches(
        CpuType.PI3, distribution, files, patches=(blueos_startup_update.clean_config_pi3,)
    )

    assert not any(applied.values()), "the cleanup did not converge, a reboot loop would follow"


def test_bcm28xx_enables_the_peripherals_a_pi3_needs() -> None:
    # Pi zero/1/2/3 have no startup patch to cross-check this script against, so these four lines
    # are the only description of what the onboard peripherals need
    deletions, insertions = install_script_configuration("install/boards/bcm_28xx.sh")

    assert sorted(insertions) == [
        "dtoverlay=spi1-3cs",
        "dtoverlay=uart1",
        "dtparam=i2c_arm=on",
        "dtparam=spi=on",
    ], f"bcm_28xx.sh no longer enables I2C, SPI and UART on a Pi3: {sorted(insertions)}"
    for insertion in insertions:
        assert any(
            deletion in insertion for deletion in deletions
        ), f"{insertion!r} is written but never cleaned out first, so reinstalling would stack duplicates"


@pytest.mark.parametrize("script_name", sorted(NAVIGATOR_INSTALL_SCRIPTS.values()))
def test_install_scripts_insert_below_the_first_board_section(script_name: str, tmp_path: Path) -> None:
    section_name = install_script_section(script_name)
    content = (REPOSITORY_PATH / script_name).read_text(encoding="utf-8")
    lookup = next((line for line in content.splitlines() if line.startswith("line_number=")), None)
    assert lookup, f"{script_name} no longer looks up where to insert the Navigator configuration"

    # Devices on the release that appended a board section on every boot carry a run of stray
    # headers. One line number per match makes every insertion `sed` fail, and the deletions have
    # already run by then, so the board is left with no configuration at all and the script exits 0.
    config_file = tmp_path / "config.txt"
    config_file.write_text(f"[all]\n[{section_name}]\n\n[{section_name}]\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", "-c", f'CONFIG_FILE="{config_file}"\n{lookup}\nprintf "%s" "$line_number"'],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == "2", (
        f"{script_name} resolved the insertion point to {result.stdout!r} on a config.txt carrying stray "
        f"[{section_name}] headers, so reinstalling would strip the Navigator configuration and report success"
    )


@pytest.mark.parametrize("script_name", BOOT_FILE_INSTALL_SCRIPTS)
@pytest.mark.parametrize("layout, expected", BOOT_LAYOUTS)
def test_install_scripts_probe_selects_the_real_boot_partition(
    script_name: str, layout: Dict[str, Dict[str, str]], expected: Optional[str], tmp_path: Path
) -> None:
    probe = boot_path_probe((REPOSITORY_PATH / script_name).read_text(encoding="utf-8"))
    assert probe, f"{script_name} no longer probes for the boot partition, /boot may be an inert Bookworm stub"

    for directory, boot_files in layout.items():
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
        for name, content in boot_files.items():
            (tmp_path / directory / name).write_text(content, encoding="utf-8")

    # The sibling test guarantees the probe is the only place naming /boot, so remapping that
    # literal onto a fake root is safe, and running it under bash keeps any branch shape working
    result = subprocess.run(
        ["bash", "-c", f'{probe.replace("/boot", f"{tmp_path}/boot")}\nprintf "%s" "$BOOT_PATH"'],
        capture_output=True,
        text=True,
        check=False,
    )
    resolved = result.stdout.replace(str(tmp_path), "") or "nothing"

    if expected is None:
        assert result.returncode != 0, (
            f"{script_name} resolved BOOT_PATH to {resolved} with no boot partition mounted, so the install "
            "would configure a plain text file and still report success"
        )
        return
    assert result.returncode == 0, f"{script_name} refused a valid boot partition: {result.stderr.strip()}"
    assert result.stdout == f"{tmp_path}/{expected}", (
        f"{script_name} resolved BOOT_PATH to {resolved} instead of /{expected}, so the Navigator "
        "configuration would never reach the boot partition"
    )


@pytest.mark.parametrize("script_name", ALL_INSTALL_SCRIPTS)
def test_install_scripts_reach_boot_files_only_through_boot_path(script_name: str) -> None:
    content = (REPOSITORY_PATH / script_name).read_text(encoding="utf-8")
    code = "\n".join(re.sub(r"\s+#.*$", "", line) for line in content.splitlines() if not line.lstrip().startswith("#"))
    probe = boot_path_probe(code)

    # Bookworm keeps the boot partition at /boot/firmware and leaves plain text stubs at /boot, so
    # every boot file has to be reached through BOOT_PATH rather than a hardcoded prefix. Only the
    # probe that decides which layout this is may name a path directly.
    outside_probe = code.replace(probe, "") if probe else code
    hardcoded = sorted(set(re.findall(r"/boot[\w./$-]*", outside_probe)))
    assert not hardcoded, f"{script_name} reaches boot files without BOOT_PATH: {hardcoded}"


def test_image_build_checks_what_the_install_scripts_write() -> None:
    # An install script that configures a stub still exits 0, so the built image is the only place
    # the mistake shows. That check only runs on the upstream repository, where nobody reads it
    # until a release ships, so it stopping matching the install scripts has to fail here instead.
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    sections = {install_script_section(script): script for script in NAVIGATOR_INSTALL_SCRIPTS.values()}

    checked = []
    for words in re.findall(r"EXPECTED=\((.*?)\)", workflow, re.DOTALL):
        expected = bash_words(words)
        headers = [line for line in expected if line.startswith("[")]
        assert len(headers) == 1, f"{expected} does not look for exactly one board section"
        section_name = headers[0].strip("[]")
        assert section_name in sections, f"no install script writes a [{section_name}] section"
        _, insertions = install_script_configuration(sections[section_name])
        for line in expected:
            assert line in headers or line in insertions, f"{sections[section_name]} does not write {line!r}"
        checked.append(section_name)

    assert sorted(checked) == sorted(sections), f"{sorted(sections)} are built as images, {sorted(checked)} are checked"

    # cmdline.txt is reached through a path of its own, so it is checked separately, and every board
    # script writes the same two things to it whether or not a Navigator can be used with the board
    for configuration in ("cgroup_enable=memory", "console=serial"):
        assert f'"{configuration}" /mnt/piboot/cmdline.txt' in workflow, f"the image is not checked for {configuration}"
        for script_name in BOOT_FILE_INSTALL_SCRIPTS:
            content = (REPOSITORY_PATH / script_name).read_text(encoding="utf-8")
            assert configuration in content, f"{script_name} no longer writes {configuration!r}"


@pytest.mark.parametrize("boot_file", ["config.txt", "cmdline.txt"])
def test_startup_patches_prefer_the_bookworm_boot_partition(boot_file: str) -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    # On Bookworm both paths exist, but /boot holds a plain text stub, so it may only ever be the
    # fallback of the two.
    candidates = re.findall(rf'"(/boot[^"]*{re.escape(boot_file)})"', source)
    assert candidates == [f"/boot/firmware/{boot_file}", f"/boot/{boot_file}"]
