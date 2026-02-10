#!/usr/bin/env python
import configparser
import copy
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import List, Tuple

import appdirs
from commonwealth.utils.commands import load_file, locate_file, run_command, save_file
from commonwealth.utils.general import CpuType, HostOs, get_cpu_type, get_host_os
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
            "/etc/blueos": {"bind": "/etc/blueos", "mode": "rw"},
            "/etc/dhcpcd.conf": {"bind": "/etc/dhcpcd.conf", "mode": "rw"},
            "/etc/machine-id": {"bind": "/etc/machine-id", "mode": "ro"},
            "/etc/resolv.conf.host": {"bind": "/etc/resolv.conf.host", "mode": "ro"},
            "/home/pi/.ssh": {"bind": "/home/pi/.ssh", "mode": "rw"},
            "/home/pi/.docker": {"bind": "/home/pi/.docker", "mode": "rw"},
            "/root/.docker": {"bind": "/root/.docker", "mode": "rw"},
            "/root/.majortom": {"bind": "/root/.majortom", "mode": "rw"},
            "/run/udev": {"bind": "/run/udev", "mode": "ro"},
            "/sys/": {"bind": "/sys/", "mode": "rw"},
            "/usr/blueos/bin": {"bind": "/usr/blueos/bin", "mode": "rw"},
            "/usr/blueos/extensions": {"bind": "/usr/blueos/extensions", "mode": "rw"},
            "/usr/blueos/userdata": {"bind": "/usr/blueos/userdata", "mode": "rw"},
            "/var/run/wpa_supplicant": {"bind": "/var/run/wpa_supplicant", "mode": "rw"},
            "/var/run/dbus": {"bind": "/var/run/dbus", "mode": "rw"},
            "/run/log/journal": {"bind": "/run/log/journal", "mode": "ro"},
            "/var/log/journal": {"bind": "/var/log/journal", "mode": "ro"},
        }
    }
}

# To prevent deletion of user configuration lines in config.txt, users can include an inline comment immediately after each configuration line using the specified word.
# However, it is important to note that conflicting configurations can happen, potentially impacting the kernel's loading process or causing harm to BlueOS.
CONFIG_USER_PROTECTION_WORD = "custom"

config_file = None
cmdline_file = None

disabled_patches = [entry.strip() for entry in os.getenv("BLUEOS_DISABLE_PATCHES", "").split(",")]

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


def boot_config_get_or_append_section(config_content: List[str], section_name: str) -> Tuple[int, int]:
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    section_match_pattern = r"^\[" + section_name + r"\].*$"
    section_start_line_number = next(
        (i for (i, line) in enumerate(config_content) if re.match(section_match_pattern, line, regex_flags)), None
    )
    if section_start_line_number is None:
        config_content.append(f"\n[{section_name}]")
        section_start_line_number = len(config_content)

    any_section_match_pattern = r"^\[.*\].*$"
    section_end_line_number = next(
        (
            (i + section_start_line_number + 1)
            for (i, line) in enumerate(config_content[section_start_line_number + 1 :])
            if line == "" or re.match(any_section_match_pattern, line, regex_flags)
        ),
        None,
    )
    if section_end_line_number is None:
        section_end_line_number = len(config_content)

    return (section_start_line_number, section_end_line_number)


def boot_config_add_configuration_at_section(config_content: List[str], config: str, section_name: str) -> None:
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    (section_start, section_end) = boot_config_get_or_append_section(config_content, section_name)

    section_content = config_content[section_start:section_end]
    config_already_exists = any(
        section_content for section_content in section_content if re.match(config, section_content, regex_flags)
    )
    if not config_already_exists:
        config_content.insert(section_start + 1, config)


def boot_config_remove_section(config_content: List[str], section_name: str) -> None:
    (section_start, section_end) = boot_config_get_or_append_section(config_content, section_name)
    del config_content[section_start:section_end]


def boot_config_get_available_section(config_content: List[str]) -> List[str]:
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    section_match_pattern = r"^\[(?P<section>\w+)\].*$"

    section = []
    for line in config_content:
        match = re.match(section_match_pattern, line, regex_flags)
        if match:
            section.append(match.group("section"))

    return section


def boot_config_filter_conflicting_configuration_at_section(
    config_content: List[str], config_pattern_match: str, config: str, section_name: str
) -> List[str]:
    regex_flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    (section_start, section_end) = boot_config_get_or_append_section(config_content, section_name)

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
                    # ...and lives inside the correct section.
                    and (section_start < i < section_end)
                )
            )
        )
    ]


def hardlink_exists(file_name: str) -> bool:
    command = f"[ -f '{file_name}' ] && [ $(stat -c '%h' '{file_name}') -gt 1 ]"
    return run_command(command, False).returncode == 0


