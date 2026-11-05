{ modulesPath, pkgs, ... }:
{
  imports = [ (modulesPath + "/profiles/qemu-guest.nix") ];

  system.stateVersion = "26.05";
  networking.hostName = "blueos";
  boot.kernelParams = [ "console=ttyS0" ];

  # Enable the mac80211_hwsim module to simulate wifi radios
  boot.kernelModules = [ "mac80211_hwsim" ];
  boot.extraModprobeConfig = ''
    options mac80211_hwsim radios=6 channels=2
    options cfg80211 ieee80211_regdom=US
  '';
  hardware.wirelessRegulatoryDatabase = true;
  environment.systemPackages = with pkgs; [ dnsmasq hostapd iw ];

  networking.networkmanager.enable = true;
  networking.networkmanager.unmanaged = [
    "interface-name:eth0"
    "interface-name:usb0"
    "interface-name:uap0"
    "interface-name:ap0"
  ];

  users.users.pi = {
    isNormalUser = true;
    initialPassword = "raspberry";
    extraGroups = [ "wheel" "docker" ];
  };
  security.sudo.wheelNeedsPassword = false;
  services.openssh.enable = true;

  virtualisation.docker.enable = true;
  virtualisation.docker.daemon.settings.features.containerd-snapshotter = false;
  networking.firewall.allowedTCPPorts = [ 80 ];

  systemd.tmpfiles.rules = [
    "d /etc/blueos 0755 root root -"
    "d /usr/blueos/bin 0755 root root -"
    "d /usr/blueos/extensions 0755 root root -"
    "d /usr/blueos/userdata 0755 root root -"
    "d /var/logs/blueos 0755 root root -"
    "f /etc/dhcpcd.conf 0644 root root -"
    "f /etc/resolv.conf.host 0644 root root -"
  ];
}
