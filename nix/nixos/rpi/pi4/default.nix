# Raspberry Pi 4 / CM4 with a Navigator hat, mirroring install/boards/bcm_27xx.sh

{
  lib,
  ...
}:
let
  inherit (lib) mkDefault;
in
{
  imports = [ ../common.nix ];

  hardware.raspberry-pi.configtxt = {
    settings.pi4 = {
      dtparam = [
        "i2c_vc=on"
        "i2c_arm_baudrate=1000000"
        "spi=on"
      ];
      enable_uart = mkDefault true;
      gpio = mkDefault [
        "11,24,25=op,pu,dh"
        "37=op,pd,dl"
      ];
    };

    deviceTreeOverlays.pi4 = [
      { uart1 = { }; }
      { uart3 = { }; }
      { uart4 = { }; }
      { uart5 = { }; }
      { i2c1 = { }; }
      {
        i2c4 = {
          pins_6_7 = true;
          baudrate = 1000000;
        };
      }
      { i2c6.baudrate = 400000; }
      { spi0-led = { }; }
      { spi1-3cs = { }; }
      { navigator-eeprom = { }; }
      { dwc2.dr_mode = "otg"; }
    ];
  };

  hardware.raspberry-pi.configtxt.settings.cm4.otg_mode = lib.mkForce null;

  hardware.i2c.enable = mkDefault true;

  boot.kernelParams = [ "8250.nr_uarts=1" ];

  boot.kernelModules = [
    "i2c-dev"
    "i2c-bcm2835"
    "bcm2835-v4l2"
    "dwc2"
    "g_ether"
    "slcan"
  ];
}