def create_hard_link(source_file_name: str, destination_file_name: str) -> bool:
    command = f"sudo rm -rf {destination_file_name}; sudo ln {source_file_name} {destination_file_name}"
    return run_command(command, False).returncode == 0


def boot_cmdline_add_modules(cmdline_content: List[str], config_key: str, desired_config: List[str]):
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


def boot_cmdline_add_config(cmdline_content: List[str], config_key: str, config_value: str):
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
        boot_cmdline_add_config(cmdline_content, config_key, config_value)

    # Don't need to apply or restart if the content is the same
    if unpatched_cmdline_content == cmdline_content:
        return False

    # Make a backup file before modifying the original one
    cmdline_content_str = " ".join(cmdline_content)
    backup_identifier = "before_update_cgroups"
    save_file(cmdline_file, cmdline_content_str, backup_identifier)

    # Patch applied and system needs to be restarted for it to take effect
    return True


def update_i2c4_symlink() -> bool:
    logger.info("Running i2c4 symlink update..")
    i2c4_symlink = "/dev/i2c-4"
    i2c4_device = "/dev/i2c-3"
    if os.path.exists(i2c4_symlink):
        return False
    if not os.path.exists(i2c4_device):
        return False
    command = f"sudo ln -s {i2c4_device} {i2c4_symlink}"
    run_command(command, False)
    return False  # This patch doesn't require restart to take effect


def revert_update_dwc2() -> bool:
    """
    Removes dwc2 configuration from cmdline.txt
    This was being wrongly applied on Pi3 due to a bad host_cpu check.
    """

    # Remove dwc2 module configuration from cmdline
    unpatched_cmdline_content = load_file(cmdline_file).replace("\n", "").split(" ")
    cmdline_content = []
    for item in unpatched_cmdline_content:
        if "dwc2" not in item and "g_ether" not in item:
            cmdline_content.append(item)

    # Save if needed, with backup
    if unpatched_cmdline_content == cmdline_content:
        return False
    save_file(cmdline_file, " ".join(cmdline_content), "before_revert_update_dwc2")

    # Patch applied and system needs to be restarted for it to take effect
    return True


