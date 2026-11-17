{
  config,
  lib,
  pkgs,
  blueos,
  ubootPackage,
  sdImageModule,
  ...
}:
let
  inherit (lib) mkDefault mkForce;

  install = "${blueos.passthru.src}/install";

  swapSize = 1024;

  firmware = pkgs.runCommand "raspberrypifw-navigator" { nativeBuildInputs = [ pkgs.dtc ]; } ''
    cp -r ${pkgs.raspberrypifw} $out
    chmod -R u+w $out
    dtc -@ -Hepapr -I dts -O dtb \
      -o $out/share/raspberrypi/boot/overlays/spi0-led.dtbo \
      ${install}/overlays/spi0-led.dts
    dtc -@ -Hepapr -I dts -O dtb \
      -o $out/share/raspberrypi/boot/overlays/navigator-eeprom.dtbo \
      ${install}/overlays/navigator-eeprom.dts
  '';
in
{
  imports = [ sdImageModule ];

  hardware.raspberry-pi.firmware = {
    package = mkDefault firmware;
    uboot.enable = mkDefault true;
    uboot.package = mkDefault ubootPackage;
  };

  fileSystems."/boot/firmware".options = mkForce [ "nofail" ];

  sdImage = {
    populateRootCommands = ''
      mkdir -p ./files/boot
      ${config.boot.loader.generic-extlinux-compatible.populateCmd} -c ${config.system.build.toplevel} -d ./files/boot
    '';
    compressImage = mkDefault true;
    firmwareSize = mkDefault 512;
  };

  image.baseName = mkDefault "blueos-${config.services.blueos.board}-${config.services.blueos.gitDescribe}";

  boot.supportedFilesystems = mkForce [
    "vfat"
    "ext4"
  ];
  boot.zfs.forceImportRoot = mkDefault false;

  boot.initrd.allowMissingModules = mkDefault true;

  swapDevices = [
    {
      device = "/var/swapfile";
      size = swapSize;
      priority = 10;
    }
  ];

  # Use fallocate instead of dd to reserve the swap contents
  # TODO: Remove once <https://github.com/NixOS/nixpkgs/pull/589996> is upstreamed
  systemd.services.mkswap-var-swapfile.script = mkForce ''
    if [[ "$(stat -c %s "$DEVICE" 2>/dev/null)" != "$(( ${toString swapSize} * 1024 * 1024 ))" ]]; then
      ${pkgs.util-linux}/bin/fallocate -l ${toString swapSize}M "$DEVICE"
      ${pkgs.util-linux}/bin/mkswap -L blueos-swap "$DEVICE"
    fi
  '';

  # Compressed swap in RAM in front of the swapfile
  zramSwap = {
    enable = mkDefault true;
    priority = mkDefault 100;
  };

  services.blueos = {
    enable = mkDefault true;
    package = mkDefault blueos;
    rollback.enable = mkDefault true;
  };

  documentation.enable = mkDefault false;

  # Do not modify this!
  system.stateVersion = "25.11";
}
