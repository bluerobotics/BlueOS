{
  blueos,
  lib,
  pkgs,
  ...
}:
let
  # Pinned so the suite does not depend on firmware.ardupilot.org at test time
  sitl = pkgs.fetchurl {
    url = "https://firmware.ardupilot.org/Sub/stable-4.5.3/SITL_x86_64_linux_gnu/ardusub";
    hash = "sha256-SCaEXmvlg57bw6TTDA8jE/fDfuYjrqHHTrfhnkC0+u0=";
  };

  firmwareDir = "/root/.config/ardupilot-manager/firmware";
in
{
  imports = [
    ./common.nix
    ../../modules/blueos
  ];

  image.efiSupport = false;

  services.blueos = {
    enable = true;
    package = lib.mkDefault blueos;
    rollback.enable = false;
  };

  systemd.tmpfiles.rules = [
    "C+ ${firmwareDir}/ardupilot_sitl_x86_64_linux_gnu 0755 root root - ${sitl}"
  ];
}
