# U-Boot for the Raspberry Pis, with the boot count limit enabled so a
# generation that never reaches userspace can be abandoned by the bootloader
# alone. nixpkgs' ubootRaspberryPiAarch64 has no bootcount support.
#
# The counter lives in a file on the firmware FAT partition rather than in the
# U-Boot environment: a missing file reads as 0, so deleting it disarms the
# fallback without needing a write, and a failed FAT write cannot corrupt the
# environment the board needs to boot at all.
{
  ubootRaspberryPiAarch64,
}:
ubootRaspberryPiAarch64.overrideAttrs (old: {
  pname = "uboot-rpi-bootcount";

  # buildUBoot appends extraConfig to .config without running olddefconfig, and
  # the bootcount backend is a choice: the generic default has to be deselected
  # explicitly or the two entries collide.
  extraConfig = (old.extraConfig or "") + ''
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
