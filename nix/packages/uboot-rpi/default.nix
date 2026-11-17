# U-Boot for the Raspberry Pis.
#
# Three deviations from nixpkgs' ubootRaspberryPiAarch64:
#
#   - preboot is dropped. rpi_arm64_defconfig sets
#     PREBOOT="pci enum; usb start;", and main_loop runs preboot before the
#     bootdelay and before any boot target is tried, so USB and PCI enumeration
#     is paid on every boot even though the card boots from mmc. boot_targets is
#     "mmc usb pxe dhcp" with mmc first, so the USB path is still reached when
#     the card itself has nothing bootable.
#
#   - bootdelay is 1 rather than 2. It is dead time before `bootflow scan`
#     starts, and 1 still leaves the autoboot interruptible.
#
#   - with `bootcount`, the boot count limit is enabled so a generation that
#     never reaches userspace can be abandoned by the bootloader alone. nixpkgs'
#     ubootRaspberryPiAarch64 has no bootcount support. Only useful when
#     rollback.nix is imported, since that is what writes the good.conf
#     altbootcmd boots and what clears the counter; without it the counter
#     climbs until the boot limit is passed and the board stops booting.
#
# The counter lives in a file on the firmware FAT partition rather than in the
# U-Boot environment: a missing file reads as 0, so deleting it disarms the
# fallback without needing a write, and a failed FAT write cannot corrupt the
# environment the board needs to boot at all.
{
  lib,
  ubootRaspberryPiAarch64,
  bootcount ? true,
}:
ubootRaspberryPiAarch64.overrideAttrs (old: {
  pname = if bootcount then "uboot-rpi-bootcount" else "uboot-rpi";

  # buildUBoot appends extraConfig to .config without running olddefconfig, and
  # the bootcount backend is a choice: the generic default has to be deselected
  # explicitly or the two entries collide.
  extraConfig =
    (old.extraConfig or "")
    + ''
      CONFIG_PREBOOT=""
      CONFIG_BOOTDELAY=1
    ''
    + lib.optionalString bootcount ''
      CONFIG_BOOTCOUNT_LIMIT=y
      # CONFIG_BOOTCOUNT_GENERIC is not set
      CONFIG_BOOTCOUNT_FS=y
      CONFIG_FAT_WRITE=y
      CONFIG_BOOTCOUNT_BOOTLIMIT=3
      CONFIG_BOOTCOUNT_ALTBOOTCMD="sysboot mmc 0:2 ext2 ''${pxefile_addr_r} /boot/extlinux/good.conf"
      CONFIG_SYS_BOOTCOUNT_FS_NAME="/bootcount"
      # BOOTCOUNT_FS has no default address. The driver maps the counter through
      # it before writing; 0x05500000 is pxefile_addr_r, which sysboot does not
      # touch until after the boot count has been read and reset.
      CONFIG_SYS_BOOTCOUNT_ADDR=0x05500000
    '';
})
