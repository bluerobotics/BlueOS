# Host settings BlueOS expects regardless of whether it runs on systemd or in
# Docker: the network stack, the device permissions, the paths the container
# binds, and the kernel features that video and the Navigator need.
#
# Nothing here starts a BlueOS process. That is what makes it usable by both
# nix/modules/blueos/native.nix and nix/modules/blueos/guest.nix.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.blueos;
  inherit (lib)
    mkDefault
    mkForce
    mkIf
    ;
in
{
  config = mkIf cfg.enable {
    nix.gc = {
      automatic = mkDefault true;
      dates = mkDefault "weekly";
    };

    networking.hostName = mkDefault "";

    networking.firewall.enable = mkDefault false;

    # cable_guy drives usb0 itself, but needs NetworkManager on D-Bus
    networking.networkmanager = {
      enable = mkDefault true;
      unmanaged = [
        "interface-name:usb0"
        "interface-name:uap0"
      ];
    };
    # ModemManager claims the autopilot's serial ports
    networking.modemmanager.enable = mkForce false;

    services.avahi = {
      enable = mkDefault true;
      settings.publish = {
        disable-publishing = false;
        publish-addresses = true;
      };
      extraServiceFiles.blueos = ''
        <?xml version="1.0" standalone='no'?>
        <!DOCTYPE service-group SYSTEM "avahi-service.dtd">
        <service-group>
          <name replace-wildcards="yes">%h</name>
          <service><type>_http._tcp</type><port>80</port></service>
          <service><type>_mavlink._udp</type><port>14550</port></service>
        </service-group>
      '';
    };

    services.openssh.enable = mkDefault true;
    security.sudo.wheelNeedsPassword = mkDefault false;

    nix.settings = {
      experimental-features = [ "nix-command flakes" ];
      trusted-users = [ cfg.user.name ];
    }
    // lib.optionalAttrs (cfg.cache.host != null) {
      extra-substituters = [ cfg.cache.host ];
    }
    // lib.optionalAttrs (cfg.cache.publicKey != null) {
      extra-trusted-public-keys = [ cfg.cache.publicKey ];
    };

    users.users.${cfg.user.name} = {
      isNormalUser = true;
      initialPassword = cfg.user.initialPassword;
      extraGroups = [
        "wheel"
        "dialout"
        "docker"
        "podman"
        "video"
        "i2c"
      ];
    };

    users.motd = mkDefault ''

         │       ___ _           ___  ___
       ╶┘│└╴    | _ ) |_  _ ___ / _ \/ __|
      ───┼───   | _ \ | || / -_) (_) \__ \
       ╶┐│┌╴    |___/_|\_,_\___|\___/|___/
         │

      ${
        lib.optionalString (cfg.motdVersion != null) ''
          Welcome to BlueOS ${cfg.motdVersion}!

        ''
      }Happy Hacking!

    '';

    users.groups = {
      docker = { };
      podman = { };
    };

    # ardupilot_manager downloads glibc-dynamic ArduSub binaries at runtime
    programs.nix-ld.enable = mkDefault true;

    environment.systemPackages = [
      pkgs.sshpass
      pkgs.openssh
      pkgs.dhcpcd
      pkgs.dnsmasq
      pkgs.linux-wifi-hotspot
      pkgs.iw
      pkgs.ifmetric
      pkgs.iproute2
      pkgs.util-linux
      pkgs.i2c-tools
      pkgs.libraspberrypi
      pkgs.tmux
    ];

    systemd.tmpfiles.rules = [
      "d /var/logs/blueos 0777 root root -"
      "d /var/logs/blueos/services 0777 root root -"
      "d /var/lib/blueos/nginx-extensions 0755 root root -"
      "d /usr/blueos/userdata/settings 0777 root root -"
      "d /usr/blueos/userdata/firmware 0777 root root -"
      "d /usr/blueos/extensions 0777 root root -"
      "d /usr/blueos/userdata/recorder 0777 root root -"
      "d /usr/blueos/userdata/modeloverrides 0777 root root -"
      "d /usr/blueos/userdata/branding 0777 root root -"
      "d /usr/blueos/userdata/styles 0777 root root -"
      "d /usr/blueos/userdata/zenoh 0777 root root -"
      "d /usr/blueos/bin 0777 root root -"
      "d /etc/blueos 0755 root root -"
      "d /etc/filebrowser 0755 root root -"
      "d /shortcuts 0755 root root -"
      "d /root/blueos-files 0755 root root -"
      "d /home/${cfg.user.name}/.ssh 0700 ${cfg.user.name} users -"
      "d /root/.config/ardupilot-manager/logs 0755 root root -"
      "L /shortcuts/userdata - - - - /usr/blueos/userdata"
      "L /shortcuts/ardupilot_logs - - - - /root/.config/ardupilot-manager/logs"
      "L /shortcuts/extensions - - - - /usr/blueos/extensions"
      "L /shortcuts/system_logs - - - - /var/logs/blueos"
      "f /etc/hostname 0644 root root - blueos"
    ];

    boot.kernel.sysctl = {
      "net.core.wmem_max" = 16777216;
      "net.core.rmem_max" = 16777216;
      "net.core.wmem_default" = 1048576;
      "net.core.rmem_default" = 1048576;
      "net.core.netdev_max_backlog" = 5000;
      "vm.swappiness" = 10;
    };

    # The journal has no size limit by default, which on a constrained
    # board means a runaway writer can fill the card
    services.journald.settings.Journal = {
      SystemMaxUse = "64M";
      RuntimeMaxUse = "32M";
    };

    services.udev.extraRules = ''
      ${builtins.readFile "${cfg.source}/install/udev/100.autopilot.rules"}
      ${builtins.readFile "${cfg.source}/install/udev/110.usb-power.rules"}
      SUBSYSTEM=="vchiq|vcio|vc-mem", GROUP="video", MODE="0660"
    '';

    hardware.i2c.enable = mkIf cfg.raspberryPi.enable (mkDefault true);
    boot.kernelModules = mkIf cfg.raspberryPi.enable [
      "i2c-dev"
      "i2c-bcm2835"
      "bcm2835-v4l2"
      "dwc2"
      "g_ether"
      "slcan"
    ];
    boot.kernelParams = mkIf cfg.raspberryPi.enable [
      "console=tty1"
      "cgroup_enable=cpuset"
      "cgroup_memory=1"
      "cgroup_enable=memory"
      "iomem=relaxed"
    ];
  };
}
