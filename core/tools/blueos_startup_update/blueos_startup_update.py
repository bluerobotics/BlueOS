#!/usr/bin/env python
import copy
import json
import logging
import os
import re
from enum import Enum
import time
from typing import List, Optional, Tuple

import appdirs
from commonwealth.utils.commands import run_command, save_file, locate_file
from commonwealth.utils.logs import InterceptHandler, init_logger
from loguru import logger

SERVICE_NAME = "blueos_startup_update"

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

BOOT_LOOP_DETECTOR = "/root/.config/.boot_loop_detector"

# Any change made in this DELTA_JSON dict should be also made
# into /bootstrap/startup.json.default too!
DELTA_JSON = {
    "core": {
        "binds": {
            "/run/udev": {"bind": "/run/udev", "mode": "ro"},
            "/etc/blueos": {"bind": "/etc/blueos", "mode": "rw"},
            "/etc/machine-id": {"bind": "/etc/machine-id", "mode": "ro"},
            "/etc/dhcpcd.conf": {"bind": "/etc/dhcpcd.conf", "mode": "rw"},
            "/usr/blueos/userdata": {"bind": "/usr/blueos/userdata", "mode": "rw"},
            "/usr/blueos/extensions": {"bind": "/usr/blueos/extensions", "mode": "rw"},
            "/usr/blueos/bin": {"bind": "/usr/blueos/bin", "mode": "rw"},
            "/etc/resolv.conf.host": {"bind": "/etc/resolv.conf.host", "mode": "ro"},
            "/home/pi/.ssh": {"bind": "/home/pi/.ssh", "mode": "rw"},
        }
    }
}

# To prevent deletion of user configuration lines in config.txt, users can include an inline comment immediately after each configuration line using the specified word.
# However, it is important to note that conflicting configurations can happen, potentially impacting the kernel's loading process or causing harm to BlueOS.
CONFIG_USER_PROTECTION_WORD = "custom"

config_file = None
cmdline_file = None


class CpuType(str, Enum):
    PI4 = "Raspberry Pi 4 (BCM2711)"
    PI5 = "Raspberry Pi 5 (BCM2712)"
    Other = "Other"


class HostOs(str, Enum):
    Bookworm = "Debian(Raspberry Pi OS?) 12 (Bookworm)"
    Bullseye = "Debian(Raspberry Pi OS?) 11 (Bullseye)"
    Other = "Other"


def get_cpu_type() -> CpuType:
    with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
        for line in f:
            if "Raspberry Pi 4" in line:
                return CpuType.PI4
            if "Raspberry Pi 5" in line:
                return CpuType.PI5
    return CpuType.Other


def get_host_os() -> HostOs:
    os_release = load_file("/etc/os-release")
    if "bookworm" in os_release:
        return HostOs.Bookworm
    if "bullseye" in os_release:
        return HostOs.Bullseye
    return HostOs.Other


# Copyright 2016-2022 Paul Durivage
# Licensed under the Apache License, Version 2.0 (the "License");
# Based on: https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
def dict_merge(dct, merge_dct):
    for k, _v in merge_dct.items():
        if k in dct and isinstance(dct[k], dict) and isinstance(merge_dct[k], dict):  # noqa
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


def update_startup() -> bool:
    logger.info("Updating startup.json...")
    startup_path = os.path.join(appdirs.user_config_dir("bootstrap"), "startup.json")
    config = {}

    if not os.path.isfile(startup_path):
        logger.error(f"File: {startup_path}, does not exist, aborting.")
        return False

    with open(startup_path, mode="r", encoding="utf-8") as startup_file:
        config = json.load(startup_file)
        old_config = copy.deepcopy(config)
        dict_merge(config, DELTA_JSON)
        if old_config == config:
            # Don't need to apply or restart if the content is the same
            return False

    with open(startup_path, mode="w", encoding="utf-8") as startup_file:
        result = json.dumps(config, indent=4, sort_keys=True)
        startup_file.write(result)

        # Patch applied and system needs to be restarted for it to take effect
        return True


def boot_config_get_or_append_session(config_content: List[str], session_name: str) -> Tuple[int, int]:
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    session_match_pattern = r"^\[" + session_name + r"\].*$"
    session_start_line_number = next(
        (i for (i, line) in enumerate(config_content) if re.match(session_match_pattern, line, regex_flags)), None
    )
    if session_start_line_number is None:
        config_content.append(f"\n[{session_name}]")
        session_start_line_number = len(config_content)

    any_session_match_pattern = r"^\[.*\].*$"
    session_end_line_number = next(
        (
            (i + session_start_line_number + 1)
            for (i, line) in enumerate(config_content[session_start_line_number + 1 :])
            if line == "" or re.match(any_session_match_pattern, line, regex_flags)
        ),
        None,
    )
    if session_end_line_number is None:
        session_end_line_number = len(config_content)

    return (session_start_line_number, session_end_line_number)


