{
  lib,
  modulesPath,
  pkgs,
  ...
}:
{
  imports = [
    (modulesPath + "/profiles/qemu-guest.nix")
    (modulesPath + "/virtualisation/disk-image.nix")
  ];

  # Enable Wi-Fi simulation
  boot.kernelModules = [ "mac80211_hwsim" ];
  boot.extraModprobeConfig = ''
    options mac80211_hwsim radios=6 channels=2
    options cfg80211 ieee80211_regdom=US
  '';
  hardware.wirelessRegulatoryDatabase = true;

  environment.systemPackages = with pkgs; [
    dnsmasq
    hostapd
    iw
  ];

  networking.networkmanager = {
    enable = lib.mkDefault true;
    unmanaged = [
      "interface-name:usb0"
      "interface-name:uap0"
    ];
  };
  networking.wireless.interfaces = [ "wlan0" ];

  virtualisation.diskSize = 8192;

  services.openssh.enable = lib.mkDefault true;
  users.users.pi = {
    isNormalUser = true;
    initialPassword = "raspberry";
    extraGroups = [
      "wheel"
      "docker"
      "podman"
      "video"
    ];
  };
  security.sudo.wheelNeedsPassword = lib.mkDefault false;

  # Do not modify this!
  system.stateVersion = "25.11";
}
