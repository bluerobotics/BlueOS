{
  imports = [ ./common.nix ];

  image.efiSupport = false;

  virtualisation.docker.enable = true;

  networking.firewall.allowedTCPPorts = [ 80 ];

  # Mount points the BlueOS containers bind to
  systemd.tmpfiles.rules = [
    "d /etc/blueos 0755 root root -"
    "d /usr/blueos/bin 0755 root root -"
    "d /usr/blueos/extensions 0755 root root -"
    "d /usr/blueos/userdata 0755 root root -"
    "d /var/logs/blueos 0755 root root -"
  ];
}