def clean_config_pi3() -> bool:
    """
    Removes any tagged configurations from config.txt on Pi3
    This was being wrongly applied due to a bad host_cpu check.
    """
    config_content = load_file(config_file).splitlines()
    unpatched_config_content = config_content.copy()

    # Remove unwanted sections
    # For a Pi3, we want to keep certain sections (see https://www.raspberrypi.com/documentation/computers/config_txt.html#model-filters)
    sections_to_keep = ["all", "pi3", "pi3+", "cm3", "cm3+"]
    current_section = boot_config_get_available_section(config_content)
    for section in current_section:
        if section not in sections_to_keep:
            boot_config_remove_section(config_content, section)

    # Save if needed, with backup
    backup_identifier = "before_clean_config_pi3"
    if unpatched_config_content == config_content:
        return False
    config_content_str = "\n".join(config_content)
    save_file(config_file, config_content_str, backup_identifier)

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

    section_name = "pi4" if get_cpu_type() == CpuType.PI4 else "pi5"
    # Add dwc2 overlay in pi4 or pi5 section if it doesn't exist
    if get_cpu_type() == CpuType.PI4:
        dwc2_overlay_config = "dtoverlay=dwc2,dr_mode=otg"
    elif get_cpu_type() == CpuType.PI5:
        dwc2_overlay_config = "dtoverlay=dwc2,dr_mode=peripheral"
    else:
        logger.error("Unsupported CPU type for dwc2 update")
        return False

    boot_config_add_configuration_at_section(config_content, dwc2_overlay_config, section_name)

    # Remove any unprotected and conflicting dwc2 overlay configuration
    dwc2_overlay_match_pattern = "^[#]*dtoverlay=dwc2.*$"
    config_content = boot_config_filter_conflicting_configuration_at_section(
        config_content, dwc2_overlay_match_pattern, dwc2_overlay_config, section_name
    )

    # Save if needed, with backup
    backup_identifier = "before_update_dwc2"
    if unpatched_config_content != config_content:
        config_content_str = "\n".join(config_content)
        save_file(config_file, config_content_str, backup_identifier)

    cmdline_content = load_file(cmdline_file).replace("\n", "").split(" ")
    unpatched_cmdline_content = cmdline_content.copy()

    # Add the dwc2 module configuration to enable USB OTG as ethernet adapter
    boot_cmdline_add_modules(cmdline_content, "modules-load", ["dwc2", "g_ether"])

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

    pi4_section_name = "pi4"
    for (config, config_match_pattern) in navigator_configs_with_match_patterns:
        # Add each navigator configuration to pi4 section
        boot_config_add_configuration_at_section(config_content, config, pi4_section_name)

        # Remove any unprotected and conflicting configuration of peripherals
        config_content = boot_config_filter_conflicting_configuration_at_section(
            config_content, config_match_pattern, config, pi4_section_name
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


def ensure_ipv6_disabled() -> bool:
    required_entries = [
        (
            "net.ipv6.conf.all.disable_ipv6=1",
            re.compile(r"^\s*#?\s*net\.ipv6\.conf\.all\.disable_ipv6\s*=\s*1", re.MULTILINE),
        ),
        (
            "net.ipv6.conf.default.disable_ipv6=1",
            re.compile(r"^\s*#?\s*net\.ipv6\.conf\.default\.disable_ipv6\s*=\s*1", re.MULTILINE),
        ),
        (
            "net.ipv6.conf.lo.disable_ipv6=1",
            re.compile(r"^\s*#?\s*net\.ipv6\.conf\.lo\.disable_ipv6\s*=\s*1", re.MULTILINE),
        ),
    ]

    sysctl_config_path = "/etc/sysctl.conf"
    sysctl_config_file = load_file(sysctl_config_path)

    # Make sure every required entry is in the file and uncommented
    needs_update = False
    for (desired, pattern) in required_entries:
        entry_match = pattern.search(sysctl_config_file)
        if entry_match:
            line_result = entry_match.group(0)
            if "#" in line_result:
                sysctl_config_file = pattern.sub(desired, sysctl_config_file)
                needs_update = True
        else:
            sysctl_config_file += f"\n{desired}\n"
            needs_update = True

    if needs_update:
        backup_identifier = "before_no_ipv6"
        save_file(sysctl_config_path, sysctl_config_file, backup_identifier)

    return needs_update


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


def fix_wpa_service() -> bool:
    """
    Adds -i wlan0 and -c /etc/wpa_supplicant/wpa_supplicant.conf to the wpa_supplicant service
    This is needed to make the service actually consume the .conf file with update_config=1
    """
    logger.info("checking wpa_supplicant service...")
    file_path = "/lib/systemd/system/wpa_supplicant.service"
    original_file = load_file(file_path)
    # extract execstart line
    execstart_line = next((line for line in original_file.splitlines() if line.startswith("ExecStart=")), None)
    if execstart_line and "-i " in execstart_line and "-c " in execstart_line:
        # the settings are there. not our job to check if they are the ones we want
        return False
    new_execstart_line = execstart_line
    if "-i " not in execstart_line:
        new_execstart_line = new_execstart_line + " -i wlan0"
    if "-c " not in execstart_line:
        new_execstart_line = new_execstart_line + " -c /etc/wpa_supplicant/wpa_supplicant.conf"
    original_file = original_file.replace(execstart_line, new_execstart_line)
    save_file(file_path, original_file, "before_fix_wpa_service")
    return True


def configure_network_manager() -> bool:
    """
    Ensures NetworkManager.conf has [main] section with dns=none set if dns is not already configured
    """
    logger.info("Configuring NetworkManager DNS settings...")
    file_path = "/etc/NetworkManager/NetworkManager.conf"

    config = configparser.ConfigParser()

    # Try to read existing file
    result = run_command(f"test -f {file_path} && cat {file_path}", check=False)
    if result.returncode != 0:
        # File doesn't exist, create with template
        content = """[main]
plugins=ifupdown,keyfile
dns=none

[ifupdown]
managed=false

[device]
wifi.scan-rand-mac-address=no

[keyfile]
unmanaged-devices=interface:eth0;interface:usb0
"""
        run_command(f"echo '{content}' | sudo tee {file_path}", check=False)
        return True

    config.read_string(result.stdout)

    # Check if we need to make changes
    if ("main" in config.sections() and "dns" in config["main"]) and (
        "keyfile" in config.sections() and "unmanaged-devices" in config["keyfile"]
    ):
        return False

    # Add our settings if needed
    if "main" not in config:
        config.add_section("main")
    if "dns" not in config["main"]:
        config["main"]["dns"] = "none"

    # Ensure keyfile section exists and has unmanaged-devices
    if "keyfile" not in config:
        config.add_section("keyfile")
    if "unmanaged-devices" not in config["keyfile"]:
        config["keyfile"]["unmanaged-devices"] = "interface:eth0;interface:usb0"

    # Write back if changes were made
    content = ""
    for section in config.sections():
        content += f"[{section}]\n"
        for key, value in config[section].items():
            content += f"{key}={value}\n"
        content += "\n"

    run_command(f"echo '{content}' | sudo tee {file_path}", check=False)
    return True


def check_available_space(required_mb: int) -> bool:
    """Check if there is enough space in disk for the required megabytes"""
    try:
        stats = os.statvfs("/")
        available_mb = stats.f_bavail * stats.f_frsize / (1024 * 1024)
        return available_mb >= required_mb
    except Exception as exception:
        logger.error(f"Failed to check available space: {exception}")
        return False


def update_swap_size() -> bool:
    """Updates the swap size if there is enough space available"""
    logger.info("Checking and updating swap size...")

    swap_conf_file = "/etc/dphys-swapfile"

    if check_available_space(1300):
        desired_size = 1024
    elif check_available_space(800):
        desired_size = 512
    else:
        logger.warning("Not enough space to increase swap size")
        return False

    try:
        content = load_file(swap_conf_file)

        match = re.search(r"^CONF_SWAPSIZE=(\d+)", content, re.MULTILINE)
        if not match:
            logger.error("Could not find CONF_SWAPSIZE in configuration")
            return False

        current_size = int(match.group(1))
        if current_size >= desired_size:
            logger.info(f"Current swap size ({current_size}MB) is already >= desired size ({desired_size}MB)")
            return False

        new_content = re.sub(r"^CONF_SWAPSIZE=\d+", f"CONF_SWAPSIZE={desired_size}", content, flags=re.MULTILINE)

        backup_identifier = "before_update_swap"
        save_file(swap_conf_file, new_content, backup_identifier)

        logger.info(f"Updated swap size from {current_size}MB to {desired_size}MB")
        return True

    except Exception as exception:
        logger.error(f"Failed to update swap size: {exception}")
        return False


def setup_ssh() -> bool:
    logger.info("Setting up SSH...")
    # store the key in the docker .config volume
    key_path = Path("/root/.config/.ssh")
    private_key = key_path / "id_rsa"
    public_key = private_key.with_suffix(".pub")
    user = os.environ.get("SSH_USER", "pi")
    gid = int(os.environ.get("USER_GID", 1000))
    uid = int(os.environ.get("USER_UID", 1000))
    authorized_keys = Path(f"/home/{user}/.ssh/authorized_keys")

    try:
        key_path.mkdir(parents=True, exist_ok=True)
        # check if id_rsa.pub exists, creates a new one if it doesnt
        if not public_key.is_file():
            subprocess.run(["ssh-keygen", "-t", "rsa", "-f", private_key, "-q", "-N", ""], check=True)
            logger.info("Generated new SSH key pair")

        public_key_text = public_key.read_text("utf-8")
        # add id_rsa.pub to authorized_keys if not there already
        try:
            authorized_keys_text = authorized_keys.read_text("utf-8")
        except FileNotFoundError:
            logger.info(f"File does not exist: {authorized_keys}")
            authorized_keys_text = ""

        if public_key_text not in authorized_keys_text:
            if not authorized_keys_text.endswith("\n"):
                authorized_keys_text += "\n"
            authorized_keys_text += public_key_text
            authorized_keys.write_text(authorized_keys_text, "utf-8")
            logger.info("Added public key to authorized_keys")

        os.chown(authorized_keys, uid, gid)
        authorized_keys.chmod(0o600)
        return True
    except Exception as sshError:
        logger.error(f"Error setting up ssh: {sshError}")
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
        ("startup", update_startup),
        ("userdata", ensure_user_data_structure_is_in_place),
        ("nginx", ensure_nginx_permissions),
        ("dns", create_dns_conf_host_link),
        ("ssh", fix_ssh_ownership),
        ("noIPV6", ensure_ipv6_disabled),
        ("swap", update_swap_size),
        ("cgroups", update_cgroups),
    ]

    if host_cpu == CpuType.PI3:
        patches_to_apply.extend(
            [
                ("revert_update_dwc2", revert_update_dwc2),
                ("clean_config_pi3", clean_config_pi3),
            ]
        )

    if host_cpu == CpuType.PI4:
        patches_to_apply.extend([("navigator", update_navigator_overlays)])

    if host_cpu in [CpuType.PI4, CpuType.PI5]:
        patches_to_apply.extend(
            [
                ("dwc2", update_dwc2),
                ("i2c4", update_i2c4_symlink),
            ]
        )
    if host_os == HostOs.Bookworm:
        patches_to_apply.extend([("wpa", fix_wpa_service), ("networkmanager", configure_network_manager)])

    logger.info("The following patches will be applied if needed:")
    for name, patch in patches_to_apply:
        logger.info(f"{name} {'(suppressed)' if name in disabled_patches else '(enabled)'}")

    enabled_patches = [(name, patch) for name, patch in patches_to_apply if name not in disabled_patches]

    patches_requiring_restart = [name for name, patch in enabled_patches if patch()]
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
    try:
        setup_ssh()
    except Exception as error:
        logger.error(f"An error occurred while setting up ssh: {error}")
    try:
        main()
        if os.path.exists(BOOT_LOOP_DETECTOR):
            os.remove(BOOT_LOOP_DETECTOR)
    except Exception as error:
        logger.error(f"An error occurred while applying patches: {error}")
