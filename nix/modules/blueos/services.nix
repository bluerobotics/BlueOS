{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.blueos;
  inherit (lib) mkIf optionals optionalAttrs;

  blueos = cfg.package;
  logs = "/var/logs/blueos/services";
  userdata = "/usr/blueos/userdata";

  motdFile = pkgs.writeText "blueos-motd" ''

       │       ___ _           ___  ___
     ╶┘│└╴    | _ ) |_  _ ___ / _ \/ __|
    ───┼───   | _ \ | || / -_) (_) \__ \
     ╶┐│┌╴    |___/_|\_,_\___|\___/|___/
       │

    Welcome to BlueOS ${cfg.version}!

    What you currently see is a tmux session in BlueOS.

    USAGE NOTES:
    To split the screen horizontally, press ctrl+b then %
    To split the screen vertically, press ctrl+b then "
    To switch tabs, click them or press ctrl+b then use the directional keys in the keyboard

    Happy Hacking!

  '';

  ttydEntry = pkgs.writeShellScript "ttyd-entry" ''
    tmux attach -t user_terminal 2>/dev/null || \
      tmux new -s user_terminal "cat ${motdFile}; exec ${pkgs.bashInteractive}/bin/bash -l"
  '';

  zenohConfig = pkgs.writeText "blueos-zenoh.json5" (
    builtins.toJSON {
      adminspace.enabled = true;
      metadata.name = "vehicle";
      plugins_loading = {
        enabled = true;
        search_dirs = [
          "${cfg.packages.zenoh}/lib"
          "${cfg.packages.zenoh-backend-filesystem}/lib"
          "${cfg.packages.zenoh-plugin-remote-api}/lib"
        ];
      };
      plugins = {
        rest.http_port = 7117;
        remote_api.websocket_port = 7118;
      };
    }
  );

  gstPluginPath = lib.makeSearchPathOutput "lib" "lib/gstreamer-1.0" (
    with pkgs.gst_all_1;
    [
      gstreamer
      gst-plugins-base
      gst-plugins-good
      gst-plugins-bad
      gst-plugins-ugly
      gst-libav
      gst-plugins-rs
      pkgs.libcamera
      pkgs.libnice
    ]
  );

  toolPath = [
    cfg.packages.ardupilot-tools
    cfg.packages.bridges
    cfg.packages.disktest
    cfg.packages.machineid-cli
    cfg.packages.mavlink-server
    cfg.packages.mcap
    cfg.packages.mcap-foxglove-video-extract
    pkgs.gst_all_1.gst-plugins-base
  ];

  python = name: args: lib.escapeShellArgs ([ "${blueos}/bin/${name}" ] ++ args);

  mkService =
    {
      name,
      exec,
      memoryMax ? null,
      nice ? 0,
      user ? "root",
      path ? [ ],
      after ? [ ],
      environment ? { },
      serviceConfig ? { },
      preStart ? "",
    }:
    {
      description = "BlueOS ${name}";
      wantedBy = [ "blueos.target" ];
      partOf = [ "blueos.target" ];
      after = [ "network.target" ] ++ after;
      restartTriggers = [ blueos ];
      path = [ "/run/current-system/sw" ] ++ toolPath ++ path;
      environment = {
        MAV_SYSTEM_ID = toString cfg.mavlink.systemId;
        MAV_COMPONENT_ID_ONBOARD_COMPUTER4 = toString cfg.mavlink.componentId;
        GIT_DESCRIBE_TAGS = cfg.gitDescribe;
        RUST_BACKTRACE = "1";
        GLIBC_TUNABLES = "glibc.malloc.hugetlb=0";
      }
      // environment;
      preStart = "mkdir -p ${logs}/${name}\n" + preStart;
      serviceConfig = {
        ExecStart = exec;
        Restart = "always";
        RestartSec = 1;
        Nice = nice;
        User = user;
        WorkingDirectory = "/";
      }
      // optionalAttrs (memoryMax != null) { MemoryMax = "${toString memoryMax}M"; }
      // serviceConfig;
    };