def boot_config_add_configuration_at_session(config_content: List[str], config: str, session_name: str) -> None:
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    (session_start, session_end) = boot_config_get_or_append_session(config_content, session_name)

    session_content = config_content[session_start:session_end]
    config_already_exists = any(
        session_content for session_content in session_content if re.match(config, session_content, regex_flags)
    )
    if not config_already_exists:
        config_content.insert(session_start + 1, config)


def boot_config_filter_conflicting_configuration_at_session(
    config_content: List[str], config_pattern_match: str, config: str, session_name: str
) -> List[str]:
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    (session_start, session_end) = boot_config_get_or_append_session(config_content, session_name)

    return [
        line
        for (i, line) in enumerate(config_content)
        if (
            # If it's not protected
            re.match(f"^.*#.*{CONFIG_USER_PROTECTION_WORD}.*$", line, regex_flags)
            # Then remove the conflicting configuration...
            or not (
                re.match(config_pattern_match, line, regex_flags)
                # ...except...
                and not (
                    # ...if it's the correct one....
                    re.match(f"^{config}.*$", line, regex_flags)
                    # ...and lives inside the correct session.
                    and (session_start < i < session_end)
                )
            )
        )
    ]


def load_file(file_name) -> str:
    command = f'cat "{file_name}"'
    return run_command(command, False).stdout


def hardlink_exists(file_name: str) -> bool:
    command = f"[ -f '{file_name}' ] && [ $(stat -c '%h' '{file_name}') -gt 1 ]"
    return run_command(command, False).returncode == 0


def create_hard_link(source_file_name: str, destination_file_name: str) -> bool:
    command = f"sudo rm -rf {destination_file_name}; sudo ln {source_file_name} {destination_file_name}"
    return run_command(command, False).returncode == 0


def boot_cmdfile_add_modules(cmdline_content: List[str], config_key: str, desired_config: List[str]):
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    # Get each configs line indexes, if any
    config_indexes = [i for i, line in enumerate(cmdline_content) if re.match(f"^{config_key}=.*", line, regex_flags)]

    # Combine all config lines into a single one, starting from desired configs
    first_config_line = None
    for config_index in config_indexes:
        config_line = cmdline_content[config_index].split(f"{config_key}=")[-1].split(",")

        desired_config.extend([config for config in config_line if config not in desired_config])

        if first_config_line is None:
            first_config_line = config_index
        else:
            cmdline_content.remove(cmdline_content[config_index])

    # Replace the first configs line with the combined, append if none
    if first_config_line:
        cmdline_content[first_config_line] = f"{config_key}=" + ",".join(desired_config)
    else:
        config_line = f"{config_key}=" + ",".join(desired_config)
        cmdline_content.append(config_line)


def boot_cmdfile_add_config(cmdline_content: List[str], config_key: str, config_value: str):
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    # Get each configs line indexes, if any
    config_indexes = [
        i
        for i, line in enumerate(cmdline_content)
        if re.match(f"^{config_key}={config_value}(,.*)*$", line, regex_flags)
    ]

    found = False
    config_line = f"{config_key}={config_value}"
    for config_index in config_indexes:
        if not found:
            if config_value == cmdline_content[config_index].split(f"{config_key}=")[-1]:
                found = True
                continue

            cmdline_content[config_index] = config_line
            found = True
        else:
            cmdline_content.remove(cmdline_content[config_index])

    if not found:
        config_line = f"{config_key}={config_value}"
        cmdline_content.append(config_line)


def update_cgroups() -> bool:
    logger.info("Running cgroup update..")
    if cmdline_file is None:
        logging.warning("cmdline.txt not found. skipping cgroups update")
        return False
    cmdline_content = load_file(cmdline_file).replace("\n", "").split(" ")
    unpatched_cmdline_content = cmdline_content.copy()

    # Add the dwc2 module configuration to enable USB OTG as ethernet adapter
    cgroups = [
        ("cgroup_enable", "cpuset"),
        ("cgroup_memory", "1"),
        ("cgroup_enable", "memory"),
    ]
    for (config_key, config_value) in cgroups:
        boot_cmdfile_add_config(cmdline_content, config_key, config_value)

    # Don't need to apply or restart if the content is the same
    if unpatched_cmdline_content == cmdline_content:
        return False

    # Make a backup file before modifying the original one
    cmdline_content_str = " ".join(cmdline_content)
    backup_identifier = "before_update_cgroups"
    save_file(cmdline_file, cmdline_content_str, backup_identifier)

    # Patch applied and system needs to be restarted for it to take effect
    return True


