{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.blueos;
  inherit (lib)
    mkIf
    mkOption
    mkDefault
    mkForce
    types
    ;

  # blueos-core carries the venv, one wrapper per Python service, and the built
  # frontend. Its `src` is the patched BlueOS tree, which still owns the nginx,
  # zenoh and udev inputs that are not Python packages.
  blueos = cfg.package;
  src = blueos.passthru.src;

  version = cfg.version;

  nginxConf =
    builtins.replaceStrings
      [
        "user www-data;\n"
        "worker_processes auto;\n"
        "pid /run/nginx.pid;\n"
        "/etc/nginx/mime.types"
        "include cors.conf;"
        "/home/pi/frontend"
        "/home/pi/tools/nginx/extensions"
        # Version chooser is replaced with blueos-updates
        "location /version-chooser/ {"
      ]
      [
        ""
        ""
        ""
        "${pkgs.nginx}/conf/mime.types"
        "include ${src}/core/tools/nginx/cors.conf;"
        "${blueos}/share/blueos-frontend"
        "/var/lib/blueos/nginx-extensions"
        "location /updates/ {"
      ]
      (builtins.readFile "${src}/core/tools/nginx/nginx.conf");
in
{
  imports = [
    ./services.nix
    ./rollback.nix
    ./version.nix
  ];

  options.services.blueos = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = "Enable BlueOS core on this host.";
    };

    package = mkOption {
      type = types.package;
      description = ''
        The `blueos-core` package to run. It has to come from this flake, since
        the Python environment is built with the flake's uv2nix inputs; the
        flake's `nixosModules.default` supplies it.
      '';
    };

    packages = {
      ardupilot-tools = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/ardupilot-tools { };
        defaultText = lib.literalMD "this flake's package";
        description = "ArduPilot firmware uploader, apj_tool and decoder.";
      };

      bridges = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/bridges { };
        defaultText = lib.literalMD "this flake's package";
        description = "Serial to UDP bridge, used by bridget and ping.";
      };

      mavlink-server = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/mavlink-server { };
        defaultText = lib.literalMD "this flake's package";
        description = "MAVLink router and its web interface, the one ardupilot_manager drives.";
      };

      mavlink2rest = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/mavlink2rest { };
        defaultText = lib.literalMD "this flake's package";
        description = "MAVLink over REST and websockets.";
      };

      linux2rest = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/linux2rest { };
        defaultText = lib.literalMD "this flake's package";
        description = "Exposes host information as JSON over HTTP.";
      };

      mavlink-camera-manager = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/mavlink-camera-manager { };
        defaultText = lib.literalMD "this flake's package";
        description = "Camera streaming service.";
      };

      machineid-cli = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/machineid-cli { };
        defaultText = lib.literalMD "this flake's package";
        description = "Generates the hardware uuid BlueOS reports.";
      };

      updates = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/blueos-updates { };
        defaultText = lib.literalMD "this flake's package";
        description = "Update daemon, which lists and activates NixOS generations.";
      };

      disktest = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/disktest { };
        defaultText = lib.literalMD "this flake's package";
        description = "Sequential disk read/write benchmark used by disk_usage.";
      };

      mcap = mkOption {
        type = types.package;
        default = pkgs.mcap-cli;
        defaultText = lib.literalMD "nixpkgs' mcap-cli";
        description = "MCAP CLI, which recorder_extractor runs doctor and recover with.";
      };

      mcap-foxglove-video-extract = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/mcap-foxglove-video-extract { };
        defaultText = lib.literalMD "this flake's package";
        description = "Extracts video tracks out of MCAP recordings.";
      };

      zenoh = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/zenoh { };
        defaultText = lib.literalMD "this flake's package";
        description = "Zenoh router, with the rest and storage plugins.";
      };

      zenoh-backend-filesystem = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/zenoh-backend-filesystem { };
        defaultText = lib.literalMD "this flake's package";
        description = "Zenoh filesystem storage backend.";
      };

      blueos-recorder = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/blueos-recorder { };
        defaultText = lib.literalMD "this flake's package";
        description = "Records Zenoh traffic to MCAP files.";
      };

      zenoh-plugin-remote-api = mkOption {
        type = types.package;
        default = pkgs.callPackage ../../packages/zenoh-plugin-remote-api { };
        defaultText = lib.literalMD "this flake's package";
        description = "Zenoh websocket plugin, which the frontend's zenoh-ts client speaks to.";
      };
    };

    mavlink = {
      systemId = mkOption {
        type = types.ints.positive;
        default = 1;
        description = "MAVLink system id for the onboard computer.";
      };

      componentId = mkOption {
        type = types.ints.positive;
        default = 194;
        description = "MAVLink component id for the onboard computer.";
      };
    };

    board = mkOption {
      type = types.str;
      default = "unknown";
      example = "pi4";
      description = ''
        Board identifier, which selects the releases the update daemon offers.
        It has to match the `board` field the release manifest publishes.
      '';
    };

    updates = {
      manifestUrl = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "https://releases.example.com/blueos/manifest.json";
        description = ''
          Where the update daemon reads the list of published releases. Without
          one, the vehicle can still switch between the generations already on
          the card, but is told no remote versions exist.
        '';
      };
    };

    user = {
      name = mkOption {
        type = types.str;
        default = "pi";
        description = "Unprivileged account used by bridget and ping.";
      };

      initialPassword = mkOption {
        type = types.str;
        default = "raspberry";
        description = "Password for that account, matching BlueOS's own default.";
      };
    };

    cache = {
      # Placeholder defaults, inherited from the original standalone flake.
      # Replace both with BlueRobotics-owned values, or set them to null to ship
      # a device that trusts no cache beyond nixpkgs.
      host = mkOption {
        type = types.nullOr types.str;
        default = "https://cache.eric.dev.br";
        description = ''
          Trusted Nix binary cache to use for BlueOS updates. The manifest a
          device reads has to name store paths this cache can serve, so both
          usually belong to the same deployment.
        '';
      };

      publicKey = mkOption {
        type = types.nullOr types.str;
        default = "cache.eric.dev.br-1:szEyq5LCjxDCUHYSRaSFU5HdHmR7QlT+FRG3tB9QtpE=";
        description = "Public key for the trusted Nix binary cache.";
      };
    };

    raspberryPi = {
      enable = mkOption {
        type = types.bool;
        default = pkgs.stdenv.hostPlatform.system == "aarch64-linux";
        defaultText = lib.literalMD "true on aarch64-linux";
        description = ''
          Apply the settings BlueOS expects on a Pi: the i2c bus for the
          Navigator and the UART left free for it.
        '';
      };
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = (blueos.passthru or { }) ? src;
        message = "services.blueos.package must be the blueos-core package from this flake.";
      }
    ];

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

      Welcome to BlueOS ${version}!

      Happy Hacking!

    '';

    users.groups = {
      docker = { };
      podman = { };
    };

    # Podman exists for extensions only
    virtualisation = {
      podman = {
        enable = mkDefault true;
        dockerCompat = mkDefault true;
        dockerSocket.enable = mkDefault true;
        defaultNetwork.settings.dns_enabled = mkDefault true;
      };
      containers = {
        enable = mkDefault true;
        containersConf.settings.engine = {
          compose_warning_logs = mkDefault false;
          # By default, Podman binds ports without listening,
          # making services undiscoverable by helper
          force_port_listen = mkDefault true;
        };
        registries.settings.unqualified-search-registries = mkDefault [ "docker.io" ];
      };
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

    services.nginx = {
      enable = mkDefault true;
      config = nginxConf;
      validateConfigFile = false;
    };

    # helper reloads nginx through this pid file
    environment.etc."blueos/nginx.conf".text = nginxConf;

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
      "L+ /usr/blueos/static - - - - ${blueos.passthru.swagger-ui}"
      "d /usr/blueos/userdata/zenoh 0777 root root -"
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

    systemd.services.nginx.serviceConfig = {
      ReadWritePaths = [
        "/usr/blueos"
        "/var/lib/blueos"
      ];
      LogsDirectory = "nginx";
      SupplementaryGroups = [
        "docker"
        "podman"
      ];
    };

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
      ${builtins.readFile "${src}/install/udev/100.autopilot.rules"}
      ${builtins.readFile "${src}/install/udev/110.usb-power.rules"}
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