in
{
  config = mkIf cfg.enable {
    users.users.blueos = {
      isSystemUser = true;
      group = "blueos";
      extraGroups = [ "dialout" ];
      home = "/home/blueos";
      createHome = true;
    };
    users.groups.blueos = { };

    systemd.tmpfiles.rules = [
      # ardupilot_manager chmods the file before installing it
      "C+ /root/blueos-files/ardupilot-manager/default/ardupilot_navigator64 - - - - ${
        pkgs.fetchurl {
          url = "https://firmware.ardupilot.org/Sub/stable-4.5.3/navigator64/ardusub";
          hash = "sha256-mV5Rv5xo8TGnh+Csa4QJxryxPjcUyWKuSF23YJs85Hk=";
        }
      }"
    ]
    ++
      optionals cfg.raspberryPi.enable
        # ArduSub identifies the board from the soc node,
        # which this kernel names soc@107c000000
        [
          "C /run/blueos/device-tree - - - - /sys/firmware/devicetree/base"
          "L /run/blueos/device-tree/soc - - - - soc@107c000000"
        ];

    systemd.targets.blueos = {
      description = "BlueOS";
      wantedBy = [ "multi-user.target" ];
    };

    systemd.services = {
      blueos-uuids = {
        description = "BlueOS hardware and software uuids";
        wantedBy = [ "blueos.target" ];
        before = [ "blueos.target" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          ${cfg.packages.machineid-cli}/bin/machineid-cli \
            --key blueos --parts cpu-cores cpuid mac-address > /etc/blueos/hardware-uuid

          if [ ! -s /etc/blueos/uuid ]; then
            ${pkgs.util-linux}/bin/uuidgen | ${pkgs.coreutils}/bin/tr -d '-' > /etc/blueos/uuid
          fi
        '';
      };

      ardupilot-manager = mkService {
        name = "ardupilot_manager";
        nice = -19;
        exec = python "ardupilot_manager" [ ];
        environment = {
          inherit (config.environment.variables) NIX_LD NIX_LD_LIBRARY_PATH;
        };
        serviceConfig =
          optionalAttrs cfg.raspberryPi.enable {
            BindReadOnlyPaths = [ "/run/blueos/device-tree:/sys/firmware/devicetree/base" ];
          }
          // {
            PrivateDevices = false;
            RestrictAddressFamilies = [ ];
          };
      };

      video = mkService {
        name = "mavlink-camera-manager";
        nice = -19;
        exec = ''
          ${cfg.packages.mavlink-camera-manager}/bin/mavlink-camera-manager \
            --default-settings BlueROVUDP \
            --mavlink tcpout:127.0.0.1:5777 \
            --mavlink-system-id ${toString cfg.mavlink.systemId} \
            --mavlink-camera-component-id-range=100-105 \
            --gst-feature-rank omxh264enc=0,v4l2h264enc=250,x264enc=260 \
            --log-path ${logs}/mavlink-camera-manager \
            --stun-server stun://stun.l.google.com:19302 \
            --enable-realtime-threads \
            --recorder=external \
            --zenoh \
            --verbose
        '';
        environment.GST_PLUGIN_SYSTEM_PATH_1_0 = gstPluginPath;
        serviceConfig.PrivateDevices = false;
      };

      mavlink2rest = mkService {
        name = "mavlink2rest";
        exec = ''
          ${cfg.packages.mavlink2rest}/bin/mavlink2rest \
            --connect=udpout:127.0.0.1:14001 \
            --server [::]:6040 \
            --system-id ${toString cfg.mavlink.systemId} \
            --component-id ${toString cfg.mavlink.componentId}
        '';
      };

      cable-guy = mkService {
        name = "cable_guy";
        exec = python "cable_guy" [ ];
        serviceConfig = {
          PrivateDevices = false;
          RestrictAddressFamilies = [ ];
          CapabilityBoundingSet = [
            "CAP_NET_ADMIN"
            "CAP_NET_RAW"
            "CAP_NET_BIND_SERVICE"
          ];
        };
      };

      kraken = mkService {
        name = "kraken";
        nice = 19;
        exec = python "kraken" [ ];
        serviceConfig.SupplementaryGroups = [
          "docker"
          "podman"
        ];
      };

      wifi = mkService {
        name = "wifi";
        nice = 19;
        exec = python "wifi" [
          "--socket"
          "wlan0"
        ];
        serviceConfig = {
          RestrictAddressFamilies = [ ];
          PrivateDevices = false;
        };
      };

      zenohd = mkService {
        name = "zenohd";
        exec = ''
          ${cfg.packages.zenoh}/bin/zenohd -c ${zenohConfig}
        '';
        environment.ZENOH_BACKEND_FS_ROOT = "${userdata}/zenoh";
      };

      recorder = mkService {
        name = "recorder";
        memoryMax = 250;
        exec = ''
          ${cfg.packages.blueos-recorder}/bin/blueos-recorder \
            --recorder-path ${userdata}/recorder
        '';
      };

      beacon = mkService {
        name = "beacon";
        memoryMax = 250;
        exec = python "beacon" [ ];
        serviceConfig.RestrictAddressFamilies = [ ];
      };

      bridget = mkService {
        name = "bridget";
        nice = 19;
        user = "blueos";
        exec = python "bridget" [ ];
        serviceConfig.PrivateDevices = false;
      };

      commander = mkService {
        name = "commander";
        memoryMax = 250;
        exec = python "commander" [ ];
      };

      nmea-injector = mkService {
        name = "nmea_injector";
        memoryMax = 250;
        nice = 19;
        exec = python "nmea_injector" [ ];
      };

      helper = mkService {
        name = "helper";
        memoryMax = 250;
        exec = python "helper" [ ];
        after = [ "blueos-uuids.service" ];
        serviceConfig.ReadOnlyPaths = [ "/etc/blueos" ];
      };

      pardal = mkService {
        name = "pardal";
        memoryMax = 250;
        nice = 19;
        exec = python "pardal" [ ];
      };

      ping = mkService {
        name = "ping";
        nice = 19;
        user = "blueos";
        exec = python "ping" [ ];
        serviceConfig.PrivateDevices = false;
      };

      blueos-updates = mkService {
        name = "blueos-updates";
        memoryMax = 250;
        exec = "${cfg.packages.updates}/bin/blueos-updates";
        environment = {
          BLUEOS_BOARD = cfg.board;
          BLUEOS_UPDATES_ADDR = "127.0.0.1:8081";
        }
        // lib.optionalAttrs (cfg.updates.manifestUrl != null) {
          BLUEOS_UPDATES_MANIFEST = cfg.updates.manifestUrl;
        };
      };

      bag-of-holding = mkService {
        name = "bag_of_holding";
        memoryMax = 250;
        exec = python "bag_of_holding" [ ];
      };

      recorder-extractor = mkService {
        name = "recorder_extractor";
        memoryMax = 250;
        exec = python "recorder_extractor" [ ];
        serviceConfig.ReadWritePaths = [ "${userdata}/recorder" ];
      };

      disk-usage = mkService {
        name = "disk_usage";
        memoryMax = 250;
        exec = python "disk_usage" [ ];
        serviceConfig.PrivateDevices = false;
      };

      customization = mkService {
        name = "customization";
        memoryMax = 250;
        exec = python "customization" [ ];
        serviceConfig.ReadWritePaths = [ userdata ];
      };

      linux2rest = mkService {
        name = "linux2rest";
        memoryMax = 250;
        path = [ pkgs.libraspberrypi ];
        exec = ''
          ${cfg.packages.linux2rest}/bin/linux2rest \
            --log-settings netstat=30,platform=10,serial-ports=10,cpu=10,disk=30,info=10,memory=10,network=10,process=60,temperature=10,unix-time-seconds=10,usb=60
        '';
        serviceConfig = {
          ProtectProc = "default";
          PrivateDevices = false;
        };
      };
      iperf3 = mkService {
        name = "iperf3";
        memoryMax = 250;
        exec = "${pkgs.iperf3}/bin/iperf3 --server --port 5201";
      };

      filebrowser = mkService {
        name = "filebrowser";
        memoryMax = 250;
        nice = 19;
        path = [ pkgs.filebrowser ];
        preStart = ''
          if [ ! -f /etc/filebrowser/filebrowser.db ]; then
            filebrowser config init \
              --address=0.0.0.0 --port=7777 --auth.method=noauth \
              --log=stdout --root=/shortcuts \
              --database=/etc/filebrowser/filebrowser.db
          fi

          filebrowser config set --followExternalSymlinks \
            --database=/etc/filebrowser/filebrowser.db

          if [ "$(filebrowser users ls --database=/etc/filebrowser/filebrowser.db | wc -l)" -lt 2 ]; then
            filebrowser users add ${cfg.user.name} "$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)" \
              --database=/etc/filebrowser/filebrowser.db
          fi
        '';
        exec = ''
          ${pkgs.filebrowser}/bin/filebrowser \
            --database /etc/filebrowser/filebrowser.db --baseurl /file-browser
        '';
        serviceConfig.ReadWritePaths = [ "/etc/filebrowser" ];
      };

      ttyd = mkService {
        name = "ttyd";
        memoryMax = 250;
        nice = 19;
        path = [ pkgs.tmux ];
        exec = "${pkgs.ttyd}/bin/ttyd -W -p 8088 ${ttydEntry}";
      };
    };
  };
}