def update_dwc2() -> bool:
    logger.info("Running dwc2 update..")

    if config_file is None:
        logging.warning("config.txt not found. skipping dwc2 update")
        return False
    if cmdline_file is None:
        logging.warning("cmdline.txt not found. skipping dwc2 update")
        return False

    config_content = load_file(config_file).splitlines()
    unpatched_config_content = config_content.copy()

    # Add dwc2 overlay in pi4 section if it doesn't exist
    dwc2_overlay_config = "dtoverlay=dwc2,dr_mode=otg"
    pi4_session_name = "pi4"
    boot_config_add_configuration_at_session(config_content, dwc2_overlay_config, pi4_session_name)

    # Remove any unprotected and conflicting dwc2 overlay configuration
    dwc2_overlay_match_pattern = "^[#]*dtoverlay=dwc2.*$"
    config_content = boot_config_filter_conflicting_configuration_at_session(
        config_content, dwc2_overlay_match_pattern, dwc2_overlay_config, pi4_session_name
    )

    # Save if needed, with backup
    backup_identifier = "before_update_dwc2"
    if unpatched_config_content != config_content:
        config_content_str = "\n".join(config_content)
        save_file(config_file, config_content_str, backup_identifier)

    cmdline_content = load_file(cmdline_file).replace("\n", "").split(" ")
    unpatched_cmdline_content = cmdline_content.copy()

    # Add the dwc2 module configuration to enable USB OTG as ethernet adapter
    boot_cmdfile_add_modules(cmdline_content, "modules-load", ["dwc2", "g_ether"])

    # Don't need to apply if the content is the same, restart if the above part requires
    if unpatched_cmdline_content == cmdline_content:
        return unpatched_config_content != config_content

    # Make a backup file before modifying the original one
    cmdline_content_str = " ".join(cmdline_content)
    save_file(cmdline_file, cmdline_content_str, backup_identifier)

    # Patch applied and system needs to be restarted for it to take effect
    return True


def update_navigator_overlays() -> bool:
    logger.info("Running Navigator overlays update..")

    if config_file is None:
        logging.warning("config.txt not found. skipping overlays update")
        return False
    config_content = load_file(config_file).splitlines()
    unpatched_config_content = config_content.copy()

    navigator_configs_with_match_patterns = [
        ("enable_uart=1", "^enable_uart=.*"),
        ("dtoverlay=uart1", "^dtoverlay=uart1.*"),
        ("dtoverlay=uart3", "^dtoverlay=uart3.*"),
        ("dtoverlay=uart4", "^dtoverlay=uart4.*"),
        ("dtoverlay=uart5", "^dtoverlay=uart5.*"),
        ("dtparam=i2c_vc=on", "^dtparam=i2c_vc=.*"),
        ("dtoverlay=i2c1", "^dtoverlay=i2c1.*"),
        ("dtparam=i2c_arm_baudrate=1000000", "^dtparam=i2c_arm_baudrate.*"),
        ("dtoverlay=i2c4,pins_6_7,baudrate=1000000", "^dtoverlay=i2c4.*"),
        ("dtoverlay=i2c6,pins_22_23,baudrate=400000", "^dtoverlay=i2c6.*"),
        ("dtparam=spi=on", "^dtparam=spi=.*"),
        ("dtoverlay=spi0-led", "^dtoverlay=spi0.*"),
        ("dtoverlay=spi1-3cs", "^dtoverlay=spi1.*"),
        ("gpio=11,24,25=op,pu,dh", "^gpio=.*((11|24|25),?)+.*"),
        ("gpio=37=op,pd,dl", "^gpio=.*37.*"),
    ]
    navigator_configs_with_match_patterns.reverse()

    pi4_session_name = "pi4"
    for (config, config_match_pattern) in navigator_configs_with_match_patterns:
        # Add each navigator configuration to pi4 session
        boot_config_add_configuration_at_session(config_content, config, pi4_session_name)

        # Remove any unprotected and conflicting configuration of peripherals
        config_content = boot_config_filter_conflicting_configuration_at_session(
            config_content, config_match_pattern, config, pi4_session_name
        )

    # Don't need to apply or restart if the content is the same
    if unpatched_config_content == config_content:
        return False

    # Save if needed, with backup
    backup_identifier = "before_update_navigator_overlays"
    config_content_str = "\n".join(config_content)
    save_file(config_file, config_content_str, backup_identifier)

    # Patch applied and system needs to be restarted for it to take effect
    return True


def create_dns_conf_host_link() -> bool:
    """This patch creates a hard link of /etc/resolv.conf as /etc/resolv.conf.host, to be used as
    a binding with an fixed file-descriptor, which is neccessary for docker bindings if the original
    file is being replaced by some system service, like is the case when dnsmasq or dhcpcd changes
    the /etc/resolf.conf file."""
    logger.info("Creating dns link with host...")
    original_resolv_conf_file = "/etc/resolv.conf"
    resolv_conf_file_host_link = "/etc/resolv.conf.host"
    if hardlink_exists(resolv_conf_file_host_link):
        return False

    # Creates a static reoslv conf to allow docker binds
    if not create_hard_link(original_resolv_conf_file, resolv_conf_file_host_link):
        logger.error("Failed to apply patch")
        return False

    # Patch applied and system needs to be restarted for it to take effect
    return True


def ensure_nginx_permissions() -> bool:
    # ensure nginx can read the userdata directory
    logger.info("Ensuring nginx permissions...")
    command = "sudo chown -R www-data:www-data /usr/blueos/userdata"
    run_command(command, False)

    # This patch doesn't require restart to take effect
    return False


def ensure_user_data_structure_is_in_place() -> bool:
    # ensures we have all base folders in userdata
    logger.info("Ensuring userdata structure is in place...")
    commands = [
        "sudo mkdir -p /usr/blueos/userdata/images/vehicle",
        "sudo mkdir -p /usr/blueos/userdata/images/logo",
        "sudo mkdir -p /usr/blueos/userdata/styles",
    ]
    for command in commands:
        run_command(command, False)

    # This patch doesn't require restart to take effect
    return False


def run_command_is_working():
    output = run_command("uname -a", check=False)
    if output.returncode != 0:
        logger.error(output)
        return False
    return True


def fix_ssh_ownership() -> bool:
    logger.info("Fixing .ssh ownership...")
    command = "sudo chown -R $USER:$USER $HOME/.ssh"
    run_command(command, False)
    return False


def main() -> int:
    start = time.time()
    # check if boot_loop_detector exists
    if os.path.isfile(BOOT_LOOP_DETECTOR):
        logger.warning("It seems we the startup patches were just applied on the last boot. skipping patches...")
        return
    current_git_version = os.getenv("GIT_DESCRIBE_TAGS")
    match = re.match(r"(?P<tag>.*)-(?P<commit_number>\d+)-(?P<commit_hash>[a-z0-9]+)", current_git_version)
    tag, commit_number, commit_hash = match["tag"], match["commit_number"], match["commit_hash"]
    logger.info(f"Running BlueOS: {tag=}, {commit_number=}, {commit_hash=}")
    # pylint: disable=global-statement
    global config_file
    global cmdline_file
    config_file = locate_file(["/boot/firmware/config.txt", "/boot/config.txt"])
    logger.info(f"config.txt found at {config_file}")
    cmdline_file = locate_file(["/boot/firmware/cmdline.txt", "/boot/cmdline.txt"])
    logger.info(f"cmdline.txt found at {cmdline_file}")

    if not run_command_is_working():
        logger.error("Critical error: Something is wrong with the host computer, run_command is not working.")
        logger.error("Ignoring host computer configuration for now.")
        return 0

    host_os = get_host_os()
    logger.info(f"Host OS: {host_os}")
    host_cpu = get_cpu_type()
    logger.info(f"Host CPU: {host_cpu}")

    # TODO: parse tag as semver and check before applying patches
    patches_to_apply = [
        update_startup,
        ensure_user_data_structure_is_in_place,
        ensure_nginx_permissions,
        create_dns_conf_host_link,
        fix_ssh_ownership(),
    ]

    # this will always be pi4 as pi5 is not supported
    if host_os == HostOs.Bullseye:
        patches_to_apply.extend([update_navigator_overlays])

    if host_cpu == CpuType.PI4 or CpuType.PI5:
        patches_to_apply.extend(
            [
                update_cgroups,
                update_dwc2,
            ]
        )

    logger.info("The following patches will be applied if needed:")
    for patch in patches_to_apply:
        logger.info(patch.__name__)

    patches_requiring_restart = [patch.__name__ for patch in patches_to_apply if patch()]
    if patches_requiring_restart:
        logger.warning("The system will restart in 10 seconds because the following applied patches required restart:")
        for patch in patches_requiring_restart:
            logger.info(patch)
        # pylint: disable-next=consider-using-with,unspecified-encoding
        open(BOOT_LOOP_DETECTOR, "w").close()
        time.sleep(10)
        run_command("sudo reboot", False)
        time.sleep(600)  # we are already rebooting anyway. but we don't want the other services to come up

    logger.info(f"All patches applied successfully in { time.time() - start} seconds")
    return 0


if __name__ == "__main__":
    main()
    os.remove(BOOT_LOOP_DETECTOR)
